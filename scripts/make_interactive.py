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
import time
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


def _write_text_with_retry(path: Path, text: str, *, max_attempts: int = 5) -> None:
    """Write `text` to `path`, riding through transient OneDrive sync locks.

    The repo lives inside a OneDrive folder. When the pipeline writes all
    40 Interactive/Week_*.html files back-to-back, OneDrive's sync filter
    driver is still settling a freshly-written file when the next
    CreateFile arrives — Windows then rejects the open with EINVAL
    (errno 22) or, less often, EACCES (errno 13). It is a pure race: the
    same write succeeds in isolation and fails on a different week each
    run.

    Same retry-with-backoff shape as upload_to_oss.py's put_with_retry —
    retry only the known-transient errnos, re-raise everything else
    (ENOENT, ENOSPC, ...) immediately so real bugs still surface.
    """
    TRANSIENT_ERRNOS = {22, 13}  # EINVAL, EACCES — OneDrive sync-filter races
    for attempt in range(max_attempts):
        try:
            path.write_text(text, encoding="utf-8", newline="\n")
            if attempt > 0:
                print(f"    (write recovered after {attempt + 1} attempts: {path.name})")
            return
        except OSError as e:
            if e.errno not in TRANSIENT_ERRNOS or attempt == max_attempts - 1:
                raise
            wait_s = 0.3 * (2 ** attempt)  # 0.3, 0.6, 1.2, 2.4 s
            print(f"    OneDrive lock on {path.name} (errno {e.errno}), "
                  f"retrying in {wait_s:.1f}s (attempt {attempt + 1}/{max_attempts})")
            time.sleep(wait_s)


# ---------- Insertion 1: CSS block injected just before </style> ----------
#
# Round 43 (2026-05-12) — switched anchor from `.lines { … }` to `</style>`.
# The previous anchor was a single-brace regex via DOTALL that would
# silently SkipFile (and drop the entire week from the bake) if anyone
# added a /* comment */ inside .lines{}, a nested selector, or split the
# rule across lines. Anchoring on </style> (one per template) is robust
# to all of those harmless template edits. Side benefit: our injected
# rules now win source-order cascade ties over the template's defaults,
# which is what inserted_css.css is intended to do.

STYLE_CLOSE_RE = re.compile(r"(</style>)", re.IGNORECASE)


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
    # Round 43 — insert the block BEFORE </style> so our CSS lives inside
    # the existing <style> element. Closure-based replacement avoids
    # back-reference interpretation of `\s` etc. inside the embedded
    # base64 fonts (which would otherwise corrupt the data: URLs).
    new_html, count = STYLE_CLOSE_RE.subn(lambda m: block + m.group(1), html, count=1)
    if count != 1:
        raise SkipFile(
            "Could not find </style> closing tag to anchor CSS insertion. "
            "Template structure may have changed unexpectedly."
        )
    return new_html


# ---------- Insertion 2: wrap original .lines inside .lines-overlay-host ----------

