#!/usr/bin/env python3
"""Migrate print-relevant CSS from the interactive overlay layer into each
base Week_*_Lesson_Plan.html so that printed PDFs (rendered from base files
via Playwright in batch_convert_pdf.py) inherit the same horizontal-bullet
+ tall-Q6 layout the digital interactive HTMLs already show.

Two changes per file:

  1. Inject a `/* PRINT-LAYOUT-V1 */` block of CSS rules into the existing
     `<style>` block, immediately after the existing `.scaffold-text`
     declarations (~line 50). Rules added:
       - `.card.compact ul.scaffold-text` -> horizontal flex bullets
       - `.card.compact ul.scaffold-text li::before` -> custom bullet glyph
       - `.card.compact.q-tall { flex-basis: 20px !important; }` -> Q6 height bump

  2. Append ` q-tall` to the class attribute of the Q6 card div, located
     by the `<!-- Q6 -->` HTML comment immediately preceding
     `<div class="card compact" ...>`. Idempotent: skips if `q-tall` is
     already present in the class list.

Usage:
    python scripts/migrate_print_css.py            # dry run, prints diff
    python scripts/migrate_print_css.py --apply    # writes changes back

The script is idempotent: running with --apply twice produces no further
changes (PRINT-LAYOUT-V1 sentinel guards Step 1, `q-tall` membership check
guards Step 2).

NOTE: This only modifies BASE Week_*_Lesson_Plan.html files in the repo
ROOT. Files inside Interactive/ are not touched (those are regenerated
fresh by make_interactive.py each run).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- Step 1: print-layout CSS block to inject into <style> --------------------

SENTINEL = "/* PRINT-LAYOUT-V2 */"
# Older sentinels we know how to upgrade. When found, the OLD block (sentinel
# through the next CSS comment header `/* ===` or a heuristic boundary) is
# stripped and the new block is reinjected. This keeps the migration
# idempotent across schema bumps.
LEGACY_SENTINELS = ["/* PRINT-LAYOUT-V1 */"]

PRINT_LAYOUT_CSS = f"""
    {SENTINEL}
    /* Horizontal scaffold-text bullets in Q1-Q6 writing-box cards. Q1+Q2
       use class="card", Q3-Q6 use class="card compact" — both share this
       rule because all 6 boxes have `<ul class="scaffold-text">` cue lists
       inside them. Across the 40-week course, scaffold-text only appears
       inside Q-boxes (audited 2026-04-28), so `.card ul.scaffold-text`
       is selective enough without needing per-Q-id overrides.
       Saves vertical space on both PRINT and digital. */
    .card ul.scaffold-text {{
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 0 14px;
        margin: 0 0 4px 0;
        padding: 0;
        list-style: none;
    }}
    .card ul.scaffold-text li {{
        margin: 0;
        padding: 0;
        display: inline-flex;
        align-items: center;
        line-height: 1.2;
    }}
    .card ul.scaffold-text li::before {{
        content: "\\2022";
        color: #999;
        margin-right: 4px;
    }}
    /* Q6 +20px taller — gives the bottom card a 20px head-start over Q4/Q5
       in the equal-grow flex distribution. Triggered by the `q-tall`
       marker class on the Q6 card div (added by migrate_print_css.py). */
    .card.compact.q-tall {{
        flex-basis: 20px !important;
    }}
