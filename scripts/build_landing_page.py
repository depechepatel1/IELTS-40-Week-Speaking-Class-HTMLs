#!/usr/bin/env python3
"""Generate index.html — landing page that links to all 40 IELTS lessons.

Reads each Week_*.html original to extract the week topic from
`<span class="week-tag">Week N • Lesson X • Topic</span>`, then
emits a single index.html at repo root that visually mirrors the lesson
plans' pastel-floating-window design vocabulary (same color tokens,
rotating pastel card backgrounds, Caveat hero font, multi-layer drop
shadows, animated hover lift).

Run:  python scripts/build_landing_page.py [--bucket-base https://ielts.aischool.studio]
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
    m = WEEK_TAG_RE.search(html_text)
    if not m:
        return "Untitled"
    raw = m.group(1).strip()
    raw = re.sub(r"\s*\(Part\s+\d+\)\s*$", "", raw, flags=re.IGNORECASE)
    return html.unescape(raw)


def collect_weeks() -> list[tuple[int, str]]:
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
    p = FONT_DIR / "Caveat-400.woff2"
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode("ascii")


def render_html(weeks: list[tuple[int, str]], bucket_base: str) -> str:
    base = bucket_base.rstrip("/")
    cards = []
    for n, topic in weeks:
        href = f"{base}/Week_{int(n):02d}.html"
        cards.append(
            f'  <a class="week-card" href="{html.escape(href)}">\n'
            f'    <span class="week-num">Week {n}</span>\n'
            f'    <span class="week-topic">{html.escape(topic)}</span>\n'
            f'    <span class="week-arrow" aria-hidden="true">→</span>\n'
            f'  </a>'
        )
    cards_html = "\n".join(cards)
    caveat = caveat_b64()
    caveat_face = (
        f"@font-face {{\n"
        f"  font-family: 'Caveat'; font-style: normal; font-weight: 400;\n"
        f"  font-display: swap;\n"
        f"  src: url(data:font/woff2;base64,{caveat}) format('woff2');\n"
        f"}}\n"
    ) if caveat else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>IELTS 40-Week Speaking Class — Lesson Library</title>
<style>
  {caveat_face}

  /* === Design tokens lifted from the lesson HTMLs === */
  :root {{
    --primary-color: #2c3e50;
    --accent-color:  #3498db;
    --highlight-color: #e74c3c;
    --bg-color: #eef2f5;
    --text-color: #333333;
    --border-radius: 14px;
    --shadow-card: 0 4px 10px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.05);
    --shadow-hover: 0 14px 30px rgba(52,152,219,0.18), 0 4px 8px rgba(0,0,0,0.08);
    --shadow-hero: 0 14px 40px rgba(44,62,80,0.18), 0 4px 12px rgba(0,0,0,0.08);
  }}

  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    padding: 36px 24px 60px 24px;
    font-family: 'Lato', 'Segoe UI', Tahoma, Verdana, sans-serif;
    color: var(--text-color);
    background:
      radial-gradient(circle at 10% 0%, rgba(52,152,219,0.06) 0%, transparent 50%),
      radial-gradient(circle at 90% 100%, rgba(155,89,182,0.05) 0%, transparent 50%),
      var(--bg-color);
    line-height: 1.5;
    min-height: 100vh;
  }}

  /* === Hero floating window === */
  .hero {{
    max-width: 1140px;
    margin: 0 auto 36px auto;
    background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
    color: white;
    border-radius: var(--border-radius);
    padding: 44px 40px 36px 40px;
    box-shadow: var(--shadow-hero);
    position: relative;
    overflow: hidden;
  }}
  .hero::before {{
    /* Decorative pastel circle, floats top-right */
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 240px; height: 240px;
    background: radial-gradient(circle, rgba(255,234,167,0.18) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
  }}
  .hero h1 {{
    font-family: 'Caveat', 'Bradley Hand', cursive;
    font-size: 3.4em;
    margin: 0;
    letter-spacing: 0.01em;
    line-height: 1.05;
    position: relative;
  }}
  .hero .subtitle {{
    font-size: 1.15em;
    opacity: 0.95;
    margin: 10px 0 4px 0;
    font-weight: 300;
    position: relative;
  }}
  .hero .cn {{
    font-size: 0.95em;
    opacity: 0.85;
    margin: 0;
    position: relative;
  }}
  .hero .meta {{
    margin-top: 22px;
    padding: 14px 18px;
    background: rgba(255,255,255,0.10);
    border-left: 3px solid #ffeaa7;
    border-radius: 8px;
    font-size: 0.92em;
    line-height: 1.65;
    position: relative;
  }}
  .hero .meta strong {{ color: #ffeaa7; }}

  /* === Week grid === */
  .weeks {{
    max-width: 1140px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 16px;
  }}

  .week-card {{
    background: var(--bg-card);
    color: var(--primary-color);
    text-decoration: none;
    border-radius: var(--border-radius);
    padding: 16px 18px 14px 18px;
    box-shadow: var(--shadow-card);
    border: 1px solid rgba(0,0,0,0.04);
    border-left: 5px solid var(--accent-card);
    transition:
      transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1),
      box-shadow 0.18s ease,
      border-color 0.18s ease;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 122px;
    position: relative;
  }}
  .week-card:hover {{
    transform: translateY(-4px) scale(1.02);
    box-shadow: var(--shadow-hover);
    border-left-color: var(--accent-card);
  }}
  .week-card:focus-visible {{
    outline: 3px solid var(--accent-card);
    outline-offset: 3px;
  }}

  .week-num {{
    font-family: 'Caveat', cursive;
    font-size: 1.85em;
    color: var(--accent-card);
    line-height: 1;
    font-weight: 700;
  }}
  .week-topic {{
    font-size: 0.95em;
    color: var(--primary-color);
    font-weight: 500;
    line-height: 1.35;
    flex-grow: 1;
  }}
  .week-arrow {{
    align-self: flex-end;
    font-size: 1.3em;
    color: var(--accent-card);
    opacity: 0.5;
    transition: transform 0.2s ease, opacity 0.2s ease;
  }}
  .week-card:hover .week-arrow {{
    opacity: 1;
    transform: translateX(4px);
  }}

  /* === Pastel rotation across cards (8 themes, cycle by :nth-child) === */
  .week-card:nth-child(8n + 1) {{ --bg-card: #e8f8f5; --accent-card: #1abc9c; }}  /* mint  / teal   */
  .week-card:nth-child(8n + 2) {{ --bg-card: #ebf5fb; --accent-card: #3498db; }}  /* sky   / blue   */
  .week-card:nth-child(8n + 3) {{ --bg-card: #fef9e7; --accent-card: #f39c12; }}  /* cream / amber  */
  .week-card:nth-child(8n + 4) {{ --bg-card: #f5eef8; --accent-card: #9b59b6; }}  /* lavender/purple*/
  .week-card:nth-child(8n + 5) {{ --bg-card: #fdedec; --accent-card: #e74c3c; }}  /* peach / red    */
  .week-card:nth-child(8n + 6) {{ --bg-card: #fef5e7; --accent-card: #e67e22; }}  /* apricot/orange */
  .week-card:nth-child(8n + 7) {{ --bg-card: #fff0f5; --accent-card: #e06688; }}  /* blush / pink   */
  .week-card:nth-child(8n + 0) {{ --bg-card: #eaf2f8; --accent-card: #34495e; }}  /* slate / charcoal*/

  /* === Footer === */
  footer {{
    max-width: 1140px;
    margin: 40px auto 0 auto;
    padding: 18px 24px;
    text-align: center;
    color: #7f8c8d;
    font-size: 0.85em;
    background: white;
    border-radius: var(--border-radius);
    box-shadow: var(--shadow-card);
  }}
  footer a {{ color: var(--accent-color); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}

  /* === Responsive === */
  @media (max-width: 720px) {{
    body {{ padding: 20px 14px 40px; }}
    .hero {{ padding: 30px 22px 26px; }}
    .hero h1 {{ font-size: 2.4em; }}
    .hero .subtitle {{ font-size: 1em; }}
    .weeks {{ grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }}
    .week-card {{ min-height: 108px; padding: 14px; }}
    .week-num {{ font-size: 1.6em; }}
  }}
</style>
</head>
<body>

<header class="hero">
  <h1>IELTS 40-Week Speaking Class</h1>
  <p class="subtitle">Interactive lesson library — record your answers, get AI feedback, listen to model answers.</p>
  <p class="cn">雅思口语 40 周课程 · 互动式课堂讲义</p>
  <div class="meta">
    Click any week to open the lesson. Each lesson includes voice-recorder
    widgets for shadowing practice, an AI-correct draft section, click-to-hear
    model answers, and an <strong>✉️ email button</strong> on the homework page
    that zips up all your week's recordings for sending to your teacher.
    <br/>
    <strong>Tip:</strong> recordings are saved on this device only — clear browser
    storage erases them. Email yourself the zip after each session.
  </div>
</header>

<main class="weeks" aria-label="Lesson list">
{cards_html}
</main>

<footer>
  Hosted on Aliyun OSS · {len(weeks)} weeks · Last updated automatically by build_landing_page.py
</footer>

</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket-base", default="https://ielts.aischool.studio")
    ap.add_argument("--out", default=str(REPO / "index.html"))
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
