"""Path resolvers for the IELTS pipeline scripts.

Round 56 (2026-05-17) output-folder reorganization.

Mirror of the IGCSE scripts/_paths.py with IELTS-specific folder names.

Output files (Week_NN.html PDF base, Week_NN.pdf converted, combined PDF,
Interactive/Week_NN.html, index.html landing page) used to live at the
repo root or in an `Interactive/` subfolder. The reorg moved them into
five organised folders:

    IELTS PDF Base HTMLS/
        HTMLs/                   - Week_NN.html  (40 files, PDF-base output)
        Converted PDFs/          - Week_NN.pdf   (40 files, per-week PDFs)
        Combined PDF/            - IELTS_Speaking_Course_Complete.pdf
    IELTS Interactive HTMLS/     - Week_NN.html  (40 files, Interactive)
    Landing Page/                - index.html    (landing page)

Source files (canonical/, parse_data.py, scripts/, function-compute/,
images/, Curriculum 19.txt) stay at their current locations.

Phase 1 (the initial reorg) shipped these resolvers with a transitional
`if new.is_dir() else <old>` fallback so the pipeline kept working while
files were migrated (Phase 2). Phase 3 verified end-to-end publishes in
the new layout. Phase 4 (this revision) removed the fallback branches —
the resolvers now return the new paths unconditionally. If you see a
"directory does not exist" error from a script that uses these
resolvers, your local checkout is missing the Round 56 folder structure;
re-run the publish pipeline or `git pull` to restore it.
"""

from __future__ import annotations
from pathlib import Path


def resolve_pdf_base_html_dir(repo: Path) -> Path:
    """Where Week_NN.html (PDF base output) is read from and written to."""
    return repo / "IELTS PDF Base HTMLS" / "HTMLs"


def resolve_pdf_converted_dir(repo: Path) -> Path:
    """Where Week_NN.pdf (per-week converted PDFs) lives."""
    return repo / "IELTS PDF Base HTMLS" / "Converted PDFs"


def resolve_pdf_combined_dir(repo: Path) -> Path:
    """Where IELTS_Speaking_Course_Complete.pdf (combined) is written."""
    return repo / "IELTS PDF Base HTMLS" / "Combined PDF"


def resolve_interactive_dir(repo: Path) -> Path:
    """Where Interactive/Week_NN.html is read from and written to."""
    return repo / "IELTS Interactive HTMLS"


def resolve_landing_dir(repo: Path) -> Path:
    """Where index.html (landing page) is read from and written to."""
    return repo / "Landing Page"
