#!/usr/bin/env python3
"""HTML Consistency Audit — verify design + widget consistency across the
IGCSE and IELTS lesson-plan HTMLs.

Two-axis check:

  Axis 1 (mirror): scripts/templates/inserted_css.css and every file in
  scripts/templates/inserted_script_modules/ should be BYTE-IDENTICAL
  between the IGCSE and IELTS repos. Drift here means a recent edit on
  one side wasn't `cp`'d to the other.

  Axis 2 (marker coverage): every Week_NN.html — PDF-base AND
  Interactive, both repos — should carry the LATEST typography +
  widget design markers. Drift here means the file is stale and needs
  publish.py to re-fan-out the source.

The script is read-only and side-effect-free; it just prints a report
and exits with code 0 (clean) or 1 (drift detected).

  Run:  python scripts/audit_html_consistency.py
        python scripts/audit_html_consistency.py --json
        python scripts/audit_html_consistency.py --strict   # PDF base too

`--strict` includes PDF-base HTMLs in the marker-coverage check. By
default, PDF-base HTMLs are only checked against typography markers
(widget upgrades are interactive-only and intentionally don't apply to
print output).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


# ============================================================
# Repo paths
# ============================================================

IGCSE_REPO = Path(
    "C:/Users/depec/OneDrive/Desktop/IGCSE Github Files"
)
IELTS_REPO = Path(
    "C:/Users/depec/OneDrive/Desktop/IELTS 40 Week Speaking Class HTMLs"
    "/IELTS-40-Week-Speaking-Class-HTMLs"
)


# ============================================================
# Mirror files: byte-identical between repos (per CLAUDE.md
# mirror-invariants table). The script discovers per-module
# files dynamically by listing inserted_script_modules/.
# ============================================================

MIRRORED_PATHS_STATIC = [
    "scripts/templates/inserted_css.css",
    "scripts/templates/password_gate.html",
    "scripts/templates/voice_recorder_widget_inline.html",
]


def discover_module_files() -> list[str]:
    """Return relative paths of every file in
    scripts/templates/inserted_script_modules/ (taking the IGCSE
    listing as the source of truth)."""
    modules_dir = IGCSE_REPO / "scripts" / "templates" / "inserted_script_modules"
    if not modules_dir.is_dir():
        return []
    return sorted(
        f"scripts/templates/inserted_script_modules/{p.name}"
        for p in modules_dir.iterdir()
        if p.is_file()
    )


# ============================================================
# Marker definitions
#
# Each marker is a distinctive substring whose PRESENCE in the
# rendered HTML proves a given polish landed. Markers are
# substring matches (not regex) — flexible enough to survive
# minifier whitespace and quote-style choices.
# ============================================================

# Typography pass — applies to BOTH PDF-base and Interactive after
# the next publish (PDF-base requires source edits in template.html /
# canonical/pdf-base/Week_01.html; Interactive picks them up via
# inserted_css.css automatically).
TYPOGRAPHY_MARKERS = {
    "type-scale token --ts-h3":   "--ts-h3",
    "type-scale token --ts-body": "--ts-body",
    "type-scale token --ts-caption": "--ts-caption",
    "Lato body font in stack":    "'Lato'",
    "CJK font scoped (Noto Sans SC)": "Noto Sans SC",
}

# Widget upgrades — INTERACTIVE ONLY. The Bug 3 video, recorder logic,
# karaoke pulse, premium gradients, q-prompt-row flex, and per-row
# auto-init all live in inserted_script_modules / inserted_css.css and
# only land on Interactive HTMLs.
WIDGET_JS_MARKERS = {
    "Batch B vrStopPlayback fn":          "vrStopPlayback",
    "Batch C #3 _syncAccentButtons":      "_syncAccentButtons",
    "Typography pass enhanceQPrompts":    "enhanceQPrompts",
    "Density pass q-prompt-row wrapper":  "q-prompt-row",
}

WIDGET_CSS_MARKERS = {
    "Batch E v2 premium replay green":  "#34d399",   # replay button base gradient stop
    "Batch D karaoke pulse keyframes":  "tts-word-pulse",
    "Density pass q-prompt-row CSS":    ".q-prompt-row",
}

# Bug 3 page-bottom videos — IELTS Interactive ONLY. IGCSE side was
# dismissed by the user.
BUG3_IELTS_MARKERS = {
    "Bug 3 video1.mp4 reference":      "videos/video1.mp4",
    "Bug 3 video2.mp4 reference":      "videos/video2.mp4",
    "Bug 3 video3.mp4 reference":      "videos/video3.mp4",
    "Bug 3 .page-bottom-video class":  "page-bottom-video",
}

# Section 7+8 / Draft+Polished asymmetric merge state.
#
# PDF-base output (root Week_*.html) should have these MERGED into a
# single writing area. Interactive output keeps them separate so
# make_interactive.py can inject the AI-correction overlay into the
# polished half.
#
# IGCSE: merged label is "Section 7 &amp; 8" (one combined .floating-
# window block); unmerged shows separate <div class="section-badge">
# Section 7</div> and <div class="section-badge">Section 8</div>.
# IELTS: merged label is "Writing Homework: AI corrected"; unmerged
# shows "Writing Homework: Draft &amp; Polished Rewrite" + separate
# <strong>Draft:</strong> and <strong>Polished Rewrite:</strong>
# anchors.
IGCSE_PDF_MERGE_MARKERS = {
    "Sec 7 & 8 merged badge (PDF should have this)":
        "Section 7 &amp; 8",
}
IGCSE_INT_SEPARATE_MARKERS = {
    "Sec 7 badge present (Interactive should have this)":
        '<div class="section-badge">Section 7</div>',
    "Sec 8 badge present (Interactive should have this)":
        '<div class="section-badge">Section 8</div>',
}
IELTS_PDF_MERGE_MARKERS = {
    "Writing Homework: AI corrected banner (PDF should have this)":
        "Writing Homework: AI corrected",
    "&lt;strong&gt;AI corrected:&lt;/strong&gt; single anchor":
        "<strong>AI corrected:</strong>",
}


# ============================================================
# Helpers
# ============================================================

def sha256_short(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def collect_mirror_status() -> dict:
    """Compare every mirrored file's SHA-256 between the two repos."""
    out = {}
    for rel in MIRRORED_PATHS_STATIC + discover_module_files():
        a = IGCSE_REPO / rel
        b = IELTS_REPO / rel
        if not a.exists() or not b.exists():
            out[rel] = {
                "status": "missing",
                "igcse_exists": a.exists(),
                "ielts_exists": b.exists(),
            }
            continue
        ha = sha256_short(a)
        hb = sha256_short(b)
        out[rel] = {
            "status": "match" if ha == hb else "drift",
            "igcse": ha,
            "ielts": hb,
        }
    return out


