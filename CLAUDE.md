# CLAUDE.md — IELTS 40-Week Speaking Class HTMLs

## Source-of-truth workflow (Plan F, 2026-05-01) — READ THIS FIRST

The canonical Week 1 files live in **dedicated folders** — NOT in the root or `Interactive/`:

- `Week 1 PDF Base/Week_1_Lesson_Plan.html` — printable PDF base (with embedded fonts)
- `Week 1 Interactive/Week_1_Lesson_Plan.html` — interactive (with embedded fonts + TTS/AI widgets)

**Edit only those.** The legacy root `Week_1_Lesson_Plan.html` and `Interactive/Week_1_Lesson_Plan.html` are STAGING / backup until the user explicitly says "fan out". Don't run `parse_data.py` for Week 1 — it would silently overwrite our edits via the lessons/ → root cp step (this is the documented Plan E footgun).

### When to update which canonical file

| Edit type | What to update |
|---|---|
| **Visual / structural change** (banner, padding, layout, cover, content) | Edit `Week 1 PDF Base/Week_1_Lesson_Plan.html` AND mirror to `Week 1 Interactive/Week_1_Lesson_Plan.html` |
| **Interactive-only change** (TTS button, AI correction, recorder, karaoke, network handler) | Edit ONLY `Week 1 Interactive/Week_1_Lesson_Plan.html` |

### Fan-out (only when user says "fan out")
The 4 future fan-out passes will propagate canonical Week 1 → Weeks 2-40:
1. IGCSE PDF Base
2. IGCSE Interactive
3. IELTS PDF Base: `Week 1 PDF Base/Week_1_Lesson_Plan.html` → all 40 root Week_NN_Lesson_Plan.html files (likely via updated parse_data.py)
4. IELTS Interactive: `Week 1 Interactive/Week_1_Lesson_Plan.html` → all 40 Interactive Week_NN_Lesson_Plan.html files

## Embedded fonts (Plan F)
- 5 fonts base64-embedded at the top of the first `<style>` in each canonical file: Playfair Display 700, Montserrat 400/700, Lato 400/700.
- Source woff2 files live in `scripts/fonts/`, downloaded by `scripts/fetch_fonts.py` (lives in IGCSE repo; mirrors to BOTH).
- `scripts/build_inline_fonts.py` regenerates `scripts/fonts/_inline_font_face.css` (the base64 block).
- The Google Fonts `<link rel="stylesheet">` is kept as a backup but no longer required for rendering.

## Iteration workflow (TOKEN-CRITICAL)
- **NEVER run `parse_data.py` to regenerate all 40 weeks during iteration.** Canonical Week 1 files live in dedicated folders; edit them directly.
- Fan out to Weeks 2-40 ONLY when user says "fan out" or "publish".
- Work in small, testable steps.

## ⚠️ parse_data.py footgun
- `parse_data.py` reads Week_1_Lesson_Plan.html as template, generates `lessons/Week_*.html`, then expects `cp lessons/* .` to publish. If Week_1_Lesson_Plan.html had local edits NOT yet applied to all weeks, the lessons/ output OVERWRITES Week_1_Lesson_Plan.html — silently wiping local-only changes (e.g. cover font-family additions). Always commit before parse_data.py.
- Selectors at lines 269/287/295/363/380/388 use `find('h4', ...)` — these were `find('h2', ...)` before Plan D L2 fix. Don't switch back to h2.

## CSS cascade gotcha
- Two `<style>` blocks: main + `<style id="cover-overrides">` (later in head). The override block wins for cover classes. Edit cover styles in BOTH blocks (or just the override block) to avoid stale font-family inheritance.

## Cover typography (matches IGCSE)
- Google Fonts: `family=Montserrat:wght@400;700&family=Playfair+Display:wght@700&family=Lato:wght@400;700`.
- Title (`.cover-title-large`): Playfair Display 700 (NOT italic).
- Subtitle (`.cover-subtitle`): Montserrat 700 uppercase (was Playfair italic — too ornate).
- Top-label / week / footer: Montserrat 700.

## Card padding
- `:root { --card-padding: 12px }`. Avoid inline `padding:` overrides on `.card`.

## h2 → h4 (Plan D L2)
- Section headings use `<h4>`. Cover title is exempt (`<h2 class="cover-title-large">` — kept for parse_data.py compatibility).
