#!/usr/bin/env python3
"""Phase C of Plan E — merge PDF-extracted Part 2 content into the existing
`master Curiculum.json`, preserving the existing `lesson_2_part_3` content
(which the user said was NOT changed in the Mar 30 PDF set).

What this does:
    For each week (1-40):
      - Take `theme`, `topic`, and `lesson_1_part_2` from the extracted
        per-week JSON (from extract_pdfs_to_curriculum.py).
      - Take `lesson_2_part_3` from the existing `master Curiculum.json`.
      - Merge into a new master Curiculum.json that combines BOTH.

Safety:
    - Backs up the current master Curiculum.json before writing.
    - Backup name includes a timestamp so re-runs don't clobber backups.
    - If a week's extraction file is missing, keeps that week's existing
      `lesson_1_part_2` (does NOT blank it out).
    - --dry-run mode prints diff without writing.

Usage:
    python merge_pdf_curriculum.py            # writes the merged file
    python merge_pdf_curriculum.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EXISTING_MASTER = REPO_ROOT / "master Curiculum.json"
PER_WEEK_DIR = REPO_ROOT / ".recovered_curriculum" / "per_week"


def short_q1_repr(week: dict) -> str:
    """Compact summary of a week's q1/q2/q3 cue cards for diff display."""
    p2 = week.get("lesson_1_part_2", {})
    out = []
    for k in ("q1", "q2", "q3"):
        h = p2.get(k, {}).get("html", "") or ""
        # Pull the first <p> (cue card) text, truncated.
        prompt = h.split("</p>", 1)[0].lstrip("<p>").split("You should say:", 1)[0].strip()
        out.append(f"{k}: {prompt[:65]}")
    return " | ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print diff without writing master Curiculum.json.")
    args = ap.parse_args()

    if not EXISTING_MASTER.exists():
        print(f"ERROR: existing curriculum not found: {EXISTING_MASTER}", file=sys.stderr)
        return 2
    if not PER_WEEK_DIR.is_dir():
        print(f"ERROR: per-week dir not found: {PER_WEEK_DIR}", file=sys.stderr)
        return 2

    with EXISTING_MASTER.open("r", encoding="utf-8") as f:
        existing = json.load(f)

    # Index existing by week number
    existing_by_week = {w["week"]: w for w in existing}

    merged = []
    used_extracted = []
    fell_back = []

    for week_num in range(1, 41):
        existing_week = existing_by_week.get(week_num)
        if not existing_week:
            print(f"  Week {week_num}: NOT in existing master — skipping", file=sys.stderr)
            continue

        # Try to load extracted per-week file.
        extracted_path = PER_WEEK_DIR / f"week_{week_num:02d}.json"
        if extracted_path.exists():
            with extracted_path.open("r", encoding="utf-8") as f:
                extracted = json.load(f)
            new_week = {
                "week": week_num,
                "theme": extracted.get("theme", existing_week["theme"]),
                "topic": extracted.get("topic", existing_week["topic"]),
                "lesson_1_part_2": extracted["lesson_1_part_2"],
                "lesson_2_part_3": existing_week.get("lesson_2_part_3", {}),
            }
            used_extracted.append(week_num)
        else:
            # Fall back to existing — extraction failed for this week.
            new_week = dict(existing_week)
            fell_back.append(week_num)

        merged.append(new_week)

    # Print summary + per-week diff snapshot.
    print(f"Used extracted for {len(used_extracted)} weeks: {used_extracted}")
    print(f"Fell back to existing for {len(fell_back)} weeks: {fell_back}")
    print()
    print("=== Per-week BEFORE / AFTER (cue card prompts only) ===")
    for week_num in used_extracted[:5] + ([] if len(used_extracted) <= 10 else used_extracted[-3:]):
        before = existing_by_week[week_num]
        after = next(w for w in merged if w["week"] == week_num)
        print(f"\nWeek {week_num} BEFORE: {short_q1_repr(before)}")
        print(f"Week {week_num} AFTER:  {short_q1_repr(after)}")

    if args.dry_run:
        print("\n--dry-run: NOT writing master Curiculum.json. Re-run without --dry-run to apply.")
        return 0

    # Backup existing.
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPO_ROOT / f"master Curiculum.json.backup_pre_pdf_sync_{ts}"
    shutil.copy2(EXISTING_MASTER, backup)
    print(f"\nBackup created: {backup}")

    with EXISTING_MASTER.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Wrote merged curriculum to: {EXISTING_MASTER}")
    print(f"  ({len(merged)} weeks total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