"""

# Anchor: the existing scaffold-text rule block ends with this exact line.
SCAFFOLD_ANCHOR_RE = re.compile(
    r"(\.scaffold-text li \{ margin-bottom: 1px; \})",
)

# --- Step 2: q-tall marker on Q6 card div ------------------------------------

# Match: `<!-- Q6 -->` followed by some whitespace, then the opening
# `<div class="card compact" ...>` tag. Capture the class attribute value
# so we can rewrite it.
Q6_DIV_RE = re.compile(
    r'(<!-- Q6 -->\s*<div class=")(card compact)("[^>]*>)',
    re.MULTILINE,
)


def _strip_legacy_block(html: str, legacy_sentinel: str) -> str:
    """Remove a legacy PRINT-LAYOUT-V<n> block. The block starts at the
    sentinel comment and extends until the next top-level CSS comment block
    (matching `/* ===` which is the convention for new sections in our
    inserted styles) OR the closing of the surrounding rule context. We
    use a conservative heuristic: capture from the sentinel through the
    closing `}` of the LAST rule that immediately follows it without a
    blank-line break. Falls back to a simple pattern-known-to-be-emitted
    by the previous version of this script."""
    # The previous V1 block had a fixed shape — strip it via that shape.
    # If the shape changes again later, add a new branch here.
    legacy_v1_re = re.compile(
        re.escape(legacy_sentinel)
        + r"[\s\S]*?\.card\.compact\.q-tall\s*\{\s*flex-basis:\s*20px\s*!important;\s*\}\s*",
        re.MULTILINE,
    )
    new_html, n = legacy_v1_re.subn("", html, count=1)
    return new_html


def migrate(html: str) -> tuple[str, dict[str, bool]]:
    """Return (new_html, {'css_injected': bool, 'q_tall_added': bool, 'upgraded_from_v1': bool})."""
    flags = {"css_injected": False, "q_tall_added": False, "upgraded_from_v1": False}

    # Step 1 — inject CSS block (or upgrade from legacy)
    if SENTINEL in html:
        # Already on current version.
        pass
    else:
        # Strip any legacy version first so we don't end up with two blocks.
        for legacy in LEGACY_SENTINELS:
            if legacy in html:
                stripped = _strip_legacy_block(html, legacy)
                if stripped != html:
                    html = stripped
                    flags["upgraded_from_v1"] = True
        new_html, n = SCAFFOLD_ANCHOR_RE.subn(
            lambda m: m.group(1) + PRINT_LAYOUT_CSS,
            html,
            count=1,
        )
        if n == 1:
            html = new_html
            flags["css_injected"] = True
        # If the anchor wasn't found, leave html unchanged — caller logs.

    # Step 2 — add q-tall to Q6 card class list
    def add_q_tall(m: re.Match) -> str:
        opener, classes, rest = m.group(1), m.group(2), m.group(3)
        if "q-tall" in classes.split():
            return m.group(0)  # already migrated
        flags["q_tall_added"] = True
        return f"{opener}{classes} q-tall{rest}"

    html = Q6_DIV_RE.sub(add_q_tall, html, count=1)

    return html, flags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Write changes back to disk (default: dry run).")
    args = ap.parse_args()

    files = sorted(REPO_ROOT.glob("Week_*_Lesson_Plan.html"))
    if not files:
        print(f"No Week_*_Lesson_Plan.html files in {REPO_ROOT}",
              file=sys.stderr)
        return 2

    summary = {"total": 0, "css_injected": 0, "q_tall_added": 0,
               "upgraded": 0, "already_migrated": 0, "anchor_missing": 0}
    for path in files:
        original = path.read_text(encoding="utf-8")
        new_html, flags = migrate(original)
        summary["total"] += 1
        if flags["css_injected"]:
            summary["css_injected"] += 1
        if flags["q_tall_added"]:
            summary["q_tall_added"] += 1
        if flags["upgraded_from_v1"]:
            summary["upgraded"] += 1
        if (not flags["css_injected"] and not flags["q_tall_added"]
                and not flags["upgraded_from_v1"]):
            if SENTINEL in original and "q-tall" in original:
                summary["already_migrated"] += 1
            else:
                summary["anchor_missing"] += 1
                print(f"  [warn] {path.name}: no anchor matched "
                      f"(scaffold-text rule or <!-- Q6 --> not found)")
                continue

        if new_html != original and args.apply:
            path.write_text(new_html, encoding="utf-8", newline="\n")
        marker = "[apply]" if args.apply and new_html != original else "[dry] " if new_html != original else "[skip]"
        print(f"  {marker} {path.name}  "
              f"css={'+' if flags['css_injected'] else '.'} "
              f"q6={'+' if flags['q_tall_added'] else '.'} "
              f"upg={'V1->V2' if flags['upgraded_from_v1'] else '----'}")

    print(f"\nProcessed {summary['total']} files: "
          f"{summary['css_injected']} got CSS, "
          f"{summary['q_tall_added']} got q-tall, "
          f"{summary['upgraded']} upgraded V1->V2, "
          f"{summary['already_migrated']} already on current version, "
          f"{summary['anchor_missing']} missing anchors.")
    if not args.apply:
        print("(dry run — re-run with --apply to write changes)")
    return 0 if summary["anchor_missing"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
