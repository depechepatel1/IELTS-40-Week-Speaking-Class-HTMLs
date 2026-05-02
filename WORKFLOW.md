# IELTS Course — Print + Digital Workflow

This repo produces TWO outputs from a single set of base HTML lesson plans:

1. **Print PDFs** — `Week_*_Lesson_Plan.html` → Playwright batch-converted to A4 PDFs → sent to printer for hardcopy student workbooks. **Must NOT contain** speaking buttons, recording widgets, AI correction UI, or any other digital-only feature.
2. **Interactive HTMLs** — same `Week_*_Lesson_Plan.html` files → run through `scripts/make_interactive.py` → emitted to `Interactive/` with TTS, AI correction, recorders, textareas, draggable spider-leg editing, etc. → uploaded to OSS for student access.

The two outputs share the SAME source HTMLs. The injection of interactive features is **non-destructive** — base files in the repo root are NEVER modified by `make_interactive.py`.

---

## The boundary that keeps it simple

```
  ┌─────────────────────────┐
  │  Week_*_Lesson_Plan.html │ ──────────────────────────┐
  │  (BASE, in repo root)    │                           │
  │                          │                           │
  │  Inline <style> block:   │                           │
  │  - print-pure layout     │                           │
  │  - Q6 .q-tall class      │                           │
  │  - horizontal scaffold   │                           │
  │    bullets               │                           │
  └────────┬─────────────────┘                           │
           │                                             │
   ┌───────┘                                             │
   │ batch_convert_pdf.py                                │ make_interactive.py
   │ (Playwright, headless                               │ (regex-based, idempotent)
   │  Chromium → A4 PDF)                                 │
   ▼                                                     ▼
  Interactive/Week_*.pdf                          Interactive/Week_*_Lesson_Plan.html
  (sent to printer)                              (uploaded to OSS for students)
                                                          │
                                                          ▼
                                                  All print-pure rules INHERITED
                                                  (base <style> kept in place)
                                                  + interactive overlay layered
                                                  ON TOP via inserted_css.css +
                                                  inserted_script.js
```

---

## CSS partitioning rule — one source of truth per visual rule

| Where the CSS lives | Belongs there if… | Selectors must… |
|---|---|---|
| Base template's inline `<style>` block | The rule has a **print-visible effect** — typography, page layout, card heights, bullet arrangement, spider-grid sizing of fixed pre-baked content | Match **base-HTML markup only**. Never reference `[contenteditable]`, `[data-q-id]`, `.q-write-host`, `.voice-recorder-container`, or any other interactive marker. |
| `scripts/templates/inserted_css.css` | The rule styles **overlay-only** elements — recorder widget, textarea overlay, AI button-rows, contenteditable focus outline | May freely use `:has()` and interactive markup. The overlay container itself must be `display: none` in `@media print`. |

A rule with a print-visible effect must NOT be duplicated across both files — it's a recipe for them to drift out of sync.

`scripts/migrate_print_css.py` (IELTS) is the historical artefact that moved the two original duplicates (horizontal scaffold-text bullets + Q6 `.q-tall`) from `inserted_css.css` into the 40 base Week files. It's idempotent and re-runnable if any base files lose those rules.

---

## Standard yearly workflow

### Phase 1 — content refresh (next-year edition)

When you draft new lesson content for the 40 weeks (in a master JSON or Excel):

```bash
# 1. Update master content store (JSON / Excel — out of scope for this repo today)

# 2. Regenerate 40 base Week_*_Lesson_Plan.html files from the master content
#    NOTE: An IELTS-side generator analogous to IGCSE's `generate_course.py`
#    is not yet built. Until it is, this step is manual editing of the base
#    files. See `scripts/migrate_print_css.py` for the kind of regex-based
#    transformation a generator could perform.

# 3. Sanity-check that NO interactive markers slipped into the base files
git grep -nE '(voice-recorder-container|vr-inline|data-recorder-id|q-write-host|contenteditable|<!-- AI-INTERACTIVE-V1 -->)' \
    -- 'Week_*_Lesson_Plan.html'
# (Should return zero matches.)

# 4. Confirm the print-relevant CSS migration is in place on every base file
python scripts/migrate_print_css.py
# Idempotent — should report all 40 already migrated.
```

### Phase 2 — print PDF generation

```bash
# Renders each Week_*_Lesson_Plan.html → matching .pdf via Playwright
# (headless Chromium with @media print rules applied).
python scripts/batch_convert_pdf.py
# Output: Interactive/Week_*_Lesson_Plan.pdf  (or whichever folder the
# script targets — see its --help output)

# Send PDFs to printer.
```

### Phase 3 — digital interactive HTML generation

