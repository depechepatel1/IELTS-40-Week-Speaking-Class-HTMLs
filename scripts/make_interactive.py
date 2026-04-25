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

The script applies three insertions to each `Week_*_Lesson_Plan.html`:
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

SENTINEL = "<!-- AI-INTERACTIVE-V1 -->"
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
FONT_DIR = SCRIPT_DIR / "fonts"


class SkipFile(RuntimeError):
    """Raised when a single file's pattern-match fails — caller logs and continues."""


def _files_to_process(in_path: Path) -> Iterable[Path]:
    if in_path.is_file():
        if re.fullmatch(r"Week_\d+_Lesson_Plan\.html", in_path.name):
            yield in_path
        return
    for p in sorted(in_path.glob("Week_*_Lesson_Plan.html")):
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


def _load_inserted_css() -> str:
    css = (TEMPLATE_DIR / "inserted_css.css").read_text(encoding="utf-8")
    fonts = _load_fonts()
    for token, b64 in fonts.items():
        if token not in css:
            raise SkipFile(f"CSS template missing placeholder {token}.")
        css = css.replace(token, b64, 1)
    return css


def insertion_1_css(html: str) -> str:
    css = _load_inserted_css()
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
    """Wrap the original `.lines` inside `.lines-overlay-host` along with overlay UI.

    Per spec §6.2: the original `<div class="lines">` is KEPT in HTML so the
    file structure remains regular and is hidden via `.draft-page .lines
    { display: none; }` in the inserted CSS. The new wrapper is the
    positioning/scrolling host for the overlay textarea/markup/output.
    """
    draft_overlay = _load_overlay("draft_section_overlay.html")
    polished_overlay = _load_overlay("polished_section_overlay.html")

    def wrap_draft(m: re.Match) -> str:
        label, lines_div = m.group(1), m.group(2)
        return f'{label}\n<div class="lines-overlay-host">\n  {lines_div}\n  {draft_overlay}\n</div>'

    def wrap_polished(m: re.Match) -> str:
        label, lines_div = m.group(1), m.group(2)
        return f'{label}\n<div class="lines-overlay-host">\n  {lines_div}\n  {polished_overlay}\n</div>'

    new_html, c1 = DRAFT_LINES_RE.subn(wrap_draft, html, count=1)
    if c1 != 1:
        raise SkipFile("Could not find `<strong>Draft:</strong>` + .lines anchor.")
    new_html, c2 = POLISHED_LINES_RE.subn(wrap_polished, new_html, count=1)
    if c2 != 1:
        raise SkipFile("Could not find `<strong>Polished Rewrite:</strong>` + .lines anchor.")
    return new_html


# ---------- Insertion 3: <script> block before </body> ----------

BODY_CLOSE_RE = re.compile(r"</body>", re.IGNORECASE)


def insertion_3_script(html: str, endpoint: str, bucket_base: str, lesson_key: str) -> str:
    js = (TEMPLATE_DIR / "inserted_script.js").read_text(encoding="utf-8")
    pron_url = bucket_base.rstrip("/") + "/pronunciations.json"
    js = js.replace("__AI_ENDPOINT__", endpoint.rstrip("/"))
    js = js.replace("__PRONUNCIATIONS_URL__", pron_url)
    js = js.replace("__LESSON_KEY__", lesson_key)
    block = f"\n<script>\n/* {SENTINEL} SCRIPT */\n{js}\n</script>\n"
    # Use a callable replacement so Python doesn't interpret JS regex escapes
    # (e.g. `/\s+/` inside the script) as back-references.
    replacement = block + "</body>"
    new_html, count = BODY_CLOSE_RE.subn(lambda _m: replacement, html, count=1)
    if count != 1:
        raise SkipFile("Could not find </body> closing tag.")
    return new_html


# ---------- Compose ----------

def transform(orig_path: Path, endpoint: str, bucket_base: str) -> str:
    """Apply the three insertions and return the new HTML."""
    html = orig_path.read_text(encoding="utf-8")
    html = insertion_1_css(html)
    html = insertion_2_draft_page(html)
    html = insertion_3_script(html, endpoint, bucket_base, orig_path.stem)
    return html


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, type=Path,
                    help="Folder containing originals OR a single Week_*_Lesson_Plan.html")
    ap.add_argument("--out", dest="dst", required=True, type=Path,
                    help="Output folder for interactive files")
    ap.add_argument("--endpoint", required=True,
                    help="Function Compute URL (e.g. https://abc.fcapp.run)")
    ap.add_argument("--bucket-base", required=True,
                    help="Public bucket URL prefix where pronunciations.json lives")
    args = ap.parse_args()

    if not args.src.exists():
        print(f"error: --in path does not exist: {args.src}", file=sys.stderr)
        return 2
    args.dst.mkdir(parents=True, exist_ok=True)

    processed: list[str] = []
    skipped: list[tuple[str, str]] = []

    for orig_path in _files_to_process(args.src):
        try:
            new_html = transform(orig_path, args.endpoint, args.bucket_base)
            out_path = args.dst / orig_path.name
            out_path.write_text(new_html, encoding="utf-8", newline="\n")
            processed.append(orig_path.name)
        except SkipFile as e:
            skipped.append((orig_path.name, str(e)))
        except Exception as e:  # unexpected — fail loudly with file context
            print(f"FATAL while processing {orig_path.name}: {e}", file=sys.stderr)
            raise

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
