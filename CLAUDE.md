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

## Editing Week 1 → fan-out workflow (next-year curriculum updates)

The pipeline is **drift-free by design**: `parse_data.py` uses BeautifulSoup to
mutate ONLY per-week data nodes (cover heading, week-tag spans, vocab tables,
cue cards, model answers, Part 3 questions). Everything else — cover CSS,
embedded fonts, footer, page-numbering rules, body styling — flows through
the parse/serialize cycle unchanged. So a single canonical edit propagates
to all 40 weeks on next fan-out.

For visual / structural changes:

1. Edit `canonical/pdf-base/Week_01.html` for the print-mode change.
2. Mirror the change in `canonical/interactive/Week_01.html` if it affects
   shared layout (cover CSS, fonts, headings, footers, etc.).
3. From repo root: `python scripts/publish.py`
   This single command runs all 7 pipeline steps (parse → promote → bake
   interactive → landing page → upload → cert check → drift verification).
4. Confirm the post-publish drift summary reads `[OK] Week_05.html — 0 drift`
   (and same for Week_22, Week_38). If drift shows, investigate before
   considering the change live.
5. Smoke-test: open `https://ielts.aischool.studio/Week_05.html` in browser.

For per-week curriculum data changes (Part 2 / Part 3 questions, vocab,
homework, themes), edit `master Curiculum.json` (or the per-week JSONs
in repo root) and rerun publish.py — no canonical edit needed.

