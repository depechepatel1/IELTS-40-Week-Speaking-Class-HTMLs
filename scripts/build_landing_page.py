#!/usr/bin/env python3
"""Generate index.html — landing page that links to all 40 interactive lessons.

Reads each Week_*.html original to extract the week topic from
the `<span class="week-tag">Week N • Lesson X • Topic</span>` element, then
emits a single index.html at repo root that visually inherits the lesson
plans' design vocabulary (same color tokens, card pattern, Caveat hero font).

Run:  python scripts/build_landing_page.py [--bucket-base https://lessons.aischool.studio]
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FONT_DIR = REPO / "scripts" / "fonts"

WEEK_TAG_RE = re.compile(
    r'class="week-tag">\s*(?:Week\s+\d+\s*[•\-–—•]\s*Lesson\s+\d+\s*[•\-–—•]\s*)?([^<]+)<',
    re.IGNORECASE,
)
WEEK_NUM_RE = re.compile(r"Week_(\d+)\.html$")


def extract_topic(html_text: str) -> str:
    """Pull the lesson topic from the first .week-tag span. HTML-decode entities."""
    m = WEEK_TAG_RE.search(html_text)
    if not m:
        return "Untitled"
    raw = m.group(1).strip()
    # Trim trailing "(Part N)" markers — they vary across lessons
    raw = re.sub(r"\s*\(Part\s+\d+\)\s*$", "", raw, flags=re.IGNORECASE)
    return html.unescape(raw)


def collect_weeks() -> list[tuple[int, str]]:
    """Return [(week_num, topic), ...] sorted by week number."""
    weeks: list[tuple[int, str]] = []
    for p in REPO.glob("Week_*.html"):
        m = WEEK_NUM_RE.search(p.name)
        if not m:
            continue
        n = int(m.group(1))
        topic = extract_topic(p.read_text(encoding="utf-8"))
        weeks.append((n, topic))
    weeks.sort(key=lambda x: x[0])
    return weeks


def caveat_b64() -> str:
    return base64.b64encode((FONT_DIR / "Caveat-400.woff2").read_bytes()).decode("ascii")


def render_html(weeks: list[tuple[int, str]], bucket_base: str) -> str:
    base = bucket_base.rstrip("/")
    cards = []
    for n, topic in weeks:
        href = f"{base}/Week_{int(n):02d}.html"
        cards.append(
            f'    <a class="week-card" href="{html.escape(href)}">\n'
            f'      <span class="week-num">Week {n}</span>\n'
            f'      <span class="week-topic">{html.escape(topic)}</span>\n'
            f'      <span class="week-arrow" aria-hidden="true">→</span>\n'
            f'    </a>'
        )
    cards_html = "\n".join(cards)
    caveat = caveat_b64()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>IELTS 40-Week Speaking Class — Lesson Library</title>
<style>
  @font-face {{
    font-family: 'Caveat';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url(data:font/woff2;base64,{caveat}) format('woff2');
  }}

  /* === Design tokens lifted from the lesson HTMLs === */
  :root {{
    --primary-color: #2c3e50;
    --accent-color:  #3498db;
    --highlight-color: #e74c3c;
    --bg-color: #eef2f5;
    --card-bg: #ffffff;
    --text-color: #333333;
    --border-radius: 12px;
    --box-shadow: 0 10px 20px rgba(0,0,0,0.08), 0 6px 6px rgba(0,0,0,0.1);
    --bg-pastel-blue:   #e8f8f5;
    --bg-pastel-yellow: #fef9e7;
    --bg-pastel-green:  #eafaf1;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 32px 24px 48px 24px;
    font-family: 'Lato', 'Segoe UI', Tahoma, Verdana, sans-serif;
    color: var(--text-color);
    background: var(--bg-color);
    line-height: 1.5;
  }}

  /* === Header === */
  .hero {{
    max-width: 1100px;
    margin: 0 auto 36px auto;
    background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
    color: white;
    border-radius: var(--border-radius);
    padding: 40px 36px;
    box-shadow: var(--box-shadow);
  }}
  .hero h1 {{
    font-family: 'Caveat', 'Bradley Hand', cursive;
    font-size: 3em;
    margin: 0;
    letter-spacing: 0.02em;
    line-height: 1.1;
  }}
  .hero .subtitle {{
    font-size: 1.1em;
    opacity: 0.95;
    margin: 8px 0 0 0;
    font-weight: 300;
  }}
  .hero .cn {{
    font-size: 0.95em;
    opacity: 0.85;
    margin-top: 4px;
  }}
  .hero .meta {{
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid rgba(255,255,255,0.25);
    font-size: 0.9em;
    line-height: 1.7;
  }}
  .hero .meta strong {{ color: #ffeaa7; }}

  /* === Week grid === */
  .weeks {{
    max-width: 1100px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 14px;
  }}

  .week-card {{
    background: var(--card-bg);
    color: var(--primary-color);
    text-decoration: none;
    border-radius: var(--border-radius);
    padding: 16px 16px 14px 16px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    border: 1px solid #e0e6ed;
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 110px;
    position: relative;
  }}
  .week-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 18px rgba(52, 152, 219, 0.18);
    border-color: var(--accent-color);
  }}

  .week-num {{
    font-family: 'Caveat', cursive;
    font-size: 1.7em;
    color: var(--accent-color);
    line-height: 1;
    font-weight: 700;
  }}
  .week-topic {{
    font-size: 0.95em;
    color: var(--primary-color);
    font-weight: 500;
    line-height: 1.3;
    flex-grow: 1;
  }}
  .week-arrow {{
    align-self: flex-end;
    font-size: 1.2em;
    color: var(--accent-color);
    opacity: 0.6;
    transition: transform 0.15s ease, opacity 0.15s ease;
  }}
  .week-card:hover .week-arrow {{
    opacity: 1;
    transform: translateX(3px);
  }}

  /* === Footer === */
  footer {{
    max-width: 1100px;
    margin: 36px auto 0 auto;
    padding: 16px;
    text-align: center;
    color: #7f8c8d;
    font-size: 0.85em;
  }}
  footer a {{ color: var(--accent-color); text-decoration: none; }}

  /* === Responsive === */
  @media (max-width: 600px) {{
    body {{ padding: 18px 12px; }}
    .hero {{ padding: 28px 20px; }}
    .hero h1 {{ font-size: 2.2em; }}
    .weeks {{ grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }}
  }}
</style>
</head>
<body>

<header class="hero">
  <h1>IELTS 40-Week Speaking Class</h1>
  <p class="subtitle">Interactive lesson library — type, get instant AI feedback, listen to model answers.</p>
  <p class="cn">雅思口语 40 周课程 · 互动式课堂讲义</p>
  <div class="meta">
    Click any week to open the lesson. Each lesson includes a writing-homework section
    with AI correction, listen-aloud model answers, and clickable vocabulary with IPA
    pronunciation. <br/>
    <strong>Tip:</strong> your draft is saved on this device only — switching devices clears it.
  </div>
</header>

<main class="weeks" aria-label="Lesson list">
{cards_html}
</main>

<footer>
  Hosted on Aliyun OSS · <a href="mailto:depechepatel1@gmail.com">contact</a>
</footer>

</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bucket-base",
        default="https://lessons.aischool.studio",
        help="Public base URL for the lesson HTMLs (no trailing slash)",
    )
    ap.add_argument(
        "--out",
        default=str(REPO / "index.html"),
        help="Where to write the generated landing page",
    )
    args = ap.parse_args()

    weeks = collect_weeks()
    if not weeks:
        print("error: no Week_*.html files found at repo root", file=sys.stderr)
        return 2

    html_doc = render_html(weeks, args.bucket_base)
    out_path = Path(args.out)
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes, {len(weeks)} week cards)")
    print(f"Sample weeks:")
    for n, topic in weeks[:3]:
        print(f"  Week {n}: {topic}")
    print("  ...")
    for n, topic in weeks[-3:]:
        print(f"  Week {n}: {topic}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