```bash
# Substitute env vars / paths to your real FC + OSS deployment.
python scripts/make_interactive.py \
    --in . \
    --out Interactive \
    --endpoint https://YOUR-FC-ENDPOINT.cn-beijing.fcapp.run \
    --bucket-base https://YOUR-OSS-BUCKET.oss-cn-beijing.aliyuncs.com/ielts-interactive

# Upload Interactive/Week_*_Lesson_Plan.html (and pronunciations.json) to OSS
# for student access via aischool.studio.
```

---

## Critical files

- `Week_*_Lesson_Plan.html` × 40 — base templates. Print-pure, hand-authored today.
- `scripts/make_interactive.py` — non-destructive interactive injector (5 insertions: CSS, draft-page overlay, spider-leg editing + map recorders, Q1-Q6 textarea overlay + recorders, JS).
- `scripts/templates/inserted_css.css` — interactive-overlay CSS only. **Print-relevant rules belong in the base files, not here.**
- `scripts/templates/inserted_script.js` — TTS, AI client (with retry+backoff+jitter), MediaRecorder (with LRU IndexedDB eviction), diff engine, vocab IPA tooltips.
- `scripts/templates/voice_recorder_widget_inline.html` + `polished_section_overlay.html` + `draft_section_overlay.html` — the HTML fragments injected.
- `scripts/migrate_print_css.py` — idempotent base-template CSS migrator. Run after any content refresh to ensure horizontal-bullet + Q6-tall rules are in place.
- `scripts/batch_convert_pdf.py` — Playwright PDF batch converter.
- `scripts/fonts/Caveat-400.woff2` + `IndieFlower-400.woff2` — embedded base64 into each interactive HTML by `make_interactive.py`. These are NOT in the base files (not needed for print since handwriting fonts are only used by interactive overlay textareas).
- `function-compute/` — backend AI proxy (Zhipu API client). Deployed via `s deploy`.

---

## What lives where — quick reference

| Concern | Lives in | Why |
|---|---|---|
| Print page layout, A4 sizing, card spacing | Base file inline `<style>` | Print-visible |
| Q1-Q6 horizontal scaffold-text bullets | Base file inline `<style>` (`.card.compact ul.scaffold-text`) | Print-visible |
| Q6 +20px taller | Base file inline `<style>` (`.card.compact.q-tall`) + `q-tall` class on Q6 div | Print-visible; class added by `migrate_print_css.py` |
| Recorder widget styles | `inserted_css.css` | Overlay; hidden in print |
| Textarea overlay over `.lines` | `inserted_css.css` | Overlay; hidden in print |
| AI button-rows | `inserted_css.css` | Overlay; hidden in print |
| Embedded handwriting fonts | `make_interactive.py` injects them via `inserted_css.css` `@font-face` | Only used by overlay textareas + AI markup |
| TTS, AI fetch, recorder JS | `inserted_script.js` | Behaviour; not needed for print |
| Recordings, drafts, AI cache | Browser `IndexedDB` / `localStorage` | Per-student local; never uploaded |

---

## Scalability — designed for one-and-done

Two scenarios that would otherwise need manual ops are handled by the runtime itself:

- **iOS Safari ~1 GB IndexedDB cap.** `inserted_script.js` runs LRU eviction before every recording save — oldest 60+ recordings are silently pruned, plus an additional sweep when `navigator.storage.estimate()` reports < 20% free quota. Combined with `navigator.storage.persist()` requested at page load to prevent browser-initiated eviction. No teacher / student intervention needed.
- **FC concurrency thundering herd at start-of-class.** The AI fetch path uses pre-request jitter (0-500 ms), exponential backoff retry on 429/503/5xx with per-retry jitter, and a 45 s per-attempt abort timeout. 200 students hitting "Correct with AI" within the same second spread across half a second instead of stampeding the FC concurrency cap.
- **FC concurrency cap raise.** Default ~100 → raise to 500 in the FC dashboard once. (Marker: this is the only change that lives outside this repo. See `function-compute/README.md` if present, or the s.yaml.)
- **FC cold start.** Mitigate via the scheduled `/health` warmup trigger configured in `function-compute/s.yaml`.

---

## When in doubt

- **Adding a new visual rule.** Ask yourself: "should the printed PDF show this?" If yes → base file `<style>`. If no → `inserted_css.css`.
- **Adding a new interactive widget.** Always goes via a template in `scripts/templates/` + a regex insertion in `scripts/make_interactive.py`. The base files stay print-pure.
- **Changing a rule that should affect both.** Edit it in the base file `<style>`. The interactive HTML inherits the base `<style>` automatically (it's preserved in the `Interactive/` output).