def _resolve_dir(repo: Path, new_subpath: str, old_subpath: str) -> Path:
    """Round 56 — Phase 1 path-fallback. Match the resolver pattern in
    scripts/_paths.py without importing it (audit script lives in both
    repos and has no setup dependency)."""
    new = repo / new_subpath
    return new if new.is_dir() else (repo / old_subpath)


def collect_htmls() -> list[tuple[Path, str, str]]:
    """Return (path, kind, label) tuples for every HTML to audit.

    kind is 'pdf-base' or 'interactive'.
    label is a human-readable group name for the report.

    Round 56 — paths resolve to the new five-folder structure if Phase 2
    file moves have run; otherwise fall back to the old root/Interactive
    layout so the audit works during the transition.
    """
    out: list[tuple[Path, str, str]] = []

    # Per-week PDF-base HTMLs — resolved (new folder if migrated, else root)
    igcse_pdf = _resolve_dir(IGCSE_REPO, "IGCSE PDF Base HTMLS/HTMLs", ".")
    ielts_pdf = _resolve_dir(IELTS_REPO, "IELTS PDF Base HTMLS/HTMLs", ".")
    # Tight glob — only canonical Week_NN.html (zero-padded two-digit), so
    # stray *_preview.html or other ad-hoc files don't get audited as
    # production output. CLAUDE.md filename convention: Week_NN.html.
    for p in sorted(igcse_pdf.glob("Week_[0-9][0-9].html")):
        out.append((p, "pdf-base", "IGCSE PDF-base"))
    for p in sorted(ielts_pdf.glob("Week_[0-9][0-9].html")):
        out.append((p, "pdf-base", "IELTS PDF-base"))

    # Per-week Interactive HTMLs — resolved
    igcse_int = _resolve_dir(IGCSE_REPO, "IGCSE Interactive HTMLS", "Interactive")
    ielts_int = _resolve_dir(IELTS_REPO, "IELTS Interactive HTMLS", "Interactive")
    for p in sorted(igcse_int.glob("Week_[0-9][0-9].html")):
        out.append((p, "interactive", "IGCSE Interactive"))
    for p in sorted(ielts_int.glob("Week_[0-9][0-9].html")):
        out.append((p, "interactive", "IELTS Interactive"))

    # Canonical templates (the source-of-truth pre-fan-out files)
    igcse_tmpl = IGCSE_REPO / "template.html"
    if igcse_tmpl.exists():
        out.append((igcse_tmpl, "pdf-base", "IGCSE canonical template"))
    ielts_pdf_canon = IELTS_REPO / "canonical" / "pdf-base" / "Week_01.html"
    if ielts_pdf_canon.exists():
        out.append((ielts_pdf_canon, "pdf-base", "IELTS canonical PDF-base"))
    ielts_int_canon = IELTS_REPO / "canonical" / "interactive" / "Week_01.html"
    if ielts_int_canon.exists():
        out.append((ielts_int_canon, "interactive", "IELTS canonical interactive"))

    return out


