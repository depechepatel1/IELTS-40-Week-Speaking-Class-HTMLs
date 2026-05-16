#!/usr/bin/env python3
"""Generate index.html — landing page that links to all 40 IELTS lessons.

Round 54 redesign — Kimi's hero+grid layout with:
  * Full-viewport hero featuring a looping cover video (videos/cover_spinning.webm)
  * Fixed transparent topbar that solidifies on scroll
  * 5-column lesson library card grid with 16:9 landing images per week
  * iOS voice-quality hint banner (ported from the previous landing page)

Reads each Week_NN.html original to extract the topic from
`<span class="week-tag">Week N • Lesson X • Topic</span>`. The topic-extraction
regex and the iOS voice-hint JS logic are preserved verbatim from the previous
build_landing_page.py.

Run:  python scripts/build_landing_page.py [--bucket-base https://ielts.aischool.studio]
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# === Topic-extraction regex (preserved verbatim from previous version) =======
# IELTS week-tag format: <span class="week-tag">Week N • Lesson X • Topic</span>
# The regex strips the "Week N • Lesson X • " prefix and captures only the topic.
WEEK_TAG_RE = re.compile(
    r'class="week-tag">\s*(?:Week\s+\d+\s*[•\-–—•]\s*Lesson\s+\d+\s*[•\-–—•]\s*)?([^<]+)<',
    re.IGNORECASE,
)
WEEK_NUM_RE = re.compile(r"Week_(\d+)\.html$")


# === Landing-image filenames (40 entries, in week order) =====================
# Each filename corresponds to images/landing/{name}.jpg and is paired with
# the same-index Week_NN.html during HTML generation. Validated at runtime
# by an assertion in main().
IELTS_IMAGES = [
    "w01-family.jpg", "w02-abroad.jpg", "w03-dreamjob.jpg", "w04-movie.jpg",
    "w05-nature.jpg", "w06-trees.jpg", "w07-app.jpg", "w08-advice.jpg",
    "w09-art.jpg", "w10-building.jpg", "w11-tech.jpg", "w12-lost.jpg",
    "w13-famous.jpg", "w14-shopping.jpg", "w15-books.jpg", "w16-laughter.jpg",
    "w17-friends.jpg", "w18-housing.jpg", "w19-objects.jpg", "w20-journeys.jpg",
    "w21-talent.jpg", "w22-familybiz.jpg", "w23-toys.jpg", "w24-technical.jpg",
    "w25-mentor.jpg", "w26-service.jpg", "w27-digital.jpg", "w28-social.jpg",
    "w29-ethics.jpg", "w30-wildlife.jpg", "w31-science.jpg", "w32-learning.jpg",
    "w33-habits.jpg", "w34-restricted.jpg", "w35-planning.jpg", "w36-competition.jpg",
    "w37-neighbors.jpg", "w38-water.jpg", "w39-fashion.jpg", "w40-festival.jpg",
]


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


def build_card(n: int, topic: str, image_filename: str, card_index: int, bucket_base: str) -> str:
    """Render a single .week-card <article> with image, badge, and title."""
    href = f"{bucket_base}/Week_{n:02d}.html"
    img_src = f"images/landing/{image_filename}"
    safe_topic = html.escape(topic)
    safe_href = html.escape(href)
    safe_img = html.escape(img_src)
    return (
        f'      <article class="week-card" style="--card-index: {card_index};">\n'
        f'        <a class="week-card-link" href="{safe_href}">\n'
        f'          <div class="week-card-image">\n'
        f'            <img loading="lazy" src="{safe_img}" alt="{safe_topic}">\n'
        f'            <span class="week-badge">Week {n}</span>\n'
        f'          </div>\n'
        f'          <div class="week-card-body">\n'
        f'            <h3 class="week-card-title">{safe_topic}</h3>\n'
        f'            <span class="week-card-arrow" aria-hidden="true">&rarr;</span>\n'
        f'          </div>\n'
        f'        </a>\n'
        f'      </article>'
    )


def render_html(weeks: list[tuple[int, str]], bucket_base: str) -> str:
    base = bucket_base.rstrip("/")

    # Build the 40 lesson cards.
    cards = []
    for i, (n, topic) in enumerate(weeks):
        cards.append(build_card(n, topic, IELTS_IMAGES[i], i, base))
    cards_html = "\n".join(cards)

    video_url = f"{base}/videos/cover_spinning.webm"

    # ------------------------------------------------------------------
    # The full HTML document. Triple-quoted f-string — every literal CSS
    # curly brace is doubled ({{ }}). Variable interpolations use single
    # braces with a {name} placeholder.
    # ------------------------------------------------------------------
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>IELTS Speaking &mdash; 40-Week Course | AI School</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Inter:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet"/>
<style>
  /* === Kimi design tokens ============================================== */
  :root {{
    --primary:     #0D9488;   /* teal */
    --accent:      #E85D4C;   /* coral */
    --gold:        #D4A853;   /* gold */
    --bg:          #FAF7F2;   /* cream */
    --text:        #1B2A4A;   /* navy */
    --muted:       #5C6B7F;
    --light:       #8B95A5;
    --card-border: #E8E2D9;
    --card-hover:  #D4A853;
  }}

  *, *::before, *::after {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    font-family: 'Inter', 'Segoe UI', Tahoma, Verdana, sans-serif;
    color: var(--text);
    background: var(--bg);
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}
  img {{ max-width: 100%; display: block; }}
  a {{ color: inherit; text-decoration: none; }}

  /* === Topbar / navigation ============================================ */
  .topbar {{
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 64px;
    z-index: 100;
    background: transparent;
    border-bottom: 1px solid transparent;
    transition: background 0.3s ease, border-color 0.3s ease, backdrop-filter 0.3s ease;
  }}
  .topbar.scrolled {{
    background: rgba(250, 247, 242, 0.95);
    -webkit-backdrop-filter: blur(12px);
    backdrop-filter: blur(12px);
    border-bottom-color: rgba(27, 42, 74, 0.08);
  }}
  .topbar-inner {{
    max-width: 1280px;
    margin: 0 auto;
    height: 100%;
    padding: 0 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .topbar-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    color: #ffffff;
    transition: color 0.3s ease;
  }}
  .topbar.scrolled .topbar-brand {{ color: var(--text); }}
  .topbar-brand-mark {{
    width: 28px;
    height: 28px;
    flex-shrink: 0;
  }}
  .topbar-brand-name {{
    font-family: 'Playfair Display', Georgia, serif;
    font-weight: 700;
    font-size: 22px;
    letter-spacing: 0.01em;
  }}
  .topbar-nav {{
    display: flex;
    align-items: center;
    gap: 32px;
  }}
  .topbar-link {{
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.92);
    transition: color 0.3s ease, opacity 0.2s ease;
  }}
  .topbar.scrolled .topbar-link {{ color: var(--text); }}
  .topbar-link:hover {{ opacity: 0.75; }}
  .topbar-cta {{
    display: inline-flex;
    align-items: center;
    background: var(--accent);
    color: #ffffff !important;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 600;
    padding: 10px 22px;
    border-radius: 999px;
    transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
    box-shadow: 0 2px 8px rgba(232, 93, 76, 0.25);
  }}
  .topbar-cta:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(232, 93, 76, 0.35);
    background: #d54a3a;
  }}

  /* === Hero =========================================================== */
  .hero {{
    position: relative;
    height: 100vh;
    min-height: 600px;
    width: 100%;
    overflow: hidden;
    /* CSS fallback gradient — visible if the video tag fails to load. */
    background: linear-gradient(135deg, #0D9488 0%, #1B2A4A 100%);
  }}
  .hero-video {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    z-index: 0;
  }}
  .hero-overlay {{
    position: absolute;
    inset: 0;
    z-index: 1;
    background:
      radial-gradient(ellipse at center, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.55) 100%),
      linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.45) 50%, rgba(0,0,0,0.55) 100%);
  }}
  .hero-content {{
    position: relative;
    z-index: 2;
    height: 100%;
    max-width: 1280px;
    margin: 0 auto;
    padding: 0 48px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    color: #ffffff;
  }}
  .hero-overline,
  .hero-title,
  .hero-subtitle,
  .hero-cn {{
    opacity: 0;
    transform: translateY(20px);
    animation: fadeUp 0.9s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }}
  .hero-overline {{
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--gold);
    margin: 0 0 24px 0;
    animation-delay: 0s;
  }}
  .hero-title {{
    font-family: 'Playfair Display', Georgia, serif;
    font-weight: 700;
    font-size: 84px;
    line-height: 1.05;
    letter-spacing: -0.02em;
    margin: 0 0 28px 0;
    color: #ffffff;
    animation-delay: 0.2s;
  }}
  .hero-subtitle {{
    font-family: 'Inter', sans-serif;
    font-size: 20px;
    font-weight: 400;
    line-height: 1.55;
    max-width: 760px;
    margin: 0 0 16px 0;
    color: rgba(255, 255, 255, 0.92);
    animation-delay: 0.5s;
  }}
  .hero-cn {{
    font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
    font-size: 16px;
    font-weight: 400;
    line-height: 1.6;
    margin: 0;
    color: rgba(255, 255, 255, 0.78);
    animation-delay: 0.7s;
  }}
  .hero-scroll-indicator {{
    position: absolute;
    bottom: 36px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 2;
    width: 44px;
    height: 44px;
    color: rgba(255, 255, 255, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    animation: bounce 2s ease-in-out infinite;
    transition: color 0.2s ease;
  }}
  .hero-scroll-indicator:hover {{ color: #ffffff; }}
  .hero-scroll-indicator svg {{ width: 28px; height: 28px; }}

  @keyframes fadeUp {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes bounce {{
    0%, 100% {{ transform: translateX(-50%) translateY(0); }}
    50%      {{ transform: translateX(-50%) translateY(10px); }}
  }}

  /* === iOS voice-hint banner ========================================== */
  /* Hidden by default; the inline script at end-of-body reveals it only
     when the device is iOS, no Premium/Enhanced voice is installed, and
     the user hasn't dismissed it on a previous visit. */
  #ios-voice-hint {{
    max-width: 1280px;
    margin: 32px auto 0 auto;
    background: var(--bg);
    border-left: 4px solid var(--gold);
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(27, 42, 74, 0.06);
    display: none;
  }}
  #ios-voice-hint.is-visible {{ display: block; }}
  .ios-hint-content {{
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 20px 28px;
  }}
  .ios-hint-icon {{
    font-size: 28px;
    line-height: 1;
    flex-shrink: 0;
  }}
  .ios-hint-text {{ flex: 1; min-width: 0; }}
  .ios-hint-text strong {{
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 16px;
    font-weight: 600;
    display: block;
    margin-bottom: 8px;
  }}
  .ios-hint-text p {{
    margin: 4px 0;
    color: var(--muted);
    font-size: 14px;
    line-height: 1.55;
  }}
  .ios-hint-text p.cn {{
    color: var(--light);
    font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  }}
  #ios-voice-hint-dismiss {{
    background: transparent;
    border: none;
    font-size: 28px;
    color: var(--light);
    cursor: pointer;
    padding: 0 8px;
    line-height: 1;
    flex-shrink: 0;
    transition: color 0.2s ease;
  }}
  #ios-voice-hint-dismiss:hover {{ color: var(--accent); }}

  /* === Lesson library section ========================================= */
  .lesson-library {{
    background: var(--bg);
    padding: 120px 48px;
  }}
  .lesson-library-inner {{
    max-width: 1280px;
    margin: 0 auto;
  }}
  .lesson-library-header {{
    margin-bottom: 64px;
    max-width: 760px;
  }}
  .lesson-library-header h2 {{
    font-family: 'Playfair Display', Georgia, serif;
    font-weight: 700;
    font-size: 56px;
    line-height: 1.1;
    letter-spacing: -0.02em;
    margin: 0 0 24px 0;
    color: var(--text);
  }}
  .lesson-library-header p.lesson-library-desc {{
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    line-height: 1.65;
    color: var(--muted);
    margin: 0 0 28px 0;
  }}
  .lesson-library-tip {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(232, 93, 76, 0.08);
    border: 1px solid rgba(232, 93, 76, 0.2);
    color: var(--accent);
    padding: 12px 20px;
    border-radius: 24px;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 500;
    line-height: 1.5;
  }}

  /* === Card grid ====================================================== */
  .card-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 24px;
  }}
  .week-card {{
    background: #ffffff;
    border: 1px solid var(--card-border);
    border-radius: 16px;
    overflow: hidden;
    transition:
      border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
      box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
      transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
      opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    opacity: 0;
    transform: translateY(20px);
    transition-delay: calc(var(--card-index) * 0.03s);
  }}
  .week-card.visible {{
    opacity: 1;
    transform: translateY(0);
  }}
  .week-card:hover {{
    /* Reset the entrance stagger so hover response is instant on every card.
       Without this, late cards inherit a 1+ second transition-delay from
       the per-card --card-index stagger and feel sluggish on hover. */
    transition-delay: 0s;
    border-color: var(--card-hover);
    box-shadow: 0 8px 32px rgba(27, 42, 74, 0.08);
    transform: translateY(-4px);
  }}
  .week-card-link {{
    display: block;
    color: inherit;
    text-decoration: none;
    height: 100%;
  }}
  .week-card-image {{
    position: relative;
    width: 100%;
    padding-top: 56.25%;  /* 16:9 */
    overflow: hidden;
    background: #ECE6DC;
  }}
  .week-card-image img {{
    position: absolute;
    top: 0; left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .week-card:hover .week-card-image img {{
    transform: scale(1.04);
  }}
  .week-badge {{
    position: absolute;
    bottom: 12px;
    left: 12px;
    background: var(--text);
    color: #ffffff;
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 12px;
  }}
  .week-card-body {{
    position: relative;
    padding: 20px 22px 48px 22px;
    min-height: 110px;
  }}
  .week-card-title {{
    font-family: 'Playfair Display', Georgia, serif;
    font-weight: 700;
    font-size: 20px;
    line-height: 1.3;
    margin: 0;
    color: var(--text);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .week-card-arrow {{
    position: absolute;
    right: 22px;
    bottom: 18px;
    font-size: 18px;
    color: var(--light);
    transition: color 0.3s ease, transform 0.3s ease;
  }}
  .week-card:hover .week-card-arrow {{
    color: var(--accent);
    transform: translateX(4px);
  }}

  /* === Footer ========================================================= */
  footer.site-footer {{
    background: var(--text);
    color: #ffffff;
  }}
  .site-footer-inner {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 64px 48px;
    text-align: center;
  }}
  .site-footer-brand {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: #ffffff;
  }}
  .site-footer-brand svg {{
    width: 32px;
    height: 32px;
    color: #ffffff;
  }}
  .site-footer-brand span {{
    font-family: 'Playfair Display', Georgia, serif;
    font-weight: 700;
    font-size: 24px;
  }}
  .site-footer-tagline {{
    font-family: 'Inter', sans-serif;
    font-size: 16px;
    color: rgba(255, 255, 255, 0.7);
    margin: 16px 0 0 0;
  }}
  .site-footer-divider {{
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    margin: 32px auto;
    max-width: 480px;
  }}
  .site-footer-copy {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.5);
    margin: 0;
  }}

  /* === Responsive ===================================================== */
  /* Tablet (768-1023px): 4 columns */
  @media (max-width: 1023px) {{
    .card-grid {{ grid-template-columns: repeat(4, 1fr); gap: 20px; }}
    .topbar-inner {{ padding: 0 32px; }}
    .lesson-library {{ padding: 100px 32px; }}
    .hero-content {{ padding: 0 32px; }}
    .hero-title {{ font-size: 68px; }}
    .lesson-library-header h2 {{ font-size: 48px; }}
    .site-footer-inner {{ padding: 56px 32px; }}
  }}

  /* Mobile (<768px): 2 columns */
  @media (max-width: 767px) {{
    .card-grid {{ grid-template-columns: repeat(2, 1fr); gap: 16px; }}
    .topbar {{ height: 56px; }}
    .topbar-inner {{ padding: 0 20px; }}
    .topbar-nav {{ gap: 16px; }}
    .topbar-link:not(.topbar-cta) {{ display: none; }}
    .topbar-cta {{ padding: 8px 16px; font-size: 13px; }}
    .lesson-library {{ padding: 72px 20px; }}
    .lesson-library-header {{ margin-bottom: 40px; }}
    .lesson-library-header h2 {{ font-size: 36px; }}
    .lesson-library-header p.lesson-library-desc {{ font-size: 16px; }}
    .hero-content {{ padding: 0 20px; }}
    .hero-overline {{ font-size: 11px; margin-bottom: 18px; }}
    .hero-title {{ font-size: 52px; margin-bottom: 20px; }}
    .hero-subtitle {{ font-size: 16px; }}
    .hero-cn {{ font-size: 14px; }}
    .week-card-body {{ padding: 16px 18px 44px 18px; min-height: 96px; }}
    .week-card-title {{ font-size: 17px; }}
    .week-card-arrow {{ right: 18px; bottom: 14px; }}
    .ios-hint-content {{ padding: 16px 20px; }}
    .site-footer-inner {{ padding: 48px 20px; }}
  }}

  /* === Print stylesheet =============================================== */
  /* When printed, strip out everything decorative and produce a clean
     plain-text list of "Week N — Topic". */
  @media print {{
    .topbar,
    .hero,
    .hero-video,
    .hero-overlay,
    .hero-scroll-indicator,
    #ios-voice-hint,
    footer.site-footer {{
      display: none !important;
    }}
    body {{ background: #ffffff; color: #000000; }}
    .lesson-library {{ padding: 24px; }}
    .card-grid {{
      display: block !important;
      grid-template-columns: none !important;
    }}
    .week-card {{
      opacity: 1 !important;
      transform: none !important;
      border: none !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      page-break-inside: avoid;
      margin: 0 0 6px 0;
    }}
    .week-card-image {{ display: none !important; }}
    .week-card-body {{
      padding: 0 !important;
      min-height: 0 !important;
    }}
    .week-card-title {{
      font-family: serif;
      font-size: 12pt;
      -webkit-line-clamp: unset;
      display: block;
      overflow: visible;
    }}
    .week-card-title::before {{
      content: "Week " counter(week-counter) " \\2014  ";
      counter-increment: week-counter;
      font-weight: 700;
    }}
    .card-grid {{ counter-reset: week-counter; }}
    .week-card-arrow {{ display: none !important; }}
  }}
</style>
</head>
<body>

<!-- ================ Fixed top navigation =============================== -->
<nav class="topbar" id="topbar" aria-label="Primary">
  <div class="topbar-inner">
    <a class="topbar-brand" href="#top" aria-label="AI School home">
      <svg class="topbar-brand-mark" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M16 3 L28 11 L28 21 L16 29 L4 21 L4 11 Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" fill="none"/>
        <path d="M11 20 L16 11 L21 20 M13 17 L19 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      </svg>
      <span class="topbar-brand-name">AI School</span>
    </a>
    <div class="topbar-nav">
      <a class="topbar-link" href="#lessons">Lessons</a>
      <a class="topbar-link" href="#contact">Contact</a>
      <a class="topbar-link topbar-cta" href="#lessons">Start Learning</a>
    </div>
  </div>
</nav>

<!-- ================ Hero =============================================== -->
<section class="hero" id="top">
  <video class="hero-video" autoplay muted loop playsinline preload="metadata" aria-hidden="true">
    <source src="{video_url}" type="video/webm"/>
  </video>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <p class="hero-overline">AI School &mdash; 40-Week IELTS Speaking Course</p>
    <h1 class="hero-title">IELTS Speaking<br/>40-Week Course</h1>
    <p class="hero-subtitle">Interactive lesson library &mdash; record your answers, get AI feedback, listen to model answers.</p>
    <p class="hero-cn">雅思口语 40 周课程 · 互动式课堂讲义</p>
  </div>
  <a class="hero-scroll-indicator" href="#lessons" aria-label="Scroll to lessons">
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M6 9 L12 15 L18 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </a>
</section>

<!-- ================ iOS voice-hint banner (hidden by default) ========== -->
<!-- Round 40 port — shown ONLY when (a) device is iOS, (b) no Premium /
     Enhanced voice is already installed, and (c) the user hasn't
     dismissed it. The script at end-of-body reveals it. -->
<aside id="ios-voice-hint" role="status" aria-live="polite">
  <div class="ios-hint-content">
    <div class="ios-hint-icon" aria-hidden="true">🐢</div>
    <div class="ios-hint-text">
      <strong>iPad users &mdash; install Enhanced voices for natural speech</strong>
      <p>For the best speaking-practice experience on iPad, install a
      higher-quality English voice: <em>Settings &rarr; Accessibility &rarr;
      Spoken Content &rarr; Voices &rarr; English</em>. Tap a voice with a
      download arrow (Ava, Daniel, Serena are excellent). Free,
      ~50&nbsp;MB. Every lesson page will automatically use the new
      voice once it's downloaded.</p>
      <p class="cn">iPad 用户 &mdash; 为获得更自然的英语朗读，请在
      <em>设置 &rarr; 辅助功能 &rarr; 朗读内容 &rarr; 语音 &rarr; 英语</em>
      中下载带箭头的高品质语音（如 Ava、Daniel、Serena）。免费，约 50&nbsp;MB。</p>
    </div>
    <button id="ios-voice-hint-dismiss" type="button"
            aria-label="Dismiss this notice / 关闭此提示">&times;</button>
  </div>
</aside>

<!-- ================ Lesson Library ===================================== -->
<section class="lesson-library" id="lessons">
  <div class="lesson-library-inner">
    <header class="lesson-library-header">
      <h2>Lesson Library</h2>
      <p class="lesson-library-desc">Forty interactive IELTS speaking lessons &mdash; Parts 1, 2, and 3 across all topics. Each lesson includes voice-recorder widgets, AI-corrected drafts, click-to-hear model answers, and an email button that zips up your recordings.</p>
      <span class="lesson-library-tip">💡 Recordings are saved on this device only &mdash; clearing the browser storage erases them. Email your teacher the recordings zip file after each session.</span>
    </header>
    <div class="card-grid" id="card-grid">
{cards_html}
    </div>
  </div>
</section>

<!-- ================ Footer ============================================= -->
<footer class="site-footer" id="contact">
  <div class="site-footer-inner">
    <div class="site-footer-brand">
      <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M16 3 L28 11 L28 21 L16 29 L4 21 L4 11 Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" fill="none"/>
        <path d="M11 20 L16 11 L21 20 M13 17 L19 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      </svg>
      <span>AI School</span>
    </div>
    <p class="site-footer-tagline">40 weeks to speaking confidence</p>
    <hr class="site-footer-divider"/>
    <p class="site-footer-copy">&copy; 2026 AI School. All rights reserved.</p>
  </div>
</footer>

<!-- ================ Scripts ============================================ -->
<script>
  // --------------------------------------------------------------------
  // 1) Topbar scroll-state: solidify nav background after a few pixels
  //    of scroll so it stays legible once the user leaves the hero.
  // --------------------------------------------------------------------
  (function () {{
    var topbar = document.getElementById('topbar');
    if (!topbar) return;
    function onScroll() {{
      if (window.scrollY > 24) {{
        topbar.classList.add('scrolled');
      }} else {{
        topbar.classList.remove('scrolled');
      }}
    }}
    onScroll();
    window.addEventListener('scroll', onScroll, {{ passive: true }});
  }})();

  // --------------------------------------------------------------------
  // 2) Lesson-card entrance animation. Each card has --card-index set
  //    inline so its transition-delay staggers nicely. We use an
  //    IntersectionObserver so the cards animate in only when they
  //    scroll into view.
  // --------------------------------------------------------------------
  (function () {{
    var cards = document.querySelectorAll('.week-card');
    if (!cards.length) return;
    if (!('IntersectionObserver' in window)) {{
      // No IO support — just reveal everything immediately.
      cards.forEach(function (c) {{ c.classList.add('visible'); }});
      return;
    }}
    var observer = new IntersectionObserver(function (entries) {{
      entries.forEach(function (entry) {{
        if (entry.isIntersecting) {{
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }}
      }});
    }}, {{ threshold: 0.1, rootMargin: '0px 0px -50px 0px' }});
    cards.forEach(function (c) {{ observer.observe(c); }});
  }})();

  // --------------------------------------------------------------------
  // 3) Round 40 — iPad / iOS one-time voice-quality hint.
  //    Show only if (a) device is iOS / iPadOS, (b) the Web Speech API
  //    is present but no Premium/Enhanced/Siri voice is installed, and
  //    (c) the user has not dismissed the hint in a previous visit.
  //    Logic preserved verbatim from the previous landing page.
  // --------------------------------------------------------------------
  (function () {{
    function isIOS() {{
      var ua = navigator.userAgent || '';
      if (/iPhone|iPod|iPad/.test(ua)) return true;
      // iPadOS 13+ masquerades as MacIntel; the touch-points check is
      // the only reliable way to tell it apart from a desktop Mac.
      return navigator.platform === 'MacIntel'
          && (navigator.maxTouchPoints || 0) > 1;
    }}
    if (!isIOS()) return;
    if (!('speechSynthesis' in window)) return;

    var STORAGE_KEY = 'aischool:ios-voice-hint-seen';
    try {{
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    }} catch (e) {{ /* private mode — proceed and just won't persist dismiss */ }}

    var banner  = document.getElementById('ios-voice-hint');
    var dismiss = document.getElementById('ios-voice-hint-dismiss');
    if (!banner || !dismiss) return;

    function hasHighQualityVoice() {{
      var voices = window.speechSynthesis.getVoices() || [];
      return voices.some(function (v) {{
        var tag = (v.name || '') + ' ' + (v.voiceURI || '');
        return /Premium|Enhanced|Siri/i.test(tag);
      }});
    }}

    function reveal() {{
      if (hasHighQualityVoice()) return;   // user already installed one — silent
      banner.classList.add('is-visible');
    }}

    // iOS Safari populates voices asynchronously. Try once now in case
    // they're already cached, then again on the voiceschanged event.
    window.speechSynthesis.getVoices();
    window.speechSynthesis.addEventListener('voiceschanged', reveal);
    // Defensive: also try after a short delay in case voiceschanged
    // never fires (some WebKit builds skip it when voices are local-only).
    setTimeout(reveal, 700);

    dismiss.addEventListener('click', function () {{
      banner.classList.remove('is-visible');
      try {{ localStorage.setItem(STORAGE_KEY, '1'); }} catch (e) {{}}
    }});
  }})();
</script>

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

    # --- Validate IELTS_IMAGES against discovered weeks + actual files -----
    if len(IELTS_IMAGES) != len(weeks) or len(weeks) != 40:
        print(
            f"error: IELTS_IMAGES has {len(IELTS_IMAGES)} entries but found "
            f"{len(weeks)} weeks; expected 40 of each.",
            file=sys.stderr,
        )
        return 2
    missing: list[str] = []
    for fname in IELTS_IMAGES:
        p = REPO / "images" / "landing" / fname
        if not p.exists():
            missing.append(fname)
    if missing:
        print(
            "error: missing landing images under images/landing/:\n  "
            + "\n  ".join(missing),
            file=sys.stderr,
        )
        return 2

    html_doc = render_html(weeks, args.bucket_base)
    out_path = Path(args.out)
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes, {len(weeks)} week cards)")
    print("Sample weeks:")
    for n, topic in weeks[:3]:
        print(f"  Week {n}: {topic}")
    print("  ...")
    for n, topic in weeks[-3:]:
        print(f"  Week {n}: {topic}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