# Round 43 (2026-05-12) — anchor on <!-- DRAFT_BOX_BEGIN --> and
# <!-- POLISHED_BOX_BEGIN --> sentinel comments rather than on the literal
# "<strong>Draft:</strong>" / "<strong>Polished Rewrite:</strong>" text.
# The sentinel is captured INSIDE group(1) so the substitution callback
# (which emits group(1) + overlay) preserves it for re-bake idempotency.
DRAFT_LINES_RE = re.compile(
    r'(<!--\s*DRAFT_BOX_BEGIN\b[^>]*-->\s*'
    r'<div style="border:1px solid #eee;[^"]*">\s*'
    r'<strong>[^<]*</strong>)\s*'                     # group 1: sentinel + outer-div + <strong>label
    r'(<div class="lines"[^>]*></div>)',              # group 2: the lines div
    re.DOTALL,
)
POLISHED_LINES_RE = re.compile(
    r'(<!--\s*POLISHED_BOX_BEGIN\b[^>]*-->\s*'
    r'<div style="border:1px solid #eee;[^"]*">\s*'
    r'<strong>[^<]*</strong>)\s*'                     # group 1: sentinel + outer-div + <strong>label
    r'(<div class="lines"[^>]*></div>)',              # group 2: the lines div
    re.DOTALL,
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
    modules_dir = TEMPLATE_DIR / "inserted_script_modules"
    manifest = [line.strip() for line in
                (modules_dir / "_manifest.txt").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")]
    js = "\n".join((modules_dir / fname).read_text(encoding="utf-8") for fname in manifest)
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
    # Round 43 Tier-2 — match any <div> whose class list contains the
    # word "spider-leg", regardless of attribute order or additional
    # classes. Captures the full opening tag minus the trailing
    # whitespace/`>` (which is captured separately so the substitution
    # can insert the contenteditable attribute between them).
    r'(<div\s+[^>]*?\bclass="[^"]*\bspider-leg\b[^"]*")(\s|>)',
)
# Each <div class="spider-container"> gets a small recorder widget at top-right
# of the PARENT card (not inside the spider-container itself, since the spider
# layout is a fixed-aspect grid that would clip absolute children at its top).
# We inject the widget as a SIBLING immediately BEFORE the spider-container
# opening tag — the parent card's `:has(> .voice-recorder-container.vr-inline)`
# CSS rule promotes that card to `position: relative` so the recorder anchors
# to the card's top-right corner.
SPIDER_CONTAINER_OPEN_RE = re.compile(
    # Round 43 Tier-2 — permissive on attribute order + additional classes.
    # Matches any <div> whose class list contains "spider-container".
    r'(<div\s+[^>]*?\bclass="[^"]*\bspider-container\b[^"]*"[^>]*>)',
)


def insertion_4_brainstorming_maps(html: str) -> str:
    """Make spider-legs contenteditable + add a unique recorder per spider-container."""
    # Idempotency check: look for a SPIDER-LEG <div> that already has the
    # contenteditable attribute applied. Round 43 Tier-2 — permissive on
    # attribute order + additional classes so a re-bake correctly detects
    # the prior pass regardless of how attributes ended up being ordered.
    if re.search(r'<div\s+[^>]*?\bclass="[^"]*\bspider-leg\b[^"]*"[^>]*\bcontenteditable\b', html):
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
    # Round 43 Tier-2 — permissive Q-prefix matcher. The original anchor
    # required exactly "Q\d+:" inside an <h3>; harmless author edits like
    # "Q1." (period), "Q 1:" (space), "Question 1:", or "Q.1:" silently
    # skipped every question, leaving the recorder + textarea uninjected.
    # New pattern accepts: Q1: / Q1. / Q1) / Q1- / Q 1: / Q.1: / Question 1:
    # The digit is still captured (group 2) for the recorder id; the rest
    # of the prefix string is captured (group 1) and re-emitted verbatim so
    # visible heading text is unchanged.
    r'(<h3[^>]*>\s*Q(?:uestion)?\.?\s*(\d+)\s*[:\.\)\-]?)(.*?)(<div class="lines"[^>]*></div>)',
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


# ---------- Insertion 7: rotating-password gate ----------
#
# Round 29 (2026-05-03). Gates every Interactive Week_*.html behind a
# shared rotating password. Threat model is casual link-sharing only —
# view-source bypass is acceptable. Hash lives in `_pwhash.json` at the
# bucket root and is fetched at page-load by the inline script (so the
# teacher can rotate the password from the admin console without
# re-running publish.py — the HTML never changes when the password
# rotates).
#
# Template format: scripts/templates/password_gate.html contains two
# delimited sections (HEAD + BODY). HEAD inserts before </head>; BODY
# inserts immediately after the <body ...> opening tag. Substitution
# tokens: __PWHASH_URL__ (bucket-base + "/_pwhash.json") and
# __GATE_TITLE__ (course display name).
HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
# Anchor on `</head>...<body>` together, NOT just `<body`, because the inserted
# CSS contains a documentation comment with the literal text
# `<body class="is-interactive">`. Matching the body-open tag in isolation
# would inject the gate into that CSS comment, invisible to the parser.
# Requiring the immediately-preceding `</head>` guarantees we only match the
# real document body.
HEAD_TO_BODY_RE = re.compile(r"(</head>\s*<body\b[^>]*>)", re.IGNORECASE)

_PWGATE_HEAD_RE = re.compile(
    r"<!--\s*=====\s*PWGATE_HEAD_BEGIN\s*=====\s*-->(.+?)<!--\s*=====\s*PWGATE_HEAD_END\s*=====\s*-->",
    re.DOTALL,
)
_PWGATE_BODY_RE = re.compile(
    r"<!--\s*=====\s*PWGATE_BODY_BEGIN\s*=====\s*-->(.+?)<!--\s*=====\s*PWGATE_BODY_END\s*=====\s*-->",
    re.DOTALL,
)


def _load_password_gate_chunks(pwhash_url: str, gate_title: str) -> tuple[str, str]:
    """Read password_gate.html, split into HEAD + BODY chunks, substitute tokens."""
    template = (TEMPLATE_DIR / "password_gate.html").read_text(encoding="utf-8")

    head_m = _PWGATE_HEAD_RE.search(template)
    body_m = _PWGATE_BODY_RE.search(template)
    if not head_m or not body_m:
        raise SkipFile(
            "password_gate.html is missing PWGATE_HEAD_BEGIN/END or "
            "PWGATE_BODY_BEGIN/END delimiter comments."
        )

    head_chunk = head_m.group(1)
    body_chunk = body_m.group(1)

    for chunk in (head_chunk, body_chunk):
        # Cheap defensive escaping: gate_title is rendered into HTML, never
        # into JS — but keep it harmless even if someone passes "<script>".
        pass

    safe_title = (gate_title.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;"))

    head_chunk = head_chunk.replace("__PWHASH_URL__", pwhash_url)
    head_chunk = head_chunk.replace("__GATE_TITLE__", safe_title)
    body_chunk = body_chunk.replace("__PWHASH_URL__", pwhash_url)
    body_chunk = body_chunk.replace("__GATE_TITLE__", safe_title)

    return head_chunk.strip() + "\n", body_chunk.strip() + "\n"


def insertion_7_password_gate(html: str, bucket_base: str, gate_title: str) -> str:
    """Inject the rotating-password gate's HEAD chunk before </head> and BODY
    chunk immediately after the <body ...> opening tag. Idempotent — skips if
    already inserted (detected by the gate's stable element id)."""
    # Idempotency: the gate adds a uniquely-id'd <style> and <div>. Either
    # presence means we already ran (re-running would double-insert + break
    # the body data-attribute logic).
    if 'id="aischool-pwgate-style"' in html or 'id="aischool-pwgate"' in html:
        return html

    pwhash_url = bucket_base.rstrip("/") + "/_pwhash.json"
    head_chunk, body_chunk = _load_password_gate_chunks(pwhash_url, gate_title)

    # Insert head chunk just before </head>.
    new_html, head_count = HEAD_CLOSE_RE.subn(
        lambda _m: f"\n<!-- pwgate (head) -->\n{head_chunk}</head>",
        html, count=1,
    )
    if head_count != 1:
        raise SkipFile("Could not find </head> closing tag for password gate.")

    # Insert body chunk immediately after the real <body ...> opening tag
    # (the one that follows </head>, not any CSS-comment ghost match).
    new_html, body_count = HEAD_TO_BODY_RE.subn(
        lambda m: m.group(1) + f"\n<!-- pwgate (body) -->\n{body_chunk}",
        new_html, count=1,
    )
    if body_count != 1:
        raise SkipFile("Could not find </head><body> anchor for password gate.")

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
              gate_title: str, minify: bool = True) -> str:
    """Apply the seven insertions and return the new HTML."""
    html = orig_path.read_text(encoding="utf-8")
    html = insertion_1_css(html, minify=minify)
    html = insertion_2_draft_page(html)
    html = insertion_4_brainstorming_maps(html)
    html = insertion_5_q_writing(html)
    html = insertion_3_script(html, endpoint, bucket_base, orig_path.stem,
                              minify=minify)
    html = insertion_6_body_class(html)
    html = insertion_7_password_gate(html, bucket_base, gate_title)
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
    ap.add_argument("--gate-title", default="IELTS Speaking Course",
                    help="Display name shown on the rotating-password gate "
                         "(Round 29). Defaults to IELTS branding; pass e.g. "
                         "'IGCSE Speaking Course' for the other repo.")
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
                                 gate_title=args.gate_title,
                                 minify=args.minify)
            out_path = args.dst / orig_path.name
            _write_text_with_retry(out_path, new_html)
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
        # Round 43 — emit to BOTH stdout AND stderr so the failure is
        # impossible to miss in publish.py's quiet capture-output mode.
        total = len(processed) + len(skipped)
        banner = f"[FAIL] {len(skipped)} of {total} weeks SKIPPED — pipeline must NOT proceed to upload"
        print(banner, file=sys.stderr)
        print(f"Skipped: {len(skipped)}")
        for n, why in skipped:
            line = f"  [skip] {n} -- {why}"
            print(line)
            print(line, file=sys.stderr)
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
