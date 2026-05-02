#!/usr/bin/env python3
"""Convert IELTS lesson HTMLs into interactive AI-feature versions.

Usage:
  python scripts/make_interactive.py \\
      --in . \\
      --out Interactive/ \\
      --endpoint https://abc.fcapp.run \\
      --bucket-base http://8.168.22.242/storage/v1/object/public/ielts-interactive

Idempotent — re-running with the same args overwrites the output. Originals
are NEVER modified; output always lands in --out.

The script applies three insertions to each `Week_*.html`:
  1. CSS block (with embedded base64 woff2 fonts) after the `.lines {}` rule
  2. Wraps the two `.draft-page` `<div class="lines">` elements in
     `<div class="lines-overlay-host">` along with the overlay UI snippets
  3. `<script>` block before `</body>` with build-time substitutions
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path
from typing import Iterable

# Optional minification — saves ~40% on the JS+CSS bytes shipped per Week
# HTML (~36 KB per file with current code). If rjsmin / rcssmin aren't
# installed we silently fall back to unminified output (the script still
# works, the files are just larger). Install with:
#     pip install rjsmin rcssmin
try:
    import rjsmin  # type: ignore
    import rcssmin  # type: ignore
    _HAVE_MINIFIERS = True
except ImportError:
    _HAVE_MINIFIERS = False

SENTINEL = "<!-- AI-INTERACTIVE-V1 -->"
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
FONT_DIR = SCRIPT_DIR / "fonts"


class SkipFile(RuntimeError):
    """Raised when a single file's pattern-match fails — caller logs and continues."""


def _files_to_process(in_path: Path) -> Iterable[Path]:
    if in_path.is_file():
        if re.fullmatch(r"Week_\d{2}\.html", in_path.name):
            yield in_path
        return
    for p in sorted(in_path.glob("Week_*.html")):
        yield p


# ---------- Insertion 1: CSS block after the `.lines {}` rule ----------

LINES_RULE_RE = re.compile(
    r"(\.lines\s*\{[^}]*\})",
    re.DOTALL,
)


def _load_fonts() -> dict[str, str]:
    """Return {placeholder_token: base64_woff2} for every embedded font."""
    out: dict[str, str] = {}
    for token, fname in (
        ("__CAVEAT_400_BASE64__", "Caveat-400.woff2"),
        ("__INDIE_FLOWER_400_BASE64__", "IndieFlower-400.woff2"),
    ):
        path = FONT_DIR / fname
        if not path.exists():
            raise FileNotFoundError(
                f"Font file missing: {path}. See scripts/fonts/ for expected files."
            )
        out[token] = base64.b64encode(path.read_bytes()).decode("ascii")
    return out


def _load_inserted_css(minify: bool = True) -> str:
    css = (TEMPLATE_DIR / "inserted_css.css").read_text(encoding="utf-8")
    fonts = _load_fonts()
    for token, b64 in fonts.items():
        if token not in css:
            raise SkipFile(f"CSS template missing placeholder {token}.")
        css = css.replace(token, b64, 1)
    if minify and _HAVE_MINIFIERS:
        # Minify AFTER font substitution so the base64 strings are passed
        # through verbatim (cssmin treats data: URLs correctly).
        css = rcssmin.cssmin(css)
    return css


def insertion_1_css(html: str, minify: bool = True) -> str:
    css = _load_inserted_css(minify=minify)
    block = f"\n    /* {SENTINEL} CSS */\n    {css}\n"
    # Capture the matched rule as a closure variable so the replacement is a
    # plain string concatenation, not a regex template (avoids back-reference
    # interpretation of `\s` etc. inside the embedded base64 fonts).
    new_html, count = LINES_RULE_RE.subn(lambda m: m.group(1) + block, html, count=1)
    if count != 1:
        raise SkipFile("Could not find `.lines { … }` rule for CSS insertion.")
    return new_html


# ---------- Insertion 2: wrap original .lines inside .lines-overlay-host ----------

DRAFT_LINES_RE = re.compile(
    r"(<strong>Draft:</strong>)\s*(<div class=\"lines\"[^>]*></div>)",
    re.IGNORECASE,
)
POLISHED_LINES_RE = re.compile(
    r"(<strong>Polished Rewrite:</strong>)\s*(<div class=\"lines\"[^>]*></div>)",
    re.IGNORECASE,
)


