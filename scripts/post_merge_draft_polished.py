#!/usr/bin/env python3
"""Post-merge step: combine Draft + Polished Rewrite boxes into a single
"AI corrected" box on the printable PDF base files (root Week_*.html only).

WHY: Round 18 (2026-05-02) — user wanted the printable last page to show
ONE big writing area labeled "AI corrected" instead of two separate
Draft + Polished Rewrite boxes. But the Interactive layer NEEDS the two
separate `<strong>Draft:</strong>` and `<strong>Polished Rewrite:</strong>`
anchors so make_interactive.py can wrap their `.lines` divs in
`.lines-overlay-host` for the AI-correction overlay.

ASYMMETRIC MERGE — same pattern as IGCSE's post_merge_section_7_8.py:
  - canonical/pdf-base/Week_01.html : separate Draft + Polished (template state;
                                       parse_data.py uses this as the source for
                                       all 40 weeks; make_interactive.py also
                                       needs this structure to inject AI overlay)
  - root Week_*.html (after this script) : combined "AI corrected" (printable)
  - Interactive/Week_*.html             : separate Draft + Polished WITH AI
                                           overlay (because make_interactive.py
                                           ran BEFORE this post-merge step)
  - canonical/pdf-base/Week_01.html SKIPPED to preserve the template state.

ORDER OF OPERATIONS (per scripts/publish.py):
  1. parse_data.py        → fan out canonical → lessons/Week_*.html (separate D+P)
  2. cp lessons/* . + rm  → promote to root (separate D+P)
  3. make_interactive.py  → bake Interactive/Week_*.html (separate D+P + overlay)
  4. build_landing_page.py
  5. upload_to_oss.py
  ===========  THIS SCRIPT  ===========  ← Step 5.5: rewrite root PDF base
  6. check_cert_expiry.py
  7. verify_no_drift.py

Wait — the merge needs to happen BEFORE upload, otherwise the OSS bucket
gets the un-merged PDF base. So this runs as Step 4.5 (between
build_landing_page.py and upload_to_oss.py), or as part of make_interactive.py
post-processing. The publish.py wire-up handles the ordering.

Idempotent: detects if the merge already happened and skips. Safe to
run multiple times.

Exit codes:
  0 : success (all weeks processed or already merged)
  1 : at least one file failed (anchor not found, etc.)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent

# Banner heading on the writing-homework page.
BANNER_OLD = "Writing Homework: Draft &amp; Polished Rewrite"
BANNER_NEW = "Writing Homework: AI corrected"

# The two boxes look like this in canonical (and in fan-out output):
#
#   <div style="border:1px solid #eee; padding:10px; border-radius:6px;
#               background:var(--bg-pastel-green); flex:1; display:flex;
#               flex-direction:column; box-shadow: 0 15px 30px ...;
#               border: none !important;">
#   <strong>Draft:</strong>
#   <div class="lines" style="flex-grow:1; height:auto;"></div>
#   </div>
#   <div style="border:1px solid #eee; ...">
#   <strong>Polished Rewrite:</strong>
#   <div class="lines" ...></div>
#   </div>
#
# The combined replacement keeps the same outer styling but uses ONE box
# with one `.lines` div (which fills the flex space => bigger writing area).
DRAFT_POLISHED_RE = re.compile(
    # Round 43 (2026-05-12) — allow optional <!-- … --> comments BEFORE
    # the Draft block AND between Draft and Polished blocks. This is so
    # the sentinel anchors DRAFT_BOX_BEGIN and POLISHED_BOX_BEGIN
    # (added in canonical/pdf-base/Week_01.html to harden make_interactive
    # against title-text edits) don't break this post-merge match.
    r'(?:<!--[^>]*-->\s*)?'                           # optional DRAFT_BOX_BEGIN
    r'<div style="border:1px solid #eee;[^"]*">\s*'
    r'<strong>Draft:</strong>\s*'
    r'<div class="lines"[^>]*></div>\s*'
    r'</div>\s*'
    r'(?:<!--[^>]*-->\s*)?'                           # optional POLISHED_BOX_BEGIN
    r'<div style="border:1px solid #eee;[^"]*">\s*'
    r'<strong>Polished Rewrite:</strong>\s*'
    r'<div class="lines"[^>]*></div>\s*'
    r'</div>',
    re.DOTALL,
)

COMBINED_BOX = (
    '<div style="border:1px solid #eee; padding:10px; border-radius:6px; '
    'background:var(--bg-pastel-green); flex:1; display:flex; '
    'flex-direction:column; box-shadow: 0 15px 30px rgba(0,0,0,0.2) !important; '
    'border: none !important;">\n'
    '<strong>AI corrected:</strong>\n'
    '<div class="lines" style="flex-grow:1; height:auto;"></div>\n'
    '</div>'
)


def merge_one(html: str) -> tuple[str, str]:
    """Returns (new_html, status). status is 'ok', 'already-merged', or 'no-anchor'."""
    if BANNER_NEW in html and BANNER_OLD not in html:
        return html, "already-merged"
    new_html = html
    new_html = new_html.replace(BANNER_OLD, BANNER_NEW, 1)
    new_html, count = DRAFT_POLISHED_RE.subn(COMBINED_BOX, new_html, count=1)
    if count != 1:
        return html, "no-anchor"
    return new_html, "ok"


def main() -> int:
    week_files = sorted(REPO.glob("Week_*.html"))
    if not week_files:
        print(f"FATAL: no Week_*.html files at {REPO}")
        return 1

    ok = skipped = failed = 0
    for wf in week_files:
        original = wf.read_text(encoding="utf-8")
        new, status = merge_one(original)
        if status == "ok":
            wf.write_text(new, encoding="utf-8")
            ok += 1
        elif status == "already-merged":
            skipped += 1
        else:  # no-anchor
            failed += 1
            print(f"  [WARN] {wf.name}: Draft + Polished anchor pattern not found")

    total = ok + skipped + failed
    print(
        f"post_merge_draft_polished: {ok} merged, {skipped} already-merged, "
        f"{failed} failed (of {total} total)"
    )
    if failed:
        print("Some files could not be merged. Check the WARN lines above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