def check_markers(html: str, markers: dict) -> dict:
    return {label: substr in html for label, substr in markers.items()}


def audit_one(path: Path, kind: str, strict: bool) -> dict:
    if not path.exists():
        return {"path": str(path), "kind": kind, "error": "missing"}
    html = path.read_text(encoding="utf-8")
    result = {"path": str(path), "kind": kind, "size": len(html)}
    # Typography markers apply to BOTH kinds (after PDF-base templates
    # get the source-edit port).
    result["typography"] = check_markers(html, TYPOGRAPHY_MARKERS)
    # Widget + Bug 3 markers only meaningful for interactive (or pdf-base
    # under --strict, where we'd expect them to NOT be present).
    if kind == "interactive":
        result["widget_js"] = check_markers(html, WIDGET_JS_MARKERS)
        result["widget_css"] = check_markers(html, WIDGET_CSS_MARKERS)
        if "IELTS" in str(path):
            result["bug3"] = check_markers(html, BUG3_IELTS_MARKERS)
        # Interactive should keep Sec 7/8 separate (for AI overlay). Track
        # this for the IGCSE side; IELTS uses Draft/Polished anchors
        # which are part of the make_interactive.py contract checked
        # implicitly by the widget_js markers.
        if "IGCSE" in str(path):
            result["sec78_separate"] = check_markers(html, IGCSE_INT_SEPARATE_MARKERS)
    else:
        # PDF-base — should have the merged form. Canonical templates are
        # the intentionally-unmerged source-of-truth (post_merge_*.py
        # transforms them at fan-out time), so skip the merge check for
        # those files — flagging them as drift would be a false positive.
        path_str = str(path).replace("\\", "/")
        is_canonical = "/canonical/" in path_str or path_str.endswith("/template.html")
        if not is_canonical:
            if "IGCSE" in path_str:
                result["sec78_merged"] = check_markers(html, IGCSE_PDF_MERGE_MARKERS)
            elif "IELTS" in path_str:
                result["sec78_merged"] = check_markers(html, IELTS_PDF_MERGE_MARKERS)
    return result


