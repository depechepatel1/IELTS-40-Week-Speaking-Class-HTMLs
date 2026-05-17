#!/usr/bin/env python3
"""Audit and fix spider-leg cue labels in IELTS Week_*.html files.

Run this AFTER `parse_data.py` to catch cue-label quality issues that the
extractor's heuristics didn't get right.

A "good" cue label is one of the standard IELTS Part 2 cue interrogatives:

    WHO, WHAT, WHEN, WHERE, WHY, HOW, WHICH, WHOSE, WHOM, WHETHER

Plus compound forms separated by `/` (e.g. `HOW/WHERE`) which are
deliberate prompt-style cues.

A "bad" cue is anything else — articles (THE, A, AN), prepositions (TO,
ON, IN, AT, FOR, BY, WITH), pronouns (I, YOU, IT, THIS), connectors
(AND, BUT, OR), or random noise. Bad cues happen when the prompt's
bullet text starts with a low-content word and the real interrogative
appears later (e.g. "On what occasion ..." → real cue is WHAT).

Usage:
    python audit_lesson_labels.py            # dry-run, prints findings
    python audit_lesson_labels.py --apply    # also writes fixes back

Fixes are applied in-place on the matched Week_*.html files.
The script also reports any case it can't auto-fix with high confidence
(rare, but flagged for human review).

The fix algorithm for each bad label:

  1. Read the source bullet text from `master Curiculum.json` for the
     same week/q/position. The HTML's <strong>N. CUE:</strong> label is
     just the first-word extraction of that bullet — we re-extract here
     with a smarter rule: skip "low-content" leading words (articles,
     prepositions, connectors) and use the FIRST INTERROGATIVE we hit.
  2. If no interrogative is found in the bullet, fall back to a
     content-based default (e.g. WHAT for descriptive bullets).
  3. Apply the fix by rewriting the <strong>N. OLD:</strong> tag to
     <strong>N. NEW:</strong>.

The audit is idempotent — running it after a fix produces zero issues.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent
CURRICULUM_PATH = REPO_ROOT / "master Curiculum.json"

# === Allowlist of "good" cue words ==========================================
# These are the legitimate IELTS Part 2 cue interrogatives. Anything outside
# this set is flagged. Compound cues like "HOW/WHERE" pass if every segment
# is in the allowlist.
VALID_CUES = {
    "WHO", "WHAT", "WHEN", "WHERE", "WHY", "HOW", "WHICH", "WHOSE", "WHOM",
    "WHETHER",
}

# Words to skip when re-extracting a cue from a bullet's text. The real cue
# usually follows one of these — e.g. "On what occasion ..." starts with the
# preposition "On" but the cue is WHAT.
LOW_CONTENT_WORDS = {
    # Articles
    "THE", "A", "AN",
    # Prepositions
    "TO", "ON", "IN", "AT", "FOR", "BY", "WITH", "FROM", "OF", "ABOUT",
    "AROUND", "DURING", "AFTER", "BEFORE", "INTO", "ONTO", "OUT", "OVER",
    "UNDER", "THROUGH", "WITHIN",
    # Pronouns / determiners
    "I", "YOU", "IT", "HE", "SHE", "WE", "THEY", "THIS", "THAT", "THESE",
    "THOSE", "MY", "YOUR", "HIS", "HER", "ITS", "OUR", "THEIR",
    # Connectors / conjunctions
    "AND", "BUT", "OR", "SO", "YET",
    # Low-content verbs (rare, but seen)
    "IS", "WAS", "ARE", "WERE", "BE", "BEEN", "BEING", "DO", "DID", "DOES",
}


def is_valid_cue(cue: str) -> bool:
    """A cue is valid if every slash-separated segment is in VALID_CUES."""
    if not cue:
        return False
    parts = cue.upper().split("/")
    return all(p.strip() in VALID_CUES for p in parts)


def extract_cue_from_bullet(bullet_text: str) -> str | None:
    """Re-extract a cue from a bullet's free text using the smarter rule:
    walk past low-content leading words, return the first INTERROGATIVE.

    Special-case: "And explain (why|how|what|...)" returns the
    interrogative (matches parse_data.py's resolution of "And" connectors).
    """
    if not bullet_text:
        return None
    text = bullet_text.strip()

    # "And explain X ..." pattern — the cue is X.
    m = re.match(
        r"and\s+explain\s+(why|how|what|when|where|who|whom|whose|which|whether)\b",
        text, flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()

    # Walk word-by-word: skip low-content words, return first valid cue.
    for raw_word in re.findall(r"[A-Za-z]+", text):
        upper = raw_word.upper()
        if upper in VALID_CUES:
            return upper
        if upper in LOW_CONTENT_WORDS:
            continue
        # Hit a content word that's NOT a cue (noun, verb, adj). Stop —
        # there's no interrogative after this point in normal IELTS prose.
        break
    return None


# === Loaders ================================================================

def load_curriculum() -> dict:
    """Returns {(week:int, qkey:str): [bullet_str, ...]} keyed by week + Q.

    qkey is one of 'q1', 'q2', 'q3'. Each value is a list of up to 4
    bullet strings extracted from the prompt's <p>You should say:<br>X
    <br>Y...</p> structure.
    """
    out: dict[tuple[int, str], list[str]] = {}
    if not CURRICULUM_PATH.exists():
        return out
    data = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    for entry in data:
        wk = entry.get("week")
        if not isinstance(wk, int):
            continue
        l1 = entry.get("lesson_1_part_2", {})
        for qkey in ("q1", "q2", "q3"):
            q = l1.get(qkey, {})
            html = q.get("html", "")
            soup = BeautifulSoup(html, "html.parser")
            prompt_p = next(
                (p for p in soup.find_all("p") if "You should say" in p.get_text()),
                None,
            )
            if not prompt_p:
                continue
            content = prompt_p.decode_contents()
            if "You should say:" not in content:
                continue
            after = content.split("You should say:", 1)[1]
            bullets = [
                BeautifulSoup(b, "html.parser").get_text().strip()
                for b in re.split(r"<br\s*/?>", after)
            ]
            out[(wk, qkey)] = [b for b in bullets if b][:4]
    return out


# === Audit ==================================================================

# A spider-leg label looks like:  <strong>1. WHO:</strong>
# We capture the position number and the cue text.
LABEL_RE = re.compile(r"<strong>([1-4])\. ([^<:]+):</strong>")


def map_index_to_qkey(map_idx: int) -> str:
    """Map index 0/1/2 → q1/q2/q3 (the order spider-containers appear)."""
    return ("q1", "q2", "q3")[map_idx]


def audit_file(
    html_path: Path,
    curriculum: dict,
) -> tuple[str, list[dict]]:
    """Audit one Week_NN.html.

    Returns (possibly-rewritten html, [issue_dict, ...]).
    Each issue_dict carries: week, map_idx, qkey, position, old, new,
    bullet, fix_confidence (high|medium|low), and (if --apply was used by
    the caller) whether the fix was actually written.
    """
    week_match = re.search(r"Week_(\d+)_Lesson_Plan\.html", html_path.name)
    if not week_match:
        return html_path.read_text(encoding="utf-8"), []
    week = int(week_match.group(1))

    html = html_path.read_text(encoding="utf-8")
    issues: list[dict] = []

    # Spider-legs come grouped in <div class="spider-legs"> blocks. There
    # are 3 of those per Week file (one per map). We need to know which
    # block a label sits in to identify q1/q2/q3.
    # Strategy: scan the HTML linearly, count <div class="spider-legs">
    # opens, increment map index. For each <strong>N. CUE:</strong> hit
    # found between the Nth and (N+1)th spider-legs open, attribute it to
    # map index N.

    map_idx = -1
    cursor = 0
    for m in re.finditer(
        r'<div class="spider-legs"[^>]*>|<strong>([1-4])\. ([^<:]+):</strong>',
        html,
    ):
        if m.group(0).startswith("<div"):
            map_idx += 1
            continue
        if map_idx < 0 or map_idx > 2:
            continue
        pos = int(m.group(1))
        old = m.group(2).strip()
        if is_valid_cue(old):
            continue

        qkey = map_index_to_qkey(map_idx)
        bullets = curriculum.get((week, qkey), [])
        bullet = bullets[pos - 1] if pos - 1 < len(bullets) else ""
        new = extract_cue_from_bullet(bullet) or "WHAT"
        confidence = (
            "high" if extract_cue_from_bullet(bullet) is not None
            else "low"  # fallback to WHAT — flag for human review
        )

        issues.append({
            "week": week,
            "map_idx": map_idx,
            "qkey": qkey,
            "position": pos,
            "old": old,
            "new": new,
            "bullet": bullet,
            "confidence": confidence,
            "match_span": m.span(),
        })

    # Build the patched HTML by replacing each issue's match span. Walk
    # back-to-front so earlier indices stay valid.
    patched = html
    for issue in sorted(issues, key=lambda x: x["match_span"][0], reverse=True):
        s, e = issue["match_span"]
        replacement = f'<strong>{issue["position"]}. {issue["new"]}:</strong>'
        patched = patched[:s] + replacement + patched[e:]

    return patched, issues


# === CLI ====================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Write fixes back to the Week_*.html files (default: dry run).")
    ap.add_argument("--root", type=Path, default=REPO_ROOT,
                    help="Repo root (where Week_*.html live).")
    args = ap.parse_args()

    curriculum = load_curriculum()
    if not curriculum:
        print("WARN: master Curiculum.json not loaded — fixes will fall back "
              "to WHAT for every bad cue (low confidence).", file=sys.stderr)

    files = sorted(args.root.glob("Week_*.html"))
    if not files:
        print(f"No Week_*.html files in {args.root}", file=sys.stderr)
        return 2

    summary = {"total_cues": 0, "bad_cues": 0, "fixed_high": 0, "fixed_low": 0}
    all_issues: list[dict] = []

    for path in files:
        # Count total cues (for stats only) — quick regex pass.
        html = path.read_text(encoding="utf-8")
        summary["total_cues"] += len(LABEL_RE.findall(html))

        patched, issues = audit_file(path, curriculum)
        if not issues:
            continue

        all_issues.extend([dict(i, file=path.name) for i in issues])
        summary["bad_cues"] += len(issues)
        for i in issues:
            if i["confidence"] == "high":
                summary["fixed_high"] += 1
            else:
                summary["fixed_low"] += 1

        if args.apply and patched != html:
            path.write_text(patched, encoding="utf-8", newline="\n")

    # Report.
    print("=" * 70)
    print(f"Audited {len(files)} files, {summary['total_cues']} total cues.")
    print(f"Found {summary['bad_cues']} bad cues "
          f"({summary['fixed_high']} high-confidence, "
          f"{summary['fixed_low']} low-confidence fallback to WHAT).")
    if not all_issues:
        print("\nNo issues found.")
        return 0

    print("\nDetails (one row per bad cue):")
    print()
    for i in sorted(all_issues, key=lambda x: (x["week"], x["map_idx"], x["position"])):
        marker = "[OK ]" if i["confidence"] == "high" else "[?? ]"
        print(f"  {marker} Week {i['week']:>2}  {i['qkey']}  pos {i['position']}  "
              f"{i['old']!r:>15} -> {i['new']!r:<6}")
        if i["bullet"]:
            print(f"        bullet: {i['bullet']!r}")
    print()
    if args.apply:
        print(f"Applied {summary['bad_cues']} fixes to disk.")
    else:
        print("(dry run — re-run with --apply to write fixes.)")
        print("[OK ] = high-confidence (interrogative found in bullet)")
        print("[?? ] = low-confidence (no interrogative found; fell back to WHAT — please review)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
