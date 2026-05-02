# Production state + improvement backlog (2026-05-02)

## What's live now

| Surface | URL | Status |
|---|---|---|
| IELTS landing page | https://lessons.aischool.studio/ | ✅ live, cache-control=300s |
| IGCSE landing page | https://igcse.aischool.studio/ | ✅ live, cache-control=300s |
| IELTS Week pages × 40 | https://lessons.aischool.studio/Week_NN.html | ✅ live, AI correction works |
| IGCSE Week pages × 40 | https://igcse.aischool.studio/Week_NN.html | ✅ live, AI correction works |
| Function Compute | https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run | ✅ live, glm-4-flash, 7s avg |
| Cert (IELTS) | DigiCert DV id `24643392` | expires 2026-07-24 (83 days) |
| Cert (IGCSE) | DigiCert DV id `24762111` | expires 2026-07-29 (88 days) |

## What changed in this round (2026-05-02)

- **Skip-unchanged uploads**: `upload_to_oss.py` compares local MD5 +
  expected Cache-Control vs OSS state, skips files that match. Saves
  bandwidth + speeds up fan-outs from ~2 min → ~10 sec when nothing
  changed.
- **CDN caching enabled**: Cache-Control headers now propagate
  (HTML 5 min, JSON 1 hr, images 7 days). Verified `TCP_MEM_HIT` on
  CDN edge — students hitting same Week page within 5 min reuse
  cached copy.
- **URL drift detection**: `upload_to_oss.py` aborts if
  `function-compute/DEPLOYED_URL.txt` doesn't match the AI_ENDPOINT
  baked into Interactive/Week_*.html files. Catches the failure mode
  that bit us earlier in this session.
- **Single-command publish**: `python scripts/publish.py` runs the
  full pipeline (parse → fan-out → make_interactive → landing page →
  upload) in one go. `--quiet` and `--skip-fanout` flags available.
- **Zhipu model switched** from glm-4.7-flash (rate-limited) to
  glm-4-flash (stable, fast, free-tier). Hardcoded in s.yaml so it
  can't drift via local-env mismatch.

## Deferred / open items (in priority order)

### High value, deferred until you decide

**1. ~~Compress course_pipeline images~~** ✅ DONE 2026-05-02
- PNGs (~7.5 MB each) replaced with JPGs (~700-950 KB each, 9-11× smaller)
- Page weight: ~24 MB → 2.8 MB (88% reduction)
- Old PNGs deleted from OSS (37 MB freed) + local repos (135 MB freed)

**2. ~~Enable FC logging~~** ✅ DONE 2026-05-02
- SLS project `aischool-fc-logs` created (cn-beijing region)
- Logstore `ielts-ai-correction` created (30-day retention, 2 shards)
- Index configured for `s logs` query support
- `function-compute/s.yaml` has `logConfig:` block referencing both
- Verified: `s logs --time=N` returns FC Invoke Start/End records
  with matching Request IDs.
- Cost: under ¥1/month at current ~50 reqs/day (mostly storage; ingest
  is well under 1 GB/month).
- Usage: `cd function-compute && s logs --time=600` to see the last
  10 minutes of FC stdout/stderr. Matches Aliyun's web console at
  https://sls.console.aliyun.com/lognext/project/aischool-fc-logs/logsearch/ielts-ai-correction

**3. Cert auto-renewal verification** (expiry late July)
- Aliyun CDN console → each domain → HTTPS → confirm "auto-renewal"
  toggle is ON
- Set calendar reminder for July 1 to re-check
- `python scripts/check_cert_expiry.py` reports days remaining

### Medium value

**4. Bucket → private + CDN origin-pull auth** (security hardening)
- Aliyun OSS console → each bucket → Block Public Access → ON
- CDN console → each domain → Origin → enable RAM origin auth
- Tradeoff: students CAN currently hit OSS direct URL bypassing CDN
  (no CORS issue but means OSS pays for traffic CDN should). Hardening
  forces all traffic through CDN.

**5. Subdomain rename `lessons.aischool.studio` → `ielts.aischool.studio`**
- Symmetric with `igcse.aischool.studio` for future-proofing
- Cost: a few hours of cowork-Claude work (DNS + new CDN domain + cert)
- Old subdomain stays working until decommission
- Low urgency — current name works fine

### Low value

**6. Repo cleanup** — these files are gitignored or stale:
- IELTS: `Latest IELTS Course PDFs 30th March 2026/` (PDFs from 30 Mar)
- IELTS: `intro_packet.html` (unused?)
- IGCSE: `Old PDFs/`, `Update IGCSE Course March 30th 2026/`
- IGCSE: `Batch Prompts/`, `IGCSE Shadowing Chunking Instructions/`
- Some are reference materials worth keeping; others (PDF folders) are
  large and could be moved to a separate "archive" repo or deleted
  after confirming we don't need them for re-extraction.

**7. Documentation consolidation** — `CLAUDE.md`, `REORG_STATE.md`,
`pipeline.yaml` cover overlapping ground. Could reduce to 1 doc plus
the YAML config.

## Quick-reference commands

```bash
# Full publish (regen + upload)
cd "IELTS-..." && python scripts/publish.py
cd "IGCSE..." && python scripts/publish.py

# Upload only (no regen)
python scripts/publish.py --skip-fanout

# Check cert expiry
python scripts/check_cert_expiry.py

# Verify production health
curl -I https://lessons.aischool.studio/Week_05.html  # expect Cache-Control
curl -I https://igcse.aischool.studio/Week_05.html
curl -X POST https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run/ \
  -H 'Content-Type: application/json' \
  -d '{"draft":"<60-word draft>"}'  # expect 200 with corrected text

# FC redeploy if URL drifts (catch via URL drift check on next upload)
cd function-compute && s deploy --use-local --assume-yes
# Then update pipeline.yaml + canonical/interactive/Week_01.html
# Then python scripts/publish.py
```

## Cost estimate (monthly, 200 students)

| Component | Cost | Notes |
|---|---|---|
| OSS storage | ~¥0.01 | 64 MB total |
| CDN traffic | ~¥5-15 | depends on cache-hit rate; 7-day image cache helps |
| Function Compute | ~¥1-3 | tiny instances; warmup cron is the main spend |
| Zhipu API | ¥0 | glm-4-flash is free-tier |
| Aliyun DNS | ~¥1 | covered by domain reg |
| Cert | ¥0 | free DV via CDN |
| **Total** | **~¥10-20/month** | for 200-student steady state |

For 2,000 students (10× scale), CDN bill would scale ~linearly;
everything else stays flat. Cache-control TTLs help linearly with
scale (more hits = better hit ratio).
