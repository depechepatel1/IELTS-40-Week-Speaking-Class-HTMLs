#!/usr/bin/env python3
"""Combine intro_packet.pdf + Week_01.pdf … Week_40.pdf into a single
IELTS_Speaking_Course_Complete.pdf for printing/distribution.

Inputs (from repo root):
  - intro_packet.pdf            (cover + course intro — first in combined)
  - Week_01.pdf … Week_40.pdf   (40 weekly lesson packs — appended in order)

Output:
  - IELTS_Speaking_Course_Complete.pdf  (at repo root)

Generates the combined PDF using pypdf (pure-Python, no native deps).
Skips the file if a source PDF is missing — prints which one and exits 1.

Usage:
  python scripts/combine_pdfs.py
"""
from __future__ import annotations
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pypdf import PdfReader, PdfWriter

REPO = Path(__file__).resolve().parent.parent
INTRO = REPO / "intro_packet.pdf"
OUT = REPO / "IELTS_Speaking_Course_Complete.pdf"


def main() -> int:
    weeks = sorted(REPO.glob("Week_[0-9][0-9].pdf"))
    if not weeks:
        print("FATAL: no Week_NN.pdf files found at repo root.")
        print("Run `python batch_convert_pdf.py` first.")
        return 1
    if not INTRO.exists():
        print(f"FATAL: {INTRO.name} not found at repo root.")
        print("Run `python convert_intro_pdf.py` first.")
        return 1

    sources = [INTRO] + weeks
    print(f"Combining {len(sources)} PDFs:")
    print(f"  - {INTRO.name}")
    for w in weeks:
        print(f"  - {w.name}")

    writer = PdfWriter()
    total_pages = 0
    for src in sources:
        reader = PdfReader(src)
        n = len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)
        total_pages += n
        print(f"  + {src.name}: {n} pages")

    # LOSSLESS compression pass — both methods preserve pixel-identical rendering:
    #   - compress_content_streams: re-compress each page's content stream
    #     with FlateDecode (catches any uncompressed streams from Playwright).
    #   - compress_identical_objects: dedupe objects that are byte-identical
    #     across pages (esp. embedded woff2 fonts repeated in every weekly PDF
    #     — saves ~145KB × 40 weeks = ~5.6MB just on font dedup).
    print("\nApplying lossless compression...")
    for page in writer.pages:
        page.compress_content_streams()
    writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)

    with open(OUT, "wb") as f:
        writer.write(f)

    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"\nWrote {OUT.name}: {total_pages} pages, {size_mb:.1f} MB (lossless-compressed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
