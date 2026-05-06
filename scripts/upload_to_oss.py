#!/usr/bin/env python3
"""One-shot script: create the aischool-ielts-bj OSS bucket (if absent),
set public-read ACL, and upload all 40 interactive HTMLs + pronunciations.json
with the correct MIME types.

OSS public URL pattern after upload:
  https://aischool-ielts-bj.oss-cn-beijing.aliyuncs.com/<filename>

Run:  python scripts/upload_to_oss.py

Reads AccessKey from env: ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET.
"""
from __future__ import annotations
import hashlib
import os
import re
import sys
from pathlib import Path

import oss2

REPO = Path(__file__).resolve().parents[1]
BUCKET_NAME = "aischool-ielts-bj"
ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"

# Cache-Control header policy. CDN caches per these durations; clients
# (browsers) cache for max-age. Values balance "students see fresh
# content" vs "every page-view doesn't slam origin":
#   HTMLs:  5 min   — fresh enough for last-minute curriculum tweaks
#   JSON:   1 hour  — pronunciations.json is essentially static
#   Images: 7 days  — course pipeline PNGs change rarely
CACHE_CONTROL = {
    ".html": "public, max-age=300, must-revalidate",
    ".json": "public, max-age=3600",
    ".png":  "public, max-age=604800",
    ".jpg":  "public, max-age=604800",
    ".webp": "public, max-age=604800",
    ".svg":  "public, max-age=604800",
    ".gif":  "public, max-age=604800",
}

# Round 29 (2026-05-03): admin console + rotating-password gate config.
# admin/index.html and _pwhash.json are NOT cached at the CDN — admin
# changes (password rotation) must propagate immediately, and the admin
# UI itself should always be the latest deployed version.
_NO_CACHE = "no-cache, no-store, must-revalidate"
ADMIN_KEY = "admin/index.html"
PWHASH_KEY = "_pwhash.json"

# Fallback FC endpoint if DEPLOYED_URL.txt is missing (e.g. when IGCSE
# uploads the admin page even though FC lives in the IELTS repo).
# Keep in sync with pipeline.yaml's `function_compute.endpoint`.
_FC_ENDPOINT_FALLBACK = "https://ielts-arrection-nafrghqpzj.cn-beijing.fcapp.run"


def _file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _oss_object_state(bucket, key: str) -> tuple[str | None, str | None]:
    """Return (md5, cache_control) for an OSS object, or (None, None) if absent.
    Used to decide whether to skip the upload — we re-upload if either
    the body changed OR the cache-control header is missing/stale."""
    try:
        meta = bucket.head_object(key)
        etag = (meta.etag or "").strip('"').lower()
        if "-" in etag:  # multipart upload — ETag isn't the MD5
            return (None, None)
        # Cache-Control is in headers, lower-cased by HTTP convention
        cc = meta.headers.get("cache-control") or meta.headers.get("Cache-Control")
        return (etag, cc)
    except oss2.exceptions.NoSuchKey:
        return (None, None)
    except Exception:
        return (None, None)


def _put_with_retry(bucket, key: str, src: Path, headers: dict, max_attempts: int = 3) -> None:
    """Round 35 (2026-05-06) — retry-on-503 wrapper around put_object_from_file.
    Aliyun OSS occasionally returns transient 503 ServerErrors mid-upload
    (~1 in 40 files at this region), and each retry hits a DIFFERENT random
    file, so this is server-side flakiness — not per-file. Without retry,
    every IELTS publish would intermittently report `[FAIL]` from upload_to_oss
    even though most files succeeded. Three attempts with exponential backoff
    (1s, 2s) eliminates this."""
    import time as _time
    last = None
    for attempt in range(max_attempts):
        try:
            bucket.put_object_from_file(key, str(src), headers=headers)
            if attempt > 0:
                print(f"        (recovered after {attempt + 1} attempts)")
            return
        except oss2.exceptions.ServerError as e:
            last = e
            if e.status not in (500, 502, 503, 504) or attempt == max_attempts - 1:
                raise
            wait_s = 2 ** attempt
            print(f"        OSS {e.status}, retrying {key} in {wait_s}s "
                  f"(attempt {attempt + 1}/{max_attempts})")
            _time.sleep(wait_s)
    if last:
        raise last


