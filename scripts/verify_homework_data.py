#!/usr/bin/env python3
"""Validate homework_plan.json against the layout's structural assumptions.

The IELTS homework page is laid out for EXACTLY 5 vocab-review items + 5
grammar-clinic items per week. If a week's data has a different count,
the page either has empty rows (looks weird) or the cards grow taller and
push the upside-down answer-key footer off the bottom of the A4 page
(Week 2 had this bug 2026-05-03 — a leftover editor draft entry).

This script catches such drift BEFORE fan-out, so we don't ship broken
weeks to production.

Also flags suspicious draft text like "Wait, ...", "TODO", "FIXME",
"placeholder", etc. — leftover editor notes that should never reach
students.

Run manually or wired into publish.py as Step 0 (preflight before
parse_data.py runs).

Exit codes:
  0 — all weeks clean
  1 — at least one issue (warning; publish.py runs anyway)
  2 — homework_plan.json missing or unparseable (fatal)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
HOMEWORK_PATH = REPO / "homework_plan.json"

EXPECTED_VOCAB_COUNT = 5      # the homework page has exactly 5 vocab-table rows
EXPECTED_GRAMMAR_COUNT = 5    # the grammar-clinic box fits 5 sentences
MAX_WRITING_TASK_CHARS = 100  # h3 wraps to 2 lines beyond this — pushes layout
MAX_ANSWER_KEY_CHARS = 250    # rotated footer wraps if longer

DRAFT_RE = re.compile(
    r"\b(wait|todo|fixme|hmm|tbd|placeholder|draft|note:)\b",
    re.IGNORECASE,
)


def issues_for_week(week: dict) -> list[str]:
    n = week.get("week") or week.get("Week") or "?"
    out = []

    vocab = week.get("vocab_review") or []
    grammar = week.get("grammar_clinic") or []
    writing = week.get("writing_task") or ""
    answer = week.get("answer_key") or ""

    if len(vocab) != EXPECTED_VOCAB_COUNT:
        out.append(
            f"Week {n}: vocab_review has {len(vocab)} items "
            f"(layout expects {EXPECTED_VOCAB_COUNT})"
        )
    if len(grammar) != EXPECTED_GRAMMAR_COUNT:
        out.append(
            f"Week {n}: grammar_clinic has {len(grammar)} items "
            f"(layout expects {EXPECTED_GRAMMAR_COUNT}) — "
            f"extra items push the answer-key footer off the page"
        )

    # Cross-check: answer_key item count must match grammar_clinic + vocab_review.
    # (Bug 2026-05-03: Week 2 had grammar_clinic cleaned 6→5 but answer_key kept
    # the orphan 6th item, leaving the rotated footer text longer than expected
    # and pushing layout. Force the two fields to stay in sync.)
    parts = answer.split("|") if isinstance(answer, str) else [""]
    vocab_part = parts[0] if parts else ""
    grammar_part = parts[1] if len(parts) > 1 else ""
    ak_vocab = len(re.findall(r"\b\d+\.\s", vocab_part))
    ak_grammar = len(re.findall(r"\b\d+\.\s", grammar_part))
    if ak_vocab != len(vocab):
        out.append(
            f"Week {n}: answer_key vocab section has {ak_vocab} numbered items, "
            f"but vocab_review has {len(vocab)} — fields out of sync"
        )
    if ak_grammar != len(grammar):
        out.append(
            f"Week {n}: answer_key grammar section has {ak_grammar} numbered items, "
            f"but grammar_clinic has {len(grammar)} — fields out of sync "
            f"(extra answer items make the rotated footer wrap and push layout)"
        )

    # Draft-text detection across all string fields
    def scan(label: str, text: str) -> None:
        if isinstance(text, str) and DRAFT_RE.search(text):
            out.append(f"Week {n}: {label} contains draft note — {text!r}")

    for i, it in enumerate(grammar):
        scan(f"grammar_clinic #{i+1}", it.get("error", ""))
    for i, it in enumerate(vocab):
        for k in ("word", "synonym", "option"):
            scan(f"vocab_review #{i+1}.{k}", str(it.get(k, "")))
    scan("writing_task", writing)
    scan("answer_key", answer)

    # Length sanity checks
    if len(writing) > MAX_WRITING_TASK_CHARS:
        out.append(
            f"Week {n}: writing_task is {len(writing)} chars "
            f"(>{MAX_WRITING_TASK_CHARS}) — h3 may wrap to 2 lines"
        )
    if len(answer) > MAX_ANSWER_KEY_CHARS:
        out.append(
            f"Week {n}: answer_key is {len(answer)} chars "
            f"(>{MAX_ANSWER_KEY_CHARS}) — footer may wrap and push off page"
        )

    return out


def main() -> int:
    if not HOMEWORK_PATH.exists():
        print(f"FATAL: {HOMEWORK_PATH} not found")
        return 2
    try:
        data = json.loads(HOMEWORK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FATAL: {HOMEWORK_PATH.name} is not valid JSON: {e}")
        return 2

    if not isinstance(data, list):
        print(f"FATAL: {HOMEWORK_PATH.name} should be a JSON array of week objects")
        return 2

    print(
        f"verify_homework_data: scanning {len(data)} week entries for layout-"
        f"safe shape (vocab=={EXPECTED_VOCAB_COUNT}, grammar=={EXPECTED_GRAMMAR_COUNT}, "
        f"no draft prefixes, length sanity)"
    )
    print()

    all_issues: list[str] = []
    for w in data:
        all_issues.extend(issues_for_week(w))

    if not all_issues:
        print(f"[OK] all {len(data)} weeks pass shape + content checks")
        return 0

    for msg in all_issues:
        print(f"[WARN] {msg}")

    print(
        f"\nverify_homework_data: {len(all_issues)} issue(s) across "
        f"{len(data)} weeks — fix in homework_plan.json then re-run."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
