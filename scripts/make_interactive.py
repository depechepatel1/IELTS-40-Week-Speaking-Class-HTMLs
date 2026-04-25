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


def transform(orig_path: Path, endpoint: str, bucket_base: str) -> str:
    """Apply the three insertions and return the new HTML."""
    raise NotImplementedError("filled in by the next tasks")


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
        print(f"  ✓ {n}")
    if skipped:
        print(f"Skipped: {len(skipped)}")
        for n, why in skipped:
            print(f"  ✗ {n} — {why}")
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