def _smart_upload(bucket, key: str, src: Path, content_type: str) -> tuple[str, int]:
    """Upload `src` to `key` with appropriate Cache-Control header. Skip
    if local MD5 matches OSS ETag AND cache-control header matches.
    The cache-control check ensures objects backfilled with new header
    policy on a subsequent run instead of staying stuck on old metadata.
    Returns (status_str, bytes_uploaded). status_str in {ok, skip, fail}."""
    ext = src.suffix.lower()
    expected_cc = CACHE_CONTROL.get(ext, "")
    headers = {"Content-Type": content_type}
    if expected_cc:
        headers["Cache-Control"] = expected_cc
    local_md5 = _file_md5(src)
    remote_md5, remote_cc = _oss_object_state(bucket, key)
    body_match = local_md5 == remote_md5
    header_match = (remote_cc or "").strip() == expected_cc.strip()
    if body_match and header_match:
        return ("skip", 0)
    _put_with_retry(bucket, key, src, headers)
    return ("ok", src.stat().st_size)


def _check_fc_url_drift(repo: Path) -> None:
    """Warn if the FC URL in DEPLOYED_URL.txt doesn't match what's baked
    into the Interactive HTMLs. This catches the failure mode that bit us
    on 2026-05-02 (HTMLs were referencing a dead URL after FC redeploy)."""
    deployed_url_file = repo / "function-compute" / "DEPLOYED_URL.txt"
    if not deployed_url_file.exists():
        return  # no FC in this repo (e.g. IGCSE — shared FC lives in IELTS)
    deployed = deployed_url_file.read_text().strip()
    sample = next(iter((repo / "Interactive").glob("Week_*.html")), None)
    if not sample:
        return
    content = sample.read_text(encoding="utf-8")
    m = re.search(r'AI_ENDPOINT\s*=\s*["\']([^"\']+)["\']', content)
    if m and m.group(1) != deployed:
        print(f"WARN: FC URL drift detected!", file=sys.stderr)
        print(f"  DEPLOYED_URL.txt: {deployed}", file=sys.stderr)
        print(f"  Baked in HTMLs:   {m.group(1)}", file=sys.stderr)
        print(f"  Re-bake before uploading:", file=sys.stderr)
        print(f"    python scripts/make_interactive.py --in . --out Interactive \\", file=sys.stderr)
        print(f"      --endpoint {deployed} --bucket-base https://ielts.aischool.studio", file=sys.stderr)
        print(f"  Aborting upload to prevent deploying stale URL.", file=sys.stderr)
        sys.exit(7)


