#!/usr/bin/env python3
"""Verify that fanned-out Week_*.html files have ZERO drift from canonical
Week_01 in the blocks that should be byte-identical: cover-overrides CSS,
@font-face rules, .cover-footer, page-numbering CSS.

Why: parse_data.py uses BeautifulSoup to mutate ONLY per-week data nodes
(cover heading, week-tag, vocab tables, cue cards, model answers, Part 3
questions). Everything else flows through the parse/serialize cycle
unchanged. If a future refactor accidentally regenerates a static block,
this verifier catches it before production.

Run manually or wired non-fatally into publish.py (Step 7).

Exit codes:
  0 — all sampled weeks clean
  1 — drift detected (warning-level: publish.py should NOT abort on this)
  2 — canonical or sampled file missing (fatal)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows (cp1252 default chokes on Unicode in publish.py
# step labels). Same idiom as scripts/publish.py.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "canonical" / "pdf-base" / "Week_01.html"
SAMPLE_WEEKS = ["Week_05.html", "Week_22.html", "Week_38.html"]

# Round 56 — Phase 1 path-fallback support. Fanned-out Week_NN.html
# now lives under "IELTS PDF Base HTMLS/HTMLs/" (with fallback to repo
# root for pre-migration state).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import resolve_pdf_base_html_dir  # noqa: E402
PDF_BASE_DIR = resolve_pdf_base_html_dir(REPO)

# (label, compiled-regex). All run with re.DOTALL — patterns may span lines.
# Brace-counting note: @font-face / .cover-footer / .page-number rules don't
# contain nested braces, so a simple `\{[^}]*\}` body match is safe.
PROBES = [
    ("cover-overrides <style> block",
     re.compile(r'<style id="cover-overrides">.*?</style>', re.DOTALL)),
    ("@font-face rules",
     re.compile(r'@font-face\s*\{[^}]*\}', re.DOTALL)),
    (".cover-footer rule",
     re.compile(r'\.cover-footer\s*\{[^}]*\}', re.DOTALL)),
    (".page-number rules",
     re.compile(r'\.page-number[^{]*\{[^}]*\}', re.DOTALL)),
]


def extract_blocks(html: str) -> dict:
    """Return {label: [list of matched strings]} for every PROBE pattern."""
    return {label: pattern.findall(html) for label, pattern in PROBES}


def compare(canonical_blocks: dict, week_path: Path) -> list:
    """Return list of drift descriptions; empty list means no drift."""
    if not week_path.exists():
        return [f"  ERROR: {week_path.name} not found"]
    week_blocks = extract_blocks(week_path.read_text(encoding="utf-8"))
    drifts = []
    for label, _ in PROBES:
        c, w = canonical_blocks[label], week_blocks[label]
        if c == w:
            continue
        drifts.append(
            f"  DRIFT in '{label}': canonical={len(c)} block(s), "
            f"{week_path.name}={len(w)} block(s)"
        )
        # Show first 80 chars of the missing/extra entries (truncate big base64)
        c_set, w_set = set(c), set(w)
        for missing in (c_set - w_set):
            preview = missing[:80].replace("\n", " ")
            drifts.append(f"    canonical-only: {preview}{'...' if len(missing) > 80 else ''}")
        for extra in (w_set - c_set):
            preview = extra[:80].replace("\n", " ")
            drifts.append(f"    {week_path.name}-only: {preview}{'...' if len(extra) > 80 else ''}")
    return drifts


def main() -> int:
    if not CANONICAL.exists():
        print(f"FATAL: canonical not found at {CANONICAL}")
        return 2
    canonical_blocks = extract_blocks(CANONICAL.read_text(encoding="utf-8"))

    print(f"verify_no_drift: checking {len(SAMPLE_WEEKS)} weeks against canonical Week_01")
    for label, _ in PROBES:
        print(f"  {label}: {len(canonical_blocks[label])} match(es) in canonical")
    print()

    any_drift = False
    for week_name in SAMPLE_WEEKS:
        drifts = compare(canonical_blocks, PDF_BASE_DIR / week_name)
        if not drifts:
            print(f"[OK]    {week_name} - 0 drift")
        else:
            any_drift = True
            print(f"[DRIFT] {week_name}")
            for d in drifts:
                print(d)

    print()
    if any_drift:
        print(f"verify_no_drift: drift detected in at least one sampled week")
        return 1
    print(f"verify_no_drift: all {len(SAMPLE_WEEKS)} sampled weeks clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
