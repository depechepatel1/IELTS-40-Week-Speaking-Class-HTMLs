# Reorg state — paused 2026-05-01 mid-Batch B

User initiated session pause for ~2hr to reset rate limits. This document
captures exactly where we are so the next session resumes cleanly.

## What's done

### Batch A — local cleanup (committed in both repos)
- IELTS commit: `feat/brainstorming-q-recorders` HEAD
- IGCSE commit: `feat/igcse-interactive` HEAD

Both repos now have:
- `canonical/pdf-base/Week_01.html` and `canonical/interactive/Week_01.html` as source-of-truth
- `pipeline.yaml` config (single source of truth for endpoints, bucket, cert IDs)
- `scripts/check_cert_expiry.py` (weekly cron-able)
- Updated `CLAUDE.md` describing new architecture
- Cleaned up backup/version-suffix/debug files
- IELTS-only: filenames standardized to `Week_NN.html` (zero-padded, no `_Lesson_Plan` suffix)
- IELTS-only: `parse_data.py` footgun (hardcoded css_overrides re-injection) removed
- IGCSE-only: `scripts/post_merge_section_7_8.py` extracted from inline post-process

### Batch B partial
- IELTS: `make_interactive.py` re-baked all 40 Interactive HTMLs with new bucket-base
  `https://ielts.aischool.studio` (no path prefix). **UNCOMMITTED** — `git status`
  shows `M Interactive/Week_*.html × 40`. Files are valid; they reference a URL
  that doesn't yet resolve (subdomain not provisioned — see Batch C).
- IGCSE: re-bake attempt FAILED (1/40 succeeded) due to pipeline ordering bug —
  reverted. State unchanged from Batch A commit.

## What's next when we resume

### Step 1: IGCSE PDF base regeneration (because post_merge already ran)

The IGCSE pipeline order matters. After `post_merge_section_7_8.py` runs, PDF
base has merged Sec 7+8, but `make_interactive.py` needs SEPARATE Section 7 to
inject the AI overlay. So the correct re-run is:

```bash
cd "C:\Users\depec\OneDrive\Desktop\IGCSE Github Files"
python generate_course.py                                    # regen PDF base (separate Sec 7/8)
python scripts/make_interactive.py \
    --in . --out Interactive \
    --endpoint https://ielts-ai-correct-exuelhswhc.cn-beijing.fcapp.run \
    --bucket-base https://igcse.aischool.studio              # NO prefix
python scripts/post_merge_section_7_8.py                     # merge in PDF base only
```

### Step 2: IELTS upload to bucket root (no prefix)

The IELTS Interactive files are already re-baked. Need to update `scripts/upload_to_oss.py`
to upload to bucket ROOT (not `ielts-interactive/` prefix), then run:

```bash
cd "C:\Users\depec\OneDrive\Desktop\IELTS 40 Week Speaking Class HTMLs\IELTS-40-Week-Speaking-Class-HTMLs"
python scripts/upload_to_oss.py
```