def render_text_report(mirror: dict, audits: list[dict], strict: bool) -> tuple[str, int]:
    """Render a human-readable report. Returns (report_text, drift_count)."""
    lines: list[str] = []
    drift = 0

    add = lines.append

    add("=" * 78)
    add("HTML Consistency Audit")
    add("=" * 78)

    # === Mirror status ===
    add("")
    add("== Axis 1: Source mirror (byte-identical between IGCSE and IELTS) ==")
    add("")
    mirror_files = list(mirror.items())
    for rel, info in sorted(mirror_files):
        if info["status"] == "missing":
            add(f"  ERR    {rel:<60s}  missing in: "
                f"{'IGCSE ' if not info['igcse_exists'] else ''}"
                f"{'IELTS' if not info['ielts_exists'] else ''}")
            drift += 1
        elif info["status"] == "drift":
            add(f"  DRIFT  {rel:<60s}  igcse={info['igcse']}  ielts={info['ielts']}")
            drift += 1
        else:
            add(f"  OK     {rel}")
    matched = sum(1 for v in mirror.values() if v.get("status") == "match")
    add(f"\n  Summary: {matched}/{len(mirror_files)} mirrored files in sync.")

    # === Per-HTML marker coverage ===
    add("")
    add("== Axis 2: Per-HTML marker coverage ==")
    add("")
    add("  Legend:  OK = marker present in all files in the group")
    add("           PARTIAL (n/N) = marker present in n out of N files")
    add("           MISSING (0/N) = marker present in zero of N files")
    add("")

    # Group audits by (label, kind) and check marker coverage per group.
    groups: dict[str, list[dict]] = defaultdict(list)
    label_for_path: dict[str, str] = {}
    for p, k, lbl in collect_htmls():
        label_for_path[str(p)] = lbl

    for a in audits:
        if a.get("error"):
            continue
        lbl = label_for_path.get(a["path"], "unknown")
        groups[lbl].append(a)

    for label, items in sorted(groups.items()):
        is_interactive = items[0]["kind"] == "interactive"
        is_ielts = "IELTS" in label
        # Canonical interactive (e.g., IELTS canonical/interactive/Week_01.html)
        # is the PRE-BAKE source template. Typography + widget markers get
        # injected by make_interactive.py from inserted_css.css +
        # inserted_script_modules at bake time, so the canonical file does
        # not (and should not) carry them. Skip the group entirely to avoid
        # flagging legitimate pre-bake state as drift.
        if is_interactive and "canonical" in label.lower():
            continue
        n = len(items)
        add(f"  --- {label} ({n} files) ---")

        # Typography (applies to all)
        for marker_key in TYPOGRAPHY_MARKERS:
            count = sum(1 for a in items if a.get("typography", {}).get(marker_key, False))
            status = _status_label(count, n)
            add(f"    TYPO  {status:<14s} {marker_key}")
            # Only count typography drift on Interactive (PDF-base needs source-edit
            # port, which is a separate work-item; we report but don't count as drift
            # unless --strict).
            if count < n and (is_interactive or strict):
                drift += (n - count)

        if is_interactive:
            for marker_key in WIDGET_JS_MARKERS:
                count = sum(1 for a in items if a.get("widget_js", {}).get(marker_key, False))
                status = _status_label(count, n)
                add(f"    JS    {status:<14s} {marker_key}")
                if count < n:
                    drift += (n - count)
            for marker_key in WIDGET_CSS_MARKERS:
                count = sum(1 for a in items if a.get("widget_css", {}).get(marker_key, False))
                status = _status_label(count, n)
                add(f"    CSS   {status:<14s} {marker_key}")
                if count < n:
                    drift += (n - count)
            if is_ielts:
                for marker_key in BUG3_IELTS_MARKERS:
                    count = sum(1 for a in items if a.get("bug3", {}).get(marker_key, False))
                    status = _status_label(count, n)
                    add(f"    BUG3  {status:<14s} {marker_key}")
                    if count < n:
                        drift += (n - count)
            # IGCSE Interactive: should keep Sec 7/8 SEPARATE for AI overlay.
            if not is_ielts:
                for marker_key in IGCSE_INT_SEPARATE_MARKERS:
                    count = sum(1 for a in items if a.get("sec78_separate", {}).get(marker_key, False))
                    status = _status_label(count, n)
                    add(f"    SEC78 {status:<14s} {marker_key}")
                    if count < n:
                        drift += (n - count)
        else:
            # PDF-base: Section 7 & 8 / Draft + Polished should be MERGED.
            # Canonical templates intentionally don't have sec78_merged
            # populated (audit_one skips the check for them) — so if no
            # item in this group has sec78_merged data, this is the
            # unmerged-by-design canonical group and we skip the row
            # entirely. Avoids a false-positive "MISSING (0/1)" line.
            has_merge_data = any("sec78_merged" in a for a in items)
            if has_merge_data:
                merge_markers = (IGCSE_PDF_MERGE_MARKERS if not is_ielts
                                 else IELTS_PDF_MERGE_MARKERS)
                for marker_key in merge_markers:
                    count = sum(1 for a in items if a.get("sec78_merged", {}).get(marker_key, False))
                    status = _status_label(count, n)
                    add(f"    MERGE {status:<14s} {marker_key}")
                    if count < n:
                        drift += (n - count)
        add("")

    # === Summary ===
    add("=" * 78)
    if drift == 0:
        add("CLEAN — no drift detected.")
    else:
        add(f"DRIFT — {drift} marker-missing instances detected.")
        add("Remediation hints:")
        add("  * For Interactive drift: run `python scripts/publish.py` in the")
        add("    affected repo (re-bakes Interactive/Week_*.html × 40 from the")
        add("    latest inserted_css.css + inserted_script_modules).")
        add("  * For PDF-base drift: edit canonical/pdf-base/Week_01.html (IELTS)")
        add("    or template.html (IGCSE) to add the missing typography rules,")
        add("    then republish.")
        add("  * For source-mirror drift: `cp` the file from the side with the")
        add("    fresher content to the other side, then re-run this audit.")
    add("=" * 78)

    return "\n".join(lines), drift


def _status_label(count: int, total: int) -> str:
    if count == total:
        return "OK"
    elif count == 0:
        return f"MISSING (0/{total})"
    else:
        return f"PARTIAL ({count}/{total})"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON (suppresses text report)",
    )
    ap.add_argument(
        "--strict", action="store_true",
        help="count typography drift on PDF-base HTMLs as drift "
             "(by default these are reported but not flagged, since "
             "PDF-base typography requires a separate source-edit pass).",
    )
    args = ap.parse_args()

    mirror = collect_mirror_status()
    htmls = collect_htmls()
    audits = [audit_one(p, k, args.strict) for p, k, _ in htmls]

    if args.json:
        out = {
            "mirror": mirror,
            "audits": audits,
        }
        print(json.dumps(out, indent=2))
        any_mirror_drift = any(v.get("status") != "match" for v in mirror.values())
        return 1 if any_mirror_drift else 0

    text, drift = render_text_report(mirror, audits, args.strict)
    print(text)
    return 1 if drift > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
