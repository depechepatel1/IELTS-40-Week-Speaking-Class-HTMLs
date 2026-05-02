# Reorg state — Batch B + email-button work COMPLETE 2026-05-02

Path A executed: committed local state first, then resumed Batch B
Steps 2-5 cleanly. The reorg-paused state is now fully reconciled with
the email-button feature added during the pause.

## Current state (post Path A)

### Local repos
- IELTS HEAD: `feat/brainstorming-q-recorders` `afab7fb`
  ("Add email-recordings button + finalize Batch B local state")
- IGCSE HEAD: `feat/igcse-interactive` `d16a9a4`
  ("Add email-recordings button + finalize Batch B local state")

### OSS bucket layout (final)

```
aischool-ielts-bj/                        aischool-igcse-bj/
  Week_01.html ... Week_40.html (40)        Week_01.html ... Week_40.html (40)
  pronunciations.json                       images/course_pipeline.png
  images/course_pipeline.png                  (single image, no version suffix)
  images/course_pipeline_v2.png
  images/course_pipeline_v3.png
  images/course_pipeline_v4.png
  index.html  (landing page — needs regen with new URLs; see Out-of-scope)
```

### What's deployed publicly NOW

```
https://lessons.aischool.studio/Week_NN.html      ← IELTS, 40 files, 200 OK via CDN
https://lessons.aischool.studio/pronunciations.json
https://lessons.aischool.studio/images/...
https://igcse.aischool.studio/Week_NN.html        ← IGCSE, 40 files, 200 OK via CDN
https://igcse.aischool.studio/images/...
```

The CDN serves all of these at HTTPS via the existing DigiCert DV certs:
- IELTS cert: `24643392` (lessons.aischool.studio) — expires 2026-07-24
- IGCSE cert: `24762111` (igcse.aischool.studio) — expires 2026-07-29

Both have CDN auto-renewal enabled (verify in Aliyun console).

### Email button (✉️) is live everywhere

- **IELTS**: bottom-right of "🎙️ 4. Recording Challenge" card on the
  homework page. All 40 weeks.
- **IGCSE**: bottom-right of "Section 13. Before Next Week's Lesson"
  floating window. All 40 weeks.
- Click → enumerate IndexedDB recordings for this week's `LESSON_KEY` →
  build a STORED-mode .zip in browser → download → open mailto: with
  pre-filled subject + body (filenames listed) → completion panel
  appears with "Re-open email" + "Copy details" fallback buttons.
- No backend dependency. No PII transit. Audio stays in the student's
  browser until they manually attach the zip in their mail client.

## Steps completed

| # | Step | Result |
|---|---|---|
| 1 | IGCSE PDF base regen + Interactive rebuild + post-merge | ✅ Done as part of email-button rebuild |
| 2 | IELTS upload to bucket root | ✅ 40 weeks + pronunciations.json + 4 images uploaded |
| 3 | IGCSE upload to bucket root | ✅ 40 weeks + 1 image uploaded; upload script fixed (PREFIX="", canonical override removed) |
| 4 | Delete legacy prefix files in OSS | ✅ 40 IELTS `ielts-interactive/*` + 44 IGCSE `igcse-interactive/*` (incl. 4 v6/v7/v8/v9 backups) + 40 IELTS root-level `Week_<N>_Lesson_Plan.html` legacy orphans |
| 5 | Unbind orphan OSS CNAMEs | ✅ `lessons.aischool.studio` and `igcse.aischool.studio` unbound from their respective buckets; CDN still serves traffic (verified 200 OK on multiple paths) |
| 6 | Commit Batch B | ✅ Single commit per repo: `afab7fb` (IELTS) + `d16a9a4` (IGCSE) |

## Steps deferred

### Step 7 — Subdomain rename `lessons.aischool.studio` → `ielts.aischool.studio`

For symmetric naming with `igcse.aischool.studio`. **NOT urgent** — the
existing `lessons.aischool.studio` works fine and serves the
post-reorg content correctly. Symbolic improvement only.

When ready: paste this prompt into Claude cowork:

```
TASK: Add `ielts.aischool.studio` as a new CDN domain on Aliyun CDN
with origin = `aischool-ielts-bj.oss-cn-beijing.aliyuncs.com`.
Provision a free DV cert (mirror what was done for `igcse.aischool.studio`
and the existing `lessons.aischool.studio`). Add DNS CNAME via Alidns
API from `ielts.aischool.studio` to the CDN edge endpoint. After
verification (HTTPS + content load), DECOMMISSION
`lessons.aischool.studio` (delete CDN domain config + delete DNS
records). ICP filing 浙ICP备2026026030号-1 covers all aischool.studio
subdomains. Bucket `aischool-ielts-bj` is public-read. Credentials in
env: ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET. Pipeline config
in `IELTS-40-Week-Speaking-Class-HTMLs/pipeline.yaml`.
```

After cowork completes Step 7, we'll need to:
- Re-run `make_interactive.py` with `--bucket-base https://ielts.aischool.studio`
  (already that value — but re-bake so any cert refs update)
- Re-upload Interactive files to the bucket
- Update `pipeline.yaml` `cdn.domain` field from `lessons.aischool.studio`
  to `ielts.aischool.studio`
- Run `python scripts/check_cert_expiry.py` for the new cert

### Step 8 — Bucket → private + CDN origin-pull auth

Architectural correctness improvement; non-blocking. Currently both
buckets have `block_public_access: false` (IELTS) and `false` (IGCSE
after we toggled it for the upload). For maximum security, both should
be `true` with CDN configured to read via RAM-based origin-pull auth.

This is complex via API — recommend doing via Aliyun console:
1. CDN console → each domain → Origin → enable origin-pull authentication
   (RAM-based, scope to bucket-read-only)
2. OSS console → each bucket → Block Public Access ON
3. Verify CDN still serves (CDN hits origin via authenticated request)

### Step 9 (new, low priority) — Regenerate IELTS landing page

`https://lessons.aischool.studio/index.html` exists and links to the
old `Week_<N>_Lesson_Plan.html` filenames. Those files are now deleted,
so the landing-page links 404. Either:
- Run `python scripts/build_landing_page.py` to regenerate with new
  `Week_NN.html` URL pattern, then re-upload
- OR delete `index.html` if no one navigates to the bucket root

Lowest priority — students don't access the landing page in normal
flow. Can be deferred to next session.

## Quick verification commands

```bash
# Confirm latest commits
cd "IELTS-40-Week-Speaking-Class-HTMLs" && git log --oneline -1
cd "IGCSE Github Files" && git log --oneline -1

# Confirm CDN serves new content
curl -sI https://lessons.aischool.studio/Week_05.html | head -1
curl -sI https://igcse.aischool.studio/Week_05.html | head -1

# Confirm legacy paths DON'T serve
curl -sI https://lessons.aischool.studio/ielts-interactive/Week_05_Lesson_Plan.html | head -1   # expect 404
curl -sI https://igcse.aischool.studio/igcse-interactive/Week_05.html | head -1                  # expect 404

# Smoke test cert expiry
python scripts/check_cert_expiry.py
```

## Ports of call after each session restart

When resuming work later:
1. `git log --oneline -3` in both repos to confirm HEAD
2. `git status --short | wc -l` should be 0 (or just gitignored noise)
3. HTTP HEAD a sample CDN URL to confirm production health
4. Read CLAUDE.md to refresh on architecture