To verify drift independently (e.g., after a manual edit you're unsure about):
`python scripts/verify_no_drift.py` — exit 0 = clean, exit 1 = drift detected.

## Fan-out workflow — manual fallback

`scripts/publish.py` is the master command above. If you need to run steps
individually (debugging, partial fan-out):

```bash
python parse_data.py                                        # canonical → Weeks 2-40 PDF base
cp lessons/Week_*.html . && rm -rf lessons                  # promote to root
python scripts/make_interactive.py \
    --in . --out Interactive \
    --endpoint https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run \
    --bucket-base https://ielts.aischool.studio
python scripts/upload_to_oss.py                             # to aischool-ielts-bj at bucket root
python scripts/verify_no_drift.py                           # confirm 0 drift in sampled weeks
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

## Rotating-password gate + admin console (Round 29 — 2026-05-03)

Every Interactive `Week_*.html` is gated by a SHA-256 password the
teacher rotates whenever desired. **Same password** unlocks both
`ielts.aischool.studio` and `igcse.aischool.studio` (shared cohort).
Threat model is casual link-sharing only — view-source bypass is
acceptable. Implementation: `scripts/templates/password_gate.html`
+ `insertion_7_password_gate` in `make_interactive.py`.

**Admin console (rotate from any browser):**
- URL: <https://ielts.aischool.studio/admin/> (or the IGCSE equivalent — both work, same UI, same FC backend)
- Login: the **permanent admin password** (set as `ADMIN_PASSWORD_HASH` env var on the FC; SHA-256 hex of the chosen plaintext)
- Then enter the new student password + confirm → click **Save new password** → the FC writes `_pwhash.json` to BOTH bucket roots → students see the gate again on next page load
- Distribute the new student password via WeChat / class group

**Initial setup (one-time, before first deploy):**

```bash
# 1. Pick a permanent admin password and hash it
python -c "import hashlib; print(hashlib.sha256(b'YOUR-ADMIN-PASSWORD-HERE').hexdigest())"

# 2. Generate a JWT secret (any 32+ random hex bytes)
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Create a RAM user with PutObject on aischool-ielts-bj + aischool-igcse-bj only
#    (Aliyun Console → RAM → Users → Create) and capture its keys.

# 4. Set FC env vars in your shell BEFORE `s deploy`:
$env:ADMIN_PASSWORD_HASH = "<from step 1>"
$env:JWT_SECRET = "<from step 2>"
$env:ALIYUN_OSS_ACCESS_KEY_ID = "<RAM user id>"
$env:ALIYUN_OSS_ACCESS_KEY_SECRET = "<RAM user secret>"
# (ZHIPU_API_KEY is already set if you've deployed before.)

# 5. Deploy FC with the new env vars + ali-oss dep
cd function-compute
s deploy --use-local --assume-yes

# 6. Publish HTMLs (which now bake in the gate snippet) + admin page
cd ..
python scripts/publish.py

# 7. Open https://ielts.aischool.studio/admin/, sign in, set the
#    initial student password (e.g. "spicy-river-19"), submit. Done.
```

**To rotate the student password:** open the admin URL, sign in, type
the new password, submit. No `s deploy`, no `publish.py`, no terminal.

**To rotate the admin password:** edit `function-compute/s.yaml`'s
`ADMIN_PASSWORD_HASH` (or the env var the deploy reads), then
`s deploy --use-local --assume-yes`. Forgetting it requires the same.

**Recovery if locked out completely:** all auth state lives in FC env
vars; redeploy with new values resets the system. Buckets are
unaffected.

## function-compute/node_modules/ lives on D:\ (not OneDrive)

OneDrive cannot sync deep `node_modules/` trees (some packages contain
files OneDrive's policy refuses to mirror, e.g.
`jstoxml/.github/workflows/unit-tests.yml`). To work around this,
`function-compute/node_modules/` is a Windows directory junction
pointing to **`D:\aischool-fc-node_modules`** — the actual package
files live there, never in OneDrive.

If `npm install` is rerun and the junction is broken or missing,
recreate it:

```bash
cd "C:/Users/depec/OneDrive/Desktop/IELTS 40 Week Speaking Class HTMLs/IELTS-40-Week-Speaking-Class-HTMLs/function-compute"
# If a real node_modules dir exists, move its contents to D:\ first:
mkdir -p /d/aischool-fc-node_modules
mv node_modules/* /d/aischool-fc-node_modules/ 2>/dev/null || true
mv node_modules/.* /d/aischool-fc-node_modules/ 2>/dev/null || true
rmdir node_modules
# Re-create the junction:
cmd //c "mklink /J node_modules D:\\aischool-fc-node_modules"
```

`s deploy` works transparently through the junction (verified
2026-05-03 deploy `ielts-arrection-nafrghqpzj`).

## Cert renewal

**Wildcard cert** `*.aischool.studio` (cert id `24792685`, Wosign DV, expires **2026-11-17**, auto-renewing) covers `ielts.aischool.studio`, `igcse.aischool.studio`, and `lessons.aischool.studio` (legacy). Subscription-style: Aliyun rotates the cert mid-cycle automatically; only the subscription itself needs manual renewal (next: 2027-04-03 for the 2027-05-03 expiry). Verify health any time via `python scripts/check_cert_expiry.py`. To bind to a NEW subdomain in future, see the snippet in REORG_STATE.md.

## Iteration workflow rules

- **NEVER regenerate all 40 weeks during iteration.** Canonical files in `canonical/` are the editing surface. Fan-out only when user says "fan out" or "publish".
- **Don't run `parse_data.py` for Week 1 alone.** Edit `canonical/pdf-base/Week_01.html` directly.
- **Don't edit root-level `Week_NN.html` files directly** (they get overwritten on next fan-out). Edit canonical instead.
- **Work in small, testable steps**. Verify Week 1 visually before fan-out.

## Bug-fix preference (user-stated 2026-05-03)

When a bug is found, scan the code carefully and identify the **root cause in the source** — fix it there. Do NOT apply a patch on top of the symptom. This codebase will be handed off to a developer; clean source fixes are easier to identify and work with than layered patches.

Examples of doing it right (recent precedent):
- Week 2 grammar overflow → root cause was a stray editor draft in `homework_plan.json` (6 items vs expected 5). Fix: clean the data + add `verify_homework_data.py` validation. Did NOT add `max-height + overflow:auto` CSS (which would have hidden the symptom while keeping the broken data).
- Cover text "MASTERCLASS" appearing in fanned-out weeks despite Round 18 canonical change → root cause was hardcoded string at `parse_data.py:124`. Fix: update the string in source. Did NOT post-process generated HTMLs.

## CSS architecture notes

- The canonical file's `<head>` contains TWO `<style>` blocks:
  1. Main (line ~16): all base styles, including print-mode rules (`.draft-page > ...`)
  2. `<style id="cover-overrides">` (line ~508): cover-page-specific styles (the cover background image, Round 15/16 typography). This block intentionally OVERRIDES the main `<style>`'s `.cover-page` linear-gradient with the photo-cover.
- `parse_data.py` does NOT strip-and-reinject the cover-overrides block (this was the Round-5-vs-Round-15/16 footgun). The block flows through BeautifulSoup's read/serialize cycle untouched, so all 40 generated weeks inherit identical cover CSS to canonical.

## File-naming reference

- `Week_NN.html` for both PDF base and Interactive (zero-padded, no `_Lesson_Plan` suffix).
- LESSON_KEY in inserted_script.js = filename stem, e.g. `Week_05`. Recordings keyed `Week_05:q1`.
- Historical `Week_<N>_Lesson_Plan.html` files were renamed 2026-05-01 (no production URLs given out under that name).
