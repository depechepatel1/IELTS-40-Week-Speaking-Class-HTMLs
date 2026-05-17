"""Path resolvers for the IELTS pipeline scripts.

Round 56 (2026-05-17) output-folder reorganization — Phase 1 (fallback).

Mirror of the IGCSE scripts/_paths.py with IELTS-specific folder names.
Each resolver returns the new path if the new folder exists; otherwise
it falls back to the old (root or Interactive/) location so the
pipeline keeps working during the file-migration transition.

New folder layout:

    IELTS PDF Base HTMLS/
        HTMLs/                   - Week_NN.html  (40 files, PDF-base output)
        Converted PDFs/          - Week_NN.pdf   (40 files, per-week PDFs)
        Combined PDF/            - IELTS_Speaking_Course_Complete.pdf
    IELTS Interactive HTMLS/     - Week_NN.html  (40 files, Interactive)
    Landing Page/                - index.html    (landing page)

Source files (canonical/, parse_data.py, scripts/, function-compute/,
images/, Curriculum 19.txt) stay at their current locations.

After Phase 4 (remove fallback), the `else` branches will be deleted
and the resolvers will return the new paths unconditionally.
"""

from __future__ import annotations
from pathlib import Path


def resolve_pdf_base_html_dir(repo: Path) -> Path:
    """Where Week_NN.html (PDF base output) is read from and written to.

    NEW: <repo>/IELTS PDF Base HTMLS/HTMLs/
    OLD: <repo>/
    """
    new = repo / "IELTS PDF Base HTMLS" / "HTMLs"
    return new if new.is_dir() else repo


def resolve_pdf_converted_dir(repo: Path) -> Path:
    """Where Week_NN.pdf (per-week converted PDFs) lives.

    NEW: <repo>/IELTS PDF Base HTMLS/Converted PDFs/
    OLD: <repo>/
    """
    new = repo / "IELTS PDF Base HTMLS" / "Converted PDFs"
    return new if new.is_dir() else repo


def resolve_pdf_combined_dir(repo: Path) -> Path:
    """Where IELTS_Speaking_Course_Complete.pdf (combined) is written.

    NEW: <repo>/IELTS PDF Base HTMLS/Combined PDF/
    OLD: <repo>/
    """
    new = repo / "IELTS PDF Base HTMLS" / "Combined PDF"
    return new if new.is_dir() else repo


def resolve_interactive_dir(repo: Path) -> Path:
    """Where Interactive/Week_NN.html is read from and written to.

    NEW: <repo>/IELTS Interactive HTMLS/
    OLD: <repo>/Interactive/
    """
    new = repo / "IELTS Interactive HTMLS"
    return new if new.is_dir() else (repo / "Interactive")


def resolve_landing_dir(repo: Path) -> Path:
    """Where index.html (landing page) is read from and written to.

    NEW: <repo>/Landing Page/
    OLD: <repo>/
    """
    new = repo / "Landing Page"
    return new if new.is_dir() else repo
