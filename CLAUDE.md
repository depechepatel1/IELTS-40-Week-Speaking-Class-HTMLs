# CLAUDE.md — IELTS 40-Week Speaking Class

Last reorg: **2026-05-01** (canonical-folder workflow + filename standardization + CDN-only public surface).

## TL;DR

- **Canonical Week 1** lives at `canonical/pdf-base/Week_01.html` and `canonical/interactive/Week_01.html`. Edit those for Week 1 changes.
- **Weeks 2-40** are generated from canonical Week 1 via `parse_data.py` + `make_interactive.py`. Don't edit them directly during iteration.
- **Filename convention**: `Week_NN.html` (zero-padded, no `_Lesson_Plan` suffix).
- **Public URL**: `https://ielts.aischool.studio/Week_NN.html` (CDN-fronted; OSS bucket is private and not directly reachable).

## Directory layout

```
.
├── canonical/                  ← Source of truth for Week 1
│   ├── pdf-base/Week_01.html       (printable PDF base)
│   └── interactive/Week_01.html    (with TTS / AI / recording widgets)
├── Week_01.html ... Week_40.html   ← PDF base × 40, regenerated from canonical
├── Interactive/Week_01.html ... Week_40.html  ← Interactive × 40, regenerated
├── parse_data.py                   ← canonical PDF base → Week_NN.html × 40
├── master Curiculum.json           ← per-week content (cue cards, model answers, vocab)
├── pronunciations.json             ← IPA tooltips data (uploaded to OSS)
├── images/                         ← course_pipeline_v2/v3/v4.png used in Week pages
└── scripts/
    ├── make_interactive.py         ← Week_NN.html → Interactive/Week_NN.html
    ├── upload_to_oss.py            ← upload to aischool-ielts-bj at bucket root
    ├── bind_custom_domain.py       ← DNS + OSS CNAME + cert provisioning
    ├── build_pronunciations.py     ← regenerate pronunciations.json from corpus
    ├── build_landing_page.py       ← generate course-index landing page
    ├── check_cert_expiry.py        ← weekly cron: warn at <30 days to cert expiry
    ├── fonts/                      ← woff2 sources for embedded base64 @font-face
    └── templates/                  ← inserted_script.js, inserted_css.css, polished_section_overlay.html
```

## When to edit what

| Edit type | Where to edit |
|---|---|
| Week 1 visual / structural change (cover, banner, layout, content) | `canonical/pdf-base/Week_01.html` AND `canonical/interactive/Week_01.html` |
| Interactive-only change (TTS button, AI correction overlay, recorder) | `canonical/interactive/Week_01.html` only |
| Pipeline-wide CSS or JS change | `scripts/templates/inserted_css.css` / `inserted_script.js` |
| Per-week content (cue cards, model answers, vocab, idioms) | `master Curiculum.json` |
| Cover background image | `canonical/pdf-base/Week_01.html`'s `<style id="cover-overrides">` block |

## Fan-out workflow (only when user says "fan out" or "publish")

```bash
python parse_data.py                                        # canonical → Weeks 2-40 PDF base
cp lessons/Week_*.html . && rm -rf lessons                  # promote to root
python scripts/make_interactive.py \
    --in . --out Interactive \
    --endpoint https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run \
    --bucket-base https://ielts.aischool.studio
python scripts/upload_to_oss.py                             # to aischool-ielts-bj at bucket root
```

The `--bucket-base` value is critical: it's baked into every Interactive HTML as the URL prefix for `pronunciations.json` and other resources. Must match the public CDN domain (no path prefix).

## Embedded fonts (Plan F, 2026-05-01)

5 base64-encoded woff2 fonts (~145 KB total) live in `<style>` at the top of every canonical Week 1 file:
- Playfair Display 700 (cover title)
- Montserrat 400/700 (cover labels, banners)
- Lato 400/700 (body text — for IGCSE parity)

Source files: `scripts/fonts/*.woff2`. Regenerate the embedded block via `scripts/build_inline_fonts.py`.

The Google Fonts `<link>` is also kept as a backup, but rendering doesn't depend on it (handles network restrictions in China).

## URL contract (CDN, public)

```
https://ielts.aischool.studio/Week_NN.html              ← students/teachers
https://ielts.aischool.studio/pronunciations.json       ← IPA tooltips loaded by Week pages
https://ielts.aischool.studio/images/*.png              ← course pipeline images
```

OSS bucket `aischool-ielts-bj` is **private** (Block Public Access enabled). Only the CDN can read it via origin-pull authentication. There is **no** prefix path (`/ielts-interactive/` is gone) and **no** legacy direct-OSS URL.

## Cert renewal

DigiCert DV cert (id `24643392`, issued via Aliyun CDN's free DV) expires **2026-07-24**. CDN auto-renewal is enabled — but verify ~30 days out via `python scripts/check_cert_expiry.py`. Calendar reminder set for July 1.

## Iteration workflow rules

- **NEVER regenerate all 40 weeks during iteration.** Canonical files in `canonical/` are the editing surface. Fan-out only when user says "fan out" or "publish".
- **Don't run `parse_data.py` for Week 1 alone.** Edit `canonical/pdf-base/Week_01.html` directly.
- **Don't edit root-level `Week_NN.html` files directly** (they get overwritten on next fan-out). Edit canonical instead.
- **Work in small, testable steps**. Verify Week 1 visually before fan-out.

## CSS architecture notes

- The canonical file's `<head>` contains TWO `<style>` blocks:
  1. Main (line ~16): all base styles, including print-mode rules (`.draft-page > ...`)
  2. `<style id="cover-overrides">` (line ~508): cover-page-specific styles (the cover background image, Round 15/16 typography). This block intentionally OVERRIDES the main `<style>`'s `.cover-page` linear-gradient with the photo-cover.
- `parse_data.py` does NOT strip-and-reinject the cover-overrides block (this was the Round-5-vs-Round-15/16 footgun). The block flows through BeautifulSoup's read/serialize cycle untouched, so all 40 generated weeks inherit identical cover CSS to canonical.

## File-naming reference

- `Week_NN.html` for both PDF base and Interactive (zero-padded, no `_Lesson_Plan` suffix).
- LESSON_KEY in inserted_script.js = filename stem, e.g. `Week_05`. Recordings keyed `Week_05:q1`.
- Historical `Week_<N>_Lesson_Plan.html` files were renamed 2026-05-01 (no production URLs given out under that name).