def main() -> int:
    ak = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    sk = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
    if not ak or not sk:
        print("error: ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET env vars required",
              file=sys.stderr)
        return 2

    auth = oss2.Auth(ak, sk)
    service = oss2.Service(auth, ENDPOINT)

    # 0. Sanity check: warn if the FC URL drifted between DEPLOYED_URL.txt
    # and what's baked into Interactive HTMLs. This catches the failure
    # mode that bit us on 2026-05-02.
    _check_fc_url_drift(REPO)

    # 1. Check if bucket exists; create if absent with public-read ACL.
    existing = [b.name for b in oss2.BucketIterator(service)]
    bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)
    if BUCKET_NAME in existing:
        print(f"Bucket '{BUCKET_NAME}' already exists.")
        # Ensure public-read ACL.
        try:
            bucket.put_bucket_acl(oss2.BUCKET_ACL_PUBLIC_READ)
            print(f"  ACL set to public-read.")
        except Exception as e:
            print(f"  warning: could not update ACL ({e}).")
    else:
        bucket.create_bucket(oss2.BUCKET_ACL_PUBLIC_READ)
        print(f"Created bucket '{BUCKET_NAME}' with public-read ACL in cn-beijing.")

    ok = skip = 0

    # 2. Upload 40 interactive HTMLs with Text/HTML mime + cache headers.
    interactive = REPO / "Interactive"
    htmls = sorted(interactive.glob("Week_*.html"))
    print(f"\nUploading {len(htmls)} HTML files (skip-unchanged enabled)...")
    for f in htmls:
        status, _ = _smart_upload(bucket, f.name, f, "Text/HTML; charset=utf-8")
        if status == "ok":   ok += 1
        elif status == "skip": skip += 1
        # Less verbose: only print uploaded ones; skipped ones suppressed
        if status == "ok":
            print(f"  [ok] {f.name}")

    # 3. Upload pronunciations.json.
    pron = REPO / "pronunciations.json"
    if pron.exists():
        status, _ = _smart_upload(bucket, "pronunciations.json", pron, "application/json; charset=utf-8")
        if status == "ok":   ok += 1
        elif status == "skip": skip += 1
        print(f"  [{status}] pronunciations.json")
    else:
        print("  WARN: pronunciations.json not found at repo root", file=sys.stderr)

    # 3b. Auto-regenerate index.html if stale, then upload.
    index_path = REPO / "index.html"
    needs_rebuild = not index_path.exists()
    if not needs_rebuild:
        index_mtime = index_path.stat().st_mtime
        for w in REPO.glob("Week_*.html"):
            if w.stat().st_mtime > index_mtime:
                needs_rebuild = True
                break
    if needs_rebuild:
        import subprocess
        print(f"  [info] index.html stale or missing — regenerating via build_landing_page.py")
        subprocess.run([sys.executable, str(REPO / "scripts" / "build_landing_page.py")],
                       check=True, cwd=str(REPO))
    if index_path.exists():
        status, _ = _smart_upload(bucket, "index.html", index_path, "text/html; charset=utf-8")
        if status == "ok":   ok += 1
        elif status == "skip": skip += 1
        print(f"  [{status}] index.html")
    else:
        print("  WARN: index.html not found and build_landing_page.py failed", file=sys.stderr)

    # 4. Upload images/*.png with long cache TTL.
    candidates = [REPO / "Interactive" / "images", REPO / "images"]
    src_images = next((p for p in candidates if p.is_dir()), None)
    if src_images is None:
        print("  WARN: no images/ folder found", file=sys.stderr)
    else:
        mime_by_ext = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                       ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif"}
        img_count = 0
        for img in sorted(src_images.iterdir()):
            if img.is_file() and img.suffix.lower() in mime_by_ext:
                status, _ = _smart_upload(bucket, f"images/{img.name}", img,
                                          mime_by_ext[img.suffix.lower()])
                if status == "ok":   ok += 1
                elif status == "skip": skip += 1
                print(f"  [{status}] images/{img.name}")
                img_count += 1
        if img_count:
            print(f"Processed {img_count} image(s) from {src_images}")

    # 5. Upload the admin console (Round 29). Reads scripts/admin/index.html,
    #    substitutes __FC_ENDPOINT__ at upload time, and pushes to OSS at
    #    key `admin/index.html` with no-cache headers so admin tweaks land
    #    immediately. Idempotent — skip-unchanged based on (substituted)
    #    body MD5.
    admin_src = REPO / "scripts" / "admin" / "index.html"
    if admin_src.exists():
        deployed_url_file = REPO / "function-compute" / "DEPLOYED_URL.txt"
        fc_endpoint = (deployed_url_file.read_text().strip()
                       if deployed_url_file.exists() else _FC_ENDPOINT_FALLBACK)
        admin_html = admin_src.read_text(encoding="utf-8").replace(
            "__FC_ENDPOINT__", fc_endpoint.rstrip("/")
        )
        # Skip-unchanged: hash the SUBSTITUTED body, not the source file.
        admin_md5 = hashlib.md5(admin_html.encode("utf-8")).hexdigest()
        existing_md5, existing_cc = _oss_object_state(bucket, ADMIN_KEY)
        if existing_md5 == admin_md5 and (existing_cc or "").strip() == _NO_CACHE:
            print(f"  [skip] {ADMIN_KEY}")
            skip += 1
        else:
            bucket.put_object(
                ADMIN_KEY,
                admin_html.encode("utf-8"),
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "Cache-Control": _NO_CACHE,
                },
            )
            print(f"  [ok] {ADMIN_KEY}  (FC endpoint: {fc_endpoint})")
            ok += 1
    else:
        print(f"  WARN: scripts/admin/index.html not found — admin console not uploaded",
              file=sys.stderr)

    print(f"\nResult: {ok} uploaded, {skip} skipped (already up-to-date)")
    print(f"Public landing page: https://ielts.aischool.studio/")
    print(f"Admin console:       https://ielts.aischool.studio/admin/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