def _load_overlay(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def insertion_2_draft_page(html: str) -> str:
    """Augment the .draft-page Draft and Polished Rewrite sections in place.

    Per spec §6.2: the original `<div class="lines">` is KEPT in HTML so the
    file structure remains regular and is hidden via `.draft-page .lines
    { display: none; }` in the inserted CSS.

    The overlay snippets define the FULL post-heading structure (button-row
    + status + lines-overlay-host wrapper). The script substitutes
    `__ORIG_LINES__` inside each snippet with the captured original `.lines`
    div so it ends up nested inside `.lines-overlay-host`. This lets the
    button-row sit OUTSIDE the lines area (next to the `<strong>Draft:</strong>`
    heading) while the original `.lines` stays in the markup.
    """
    draft_overlay = _load_overlay("draft_section_overlay.html")
    polished_overlay = _load_overlay("polished_section_overlay.html")
    if "__ORIG_LINES__" not in draft_overlay:
        raise SkipFile("draft_section_overlay.html missing __ORIG_LINES__ placeholder.")
    if "__ORIG_LINES__" not in polished_overlay:
        raise SkipFile("polished_section_overlay.html missing __ORIG_LINES__ placeholder.")

    def wrap_draft(m: re.Match) -> str:
        label, lines_div = m.group(1), m.group(2)
        return f"{label}\n{draft_overlay.replace('__ORIG_LINES__', lines_div, 1)}"

    def wrap_polished(m: re.Match) -> str:
        label, lines_div = m.group(1), m.group(2)
        return f"{label}\n{polished_overlay.replace('__ORIG_LINES__', lines_div, 1)}"

    new_html, c1 = DRAFT_LINES_RE.subn(wrap_draft, html, count=1)
    if c1 != 1:
        raise SkipFile("Could not find `<strong>Draft:</strong>` + .lines anchor.")
    new_html, c2 = POLISHED_LINES_RE.subn(wrap_polished, new_html, count=1)
    if c2 != 1:
        raise SkipFile("Could not find `<strong>Polished Rewrite:</strong>` + .lines anchor.")
    return new_html


# ---------- Insertion 3: <script> block before </body> ----------

BODY_CLOSE_RE = re.compile(r"</body>", re.IGNORECASE)


def insertion_3_script(html: str, endpoint: str, bucket_base: str, lesson_key: str,
                       minify: bool = True) -> str:
    js = (TEMPLATE_DIR / "inserted_script.js").read_text(encoding="utf-8")
    pron_url = bucket_base.rstrip("/") + "/pronunciations.json"
    js = js.replace("__AI_ENDPOINT__", endpoint.rstrip("/"))
    js = js.replace("__PRONUNCIATIONS_URL__", pron_url)
    js = js.replace("__LESSON_KEY__", lesson_key)
    if minify and _HAVE_MINIFIERS:
        # rjsmin is whitespace+comment minification only — it does NOT
        # rename identifiers or reorder code, so it's safe for this
        # IIFE-wrapped script that exposes only `window.__ielts.*` from
        # the outside. Modern syntax (async/await, template literals,
        # arrow functions) is preserved verbatim.
        js = rjsmin.jsmin(js)
    block = f"\n<script>\n/* {SENTINEL} SCRIPT */\n{js}\n</script>\n"
    # Use a callable replacement so Python doesn't interpret JS regex escapes
    # (e.g. `/\s+/` inside the script) as back-references.
    replacement = block + "</body>"
    new_html, count = BODY_CLOSE_RE.subn(lambda _m: replacement, html, count=1)
    if count != 1:
        raise SkipFile("Could not find </body> closing tag.")
    return new_html


# ---------- Compose ----------

# ---------- Insertion 4: brainstorming-map quadrants editable + recorder ----------

# Each <div class="spider-leg"> becomes contenteditable so students can
# type or scribble (iPad Scribble) their own notes in each quadrant.
SPIDER_LEG_OPEN_RE = re.compile(
    r'(<div class="spider-leg")(\s|>)',
)
# Each <div class="spider-container"> gets a small recorder widget at top-right
# of the PARENT card (not inside the spider-container itself, since the spider
# layout is a fixed-aspect grid that would clip absolute children at its top).
# We inject the widget as a SIBLING immediately BEFORE the spider-container
# opening tag — the parent card's `:has(> .voice-recorder-container.vr-inline)`
# CSS rule promotes that card to `position: relative` so the recorder anchors
# to the card's top-right corner.
SPIDER_CONTAINER_OPEN_RE = re.compile(
    r'(<div class="spider-container"[^>]*>)',
)


def insertion_4_brainstorming_maps(html: str) -> str:
    """Make spider-legs contenteditable + add a unique recorder per spider-container."""
    # Idempotency check: look for the actual SPIDER-LEG markup with the
    # contenteditable attribute applied — NOT just the bare attribute string,
    # which also occurs inside the injected CSS rule
    # `.spider-leg[contenteditable="plaintext-only"] { ... }`.
    if re.search(r'<div class="spider-leg"[^>]*\bcontenteditable\b', html):
        return html

    # 1. spider-leg → contenteditable
    new_html, leg_count = SPIDER_LEG_OPEN_RE.subn(
        lambda m: m.group(1) + ' contenteditable="plaintext-only"' + m.group(2),
        html,
    )
    if leg_count == 0:
        # No spider-legs at all — skip silently, this insertion is best-effort.
        return html

    # 2. spider-container → inject recorder widget with unique recorder-id
    inline_template = (TEMPLATE_DIR / "voice_recorder_widget_inline.html").read_text(encoding="utf-8")
    map_counter = {"n": 0}

    def inject_map_recorder(m: re.Match) -> str:
        map_counter["n"] += 1
        recorder_id = f"map-{map_counter['n']}"
        widget = inline_template.replace("__RECORDER_ID__", recorder_id, 1)
        # Inject BEFORE the spider-container opening tag so the recorder is a
        # sibling (anchored to the parent card's top-right via CSS), NOT a
        # child of the fixed-aspect spider grid which would clip it.
        return widget + "\n" + m.group(1)

    new_html, _ = SPIDER_CONTAINER_OPEN_RE.subn(inject_map_recorder, new_html)
    return new_html


# ---------- Insertion 5: Q1-Q6 writing boxes — textarea overlay + recorder ----------

# Each <h3>QN: ...</h3> heading marks a Q1..Q6 writing-box card. Inside that
# card is a single empty `<div class="lines" ...></div>`. We replace it with:
#   <div class="q-write-host">
#     <textarea class="q-write-textarea" data-q-id="qN"></textarea>
#     <ORIGINAL .lines></ORIGINAL>     <!-- preserved for print fallback -->
#   </div>
#   <recorder widget data-recorder-id="qN" />   <!-- SIBLING, not child -->
# The recorder sits OUTSIDE .q-write-host so it can be absolute-positioned
# against the parent green writing window's bottom-right corner without
# fighting the textarea's `top:0; bottom:0` fill. The parent gains
# `position: relative` via the CSS `:has(> .q-write-host)` rule.
# Use a non-greedy regex that captures from the QN heading to the next .lines
# div within the same card.
Q_WRITE_RE = re.compile(
    r'(<h3[^>]*>Q(\d+):)(.*?)(<div class="lines"[^>]*></div>)',
    re.DOTALL,
)


def insertion_5_q_writing(html: str) -> str:
    """Convert each Q1-Q6 .lines div into a textarea+recorder-host."""
    # Idempotency check: look for an actual <div class="q-write-host"> in the
    # body — NOT the bare class name, which also appears in the injected CSS
    # rule `.q-write-host { ... }`.
    if '<div class="q-write-host">' in html:
        return html

    inline_template = (TEMPLATE_DIR / "voice_recorder_widget_inline.html").read_text(encoding="utf-8")

    def wrap(m: re.Match) -> str:
        head = m.group(1)
        n = m.group(2)
        between = m.group(3)
        orig_lines = m.group(4)
        recorder_id = f"q{n}"
        recorder = inline_template.replace("__RECORDER_ID__", recorder_id, 1)
        # Recorder is a SIBLING of .q-write-host (both children of the green
        # writing-window card) so the textarea can fill .q-write-host without
        # clashing with the recorder's bottom-right anchor.
        host = (
            f'<div class="q-write-host">\n'
            f'  <textarea class="q-write-textarea" data-q-id="{recorder_id}" '
            f'spellcheck="false"></textarea>\n'
            f'  {orig_lines}\n'
            f'</div>\n'
            f'{recorder}'
        )
        return f'{head}{between}{host}'

    new_html, count = Q_WRITE_RE.subn(wrap, html)
    return new_html


_BODY_CLASS_RE = re.compile(r'<body\b([^>]*)>', re.IGNORECASE)


def insertion_6_body_class(html: str) -> str:
    """Add `is-interactive` to <body class="..."> so interactive-only CSS
    rules (e.g. `.email-recordings-btn` visibility) can target the
    interactive layer without affecting print/PDF output. Idempotent —
    skip if already present.
    """
    m = _BODY_CLASS_RE.search(html)
    if not m:
        return html
    attrs = m.group(1)
    if 'is-interactive' in attrs:
        return html  # already added
    if re.search(r'\bclass\s*=', attrs, re.IGNORECASE):
        # Append to existing class list
        new_attrs = re.sub(
            r'(\bclass\s*=\s*"([^"]*)")',
            lambda mm: f'class="{mm.group(2).strip()} is-interactive"',
            attrs, count=1, flags=re.IGNORECASE,
        )
        # Same fallback for single-quoted class
        if new_attrs == attrs:
            new_attrs = re.sub(
                r"(\bclass\s*=\s*'([^']*)')",
                lambda mm: f"class='{mm.group(2).strip()} is-interactive'",
                attrs, count=1, flags=re.IGNORECASE,
            )
    else:
        new_attrs = attrs + ' class="is-interactive"'
    return html[:m.start()] + f'<body{new_attrs}>' + html[m.end():]


def transform(orig_path: Path, endpoint: str, bucket_base: str,
              minify: bool = True) -> str:
    """Apply the five insertions and return the new HTML."""
    html = orig_path.read_text(encoding="utf-8")
    html = insertion_1_css(html, minify=minify)
    html = insertion_2_draft_page(html)
    html = insertion_4_brainstorming_maps(html)
    html = insertion_5_q_writing(html)
    html = insertion_3_script(html, endpoint, bucket_base, orig_path.stem,
                              minify=minify)
    html = insertion_6_body_class(html)
    return html


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, type=Path,
                    help="Folder containing originals OR a single Week_NN.html")
    ap.add_argument("--out", dest="dst", required=True, type=Path,
                    help="Output folder for interactive files")
    ap.add_argument("--endpoint", required=True,
                    help="Function Compute URL (e.g. https://abc.fcapp.run)")
    ap.add_argument("--bucket-base", required=True,
                    help="Public bucket URL prefix where pronunciations.json lives")
    ap.add_argument("--no-minify", dest="minify", action="store_false",
                    help="Skip JS+CSS minification (useful for debugging — produces "
                         "readable output but ~40%% larger files).")
    ap.set_defaults(minify=True)
    args = ap.parse_args()

    if args.minify and not _HAVE_MINIFIERS:
        print("note: rjsmin/rcssmin not installed — emitting unminified output. "
              "Install with `pip install rjsmin rcssmin` for ~40%% smaller files.",
              file=sys.stderr)

    if not args.src.exists():
        print(f"error: --in path does not exist: {args.src}", file=sys.stderr)
        return 2
    args.dst.mkdir(parents=True, exist_ok=True)

    processed: list[str] = []
    skipped: list[tuple[str, str]] = []

    for orig_path in _files_to_process(args.src):
        try:
            new_html = transform(orig_path, args.endpoint, args.bucket_base,
                                 minify=args.minify)
            out_path = args.dst / orig_path.name
            out_path.write_text(new_html, encoding="utf-8", newline="\n")
            processed.append(orig_path.name)
        except SkipFile as e:
            skipped.append((orig_path.name, str(e)))
        except Exception as e:  # unexpected — fail loudly with file context
            print(f"FATAL while processing {orig_path.name}: {e}", file=sys.stderr)
            raise

    # Sync images/ alongside the generated HTMLs so relative paths like
    # `<img src="images/foo.png">` resolve when a user opens any
    # Interactive/Week_NN.html locally OR via OSS root deployment.
    # Without this step, all Interactive HTMLs render with broken-image
    # placeholders even though the canonical references are correct.
    src_images = args.src / "images" if args.src.is_dir() else args.src.parent / "images"
    dst_images = args.dst / "images"
    if src_images.is_dir():
        import shutil
        dst_images.mkdir(exist_ok=True)
        copied = 0
        for img in src_images.iterdir():
            if img.is_file() and img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"):
                shutil.copy2(img, dst_images / img.name)
                copied += 1
        if copied:
            print(f"Synced {copied} image(s) from {src_images} -> {dst_images}")
    else:
        print(f"note: no images/ folder at {src_images} — Interactive HTMLs may show "
              f"broken-image placeholders for embedded <img> tags",
              file=sys.stderr)

    print(f"Processed: {len(processed)}")
    for n in processed:
        print(f"  [ok] {n}")
    if skipped:
        print(f"Skipped: {len(skipped)}")
        for n, why in skipped:
            print(f"  [skip] {n} -- {why}")
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