This should upload:
- 40 Interactive/Week_NN.html → `aischool-ielts-bj/Week_NN.html` (root, no prefix)
- pronunciations.json → `aischool-ielts-bj/pronunciations.json` (root)
- images/*.png → `aischool-ielts-bj/images/*.png` (kept for self-referenced HTML)

### Step 3: IGCSE upload to bucket root

After Step 1, run IGCSE upload (script needs same root-not-prefix update):

```bash
cd "C:\Users\depec\OneDrive\Desktop\IGCSE Github Files"
python scripts/upload_to_oss.py
```

### Step 4: Delete legacy prefix files in OSS

The old `ielts-interactive/Week_*.html` and `igcse-interactive/Week_*.html` files
become orphan after Step 2-3. Delete them via Aliyun OSS console OR via:

```python
import os, oss2
auth = oss2.Auth(os.environ['ALIYUN_ACCESS_KEY_ID'], os.environ['ALIYUN_ACCESS_KEY_SECRET'])
for bucket_name, prefix in [
    ('aischool-ielts-bj', 'ielts-interactive/'),
    ('aischool-igcse-bj', 'igcse-interactive/'),
]:
    bucket = oss2.Bucket(auth, 'oss-cn-beijing.aliyuncs.com', bucket_name)
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        bucket.delete_object(obj.key)
        print(f"deleted {obj.key}")
```

Also delete the 4 orphan IGCSE backup files:
- `igcse-interactive/Week_01_v6_185702.html`
- `igcse-interactive/Week_01_v7_113420.html`
- `igcse-interactive/Week_01_v8_124624.html`
- `igcse-interactive/Week_01_v9_141607.html`

(All approved by user.)

### Step 5: Unbind orphan OSS CNAME bindings

Both buckets have OSS CNAMEs that are now orphaned (CDN handles all traffic):

```python
import os, oss2
auth = oss2.Auth(os.environ['ALIYUN_ACCESS_KEY_ID'], os.environ['ALIYUN_ACCESS_KEY_SECRET'])
for bucket_name, cname in [
    ('aischool-ielts-bj', 'lessons.aischool.studio'),
    ('aischool-igcse-bj', 'igcse.aischool.studio'),
]:
    bucket = oss2.Bucket(auth, 'https://oss-cn-beijing.aliyuncs.com', bucket_name)
    bucket.delete_bucket_cname(cname)
```

(All approved by user.)

### Step 6: Commit Batch B in both repos

### Step 7 (optional, deferred): Batch C — subdomain rename `lessons.aischool.studio` → `ielts.aischool.studio`

Recommended to delegate to Claude cowork via this prompt:

> TASK: Add `ielts.aischool.studio` as a new CDN domain on Aliyun CDN
> with origin = `aischool-ielts-bj.oss-cn-beijing.aliyuncs.com`. Provision
> a free DV cert (mirror what was done for `igcse.aischool.studio` and
> the existing `lessons.aischool.studio`). Add DNS CNAME via Alidns API
> from `ielts.aischool.studio` to the CDN edge endpoint. After verification
> (HTTPS + content load), DECOMMISSION `lessons.aischool.studio` (delete
> CDN domain config + delete DNS records). Same playbook used for the
> migration of `lessons.aischool.studio` to CDN; this just adds `ielts`
> alongside, then retires `lessons`. ICP filing 浙ICP备2026026030号-1
> covers all aischool.studio subdomains. Bucket `aischool-ielts-bj` is
> public-read. Credentials in env: ALIYUN_ACCESS_KEY_ID,
> ALIYUN_ACCESS_KEY_SECRET. Pipeline config in
> `IELTS-40-Week-Speaking-Class-HTMLs/pipeline.yaml`.

After cowork completes Batch C: run `scripts/check_cert_expiry.py` to
verify cert health, and update IELTS `pipeline.yaml` cert_id field with
the new cert.

### Step 8 (deferred): Batch D — bucket → private + CDN origin-pull auth

Architectural correctness improvement; non-blocking. Requires CDN
configuration that's complex via API. Recommend doing via Aliyun
console: each bucket → Block Public Access ON, each CDN domain →
Origin Pull → enable RAM-based auth.

## Quick sanity-check on resume

```bash
# Verify Batch A committed:
cd "IELTS-40-Week-Speaking-Class-HTMLs" && git log --oneline -1   # should show "Reorg: clean architecture..."
cd "IGCSE Github Files" && git log --oneline -1

# Verify IELTS uncommitted Batch B work:
cd "IELTS-40-Week-Speaking-Class-HTMLs" && git status --short | wc -l    # should be ~40 (Interactive/Week_*.html)
grep -c "ielts.aischool.studio" Interactive/Week_01.html                  # should be ≥1

# Verify IGCSE clean state:
cd "IGCSE Github Files" && git status --short | wc -l                     # should be 0 or just .gitignore'd files
```
