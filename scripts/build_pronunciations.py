#!/usr/bin/env python3
"""Extract bolded vocabulary from all 40 lesson HTMLs, look up IPA via the
CMU IPA dict, write a single pronunciations.json mapping at repo root.

Output is a flat JSON: { "word": "/ipa/" }.

Run:  python scripts/build_pronunciations.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Maintained mirror of CMU dict with IPA mappings.
CMU_IPA_URL = "https://raw.githubusercontent.com/menelik3/cmudict-ipa/master/cmudict-0.7b-ipa.txt"


def extract_words() -> set[str]:
    """Find every <strong>...</strong> within lesson HTMLs.

    Scoping note: a more surgical extraction would limit to .vocab-table /
    .model-box only, but that needs HTML parsing. The bolded-words approach
    is a superset; CMU lookups for non-vocab words are harmless (they just
    end up in the JSON and are referenced if a student happens to click).
    """
    words: set[str] = set()
    bold = re.compile(r"<strong[^>]*>([^<]+)</strong>", re.IGNORECASE)
    for p in sorted(REPO.glob("Week_*_Lesson_Plan.html")):
        text = p.read_text(encoding="utf-8")
        for m in bold.finditer(text):
            content = m.group(1).strip()
            for token in re.findall(r"[A-Za-z][A-Za-z'-]*", content):
                if 2 <= len(token) <= 30:
                    words.add(token.lower())
    return words


def fetch_cmu_ipa() -> dict[str, str]:
    """CMU IPA format: WORD<TAB>/aɪ p ə/   (or sometimes /ipa1/, /ipa2/ for variants)."""
    req = urllib.request.Request(
        CMU_IPA_URL,
        headers={"User-Agent": "ielts-interactive/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";;;"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        word = parts[0].lower().strip()
        # Drop multi-pronunciation suffixes like "address(1)"
        word = re.sub(r"\(\d+\)$", "", word)
        ipa = parts[1].strip()
        # Take the first encountered pronunciation only
        out.setdefault(word, ipa)
    return out


def main() -> int:
    print("Extracting bolded words from lesson HTMLs...", flush=True)
    words = extract_words()
    print(f"Found {len(words)} unique bolded words.", flush=True)

    print(f"Fetching CMU IPA dict from {CMU_IPA_URL}...", flush=True)
    cmu = fetch_cmu_ipa()
    print(f"CMU dict has {len(cmu)} entries.", flush=True)

    out = {w: cmu[w] for w in sorted(words) if w in cmu}
    print(f"Matched {len(out)} / {len(words)} ({100 * len(out) / max(1, len(words)):.1f}%).", flush=True)

    out_path = REPO / "pronunciations.json"
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    size = out_path.stat().st_size
    print(f"Wrote {out_path} ({size:,} bytes).", flush=True)
    if size > 1_048_576:
        print("WARNING: pronunciations.json exceeds 1 MB.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
