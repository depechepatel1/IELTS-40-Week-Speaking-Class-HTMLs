#!/usr/bin/env python3
"""One-off upload: Bug 3 page-bottom videos to IELTS OSS.

Uploads 3 mp4 files from D:/Downloads/ to aischool-ielts-bj at
videos/video1.mp4, videos/video2.mp4, videos/video3.mp4 with a long
Cache-Control TTL. Same model as the Round 48 cover_spinning.webm
one-off upload. The videos are stable looping clips reused across
all 40 weeks; web-only (interactive HTMLs only, NOT pdf-base).

Run:  python scripts/upload_bug3_videos.py
Env:  ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET

Hosts these public URLs after success:
  https://ielts.aischool.studio/videos/video1.mp4
  https://ielts.aischool.studio/videos/video2.mp4
  https://ielts.aischool.studio/videos/video3.mp4

This script is NOT meant for the publish pipeline. It's a one-off.
Do NOT commit it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import oss2  # type: ignore
except ImportError:
    print("error: oss2 not installed. Run: pip install oss2", file=sys.stderr)
    sys.exit(1)


BUCKET_NAME = "aischool-ielts-bj"
ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"
CACHE_CONTROL = "public, max-age=2592000"  # 30 days
CONTENT_TYPE = "video/mp4"

# Source path -> OSS key. Renames "video N.mp4" -> "videoN.mp4" to drop
# the space (OneDrive-safe + matches the parked-bug shorthand).
UPLOADS = [
    (Path("D:/Downloads/video 1.mp4"), "videos/video1.mp4"),
    (Path("D:/Downloads/video 2.mp4"), "videos/video2.mp4"),
    (Path("D:/Downloads/video 3.mp4"), "videos/video3.mp4"),
]


def main() -> int:
    ak = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    sk = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
    if not ak or not sk:
        print("error: ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET env vars required",
              file=sys.stderr)
        return 1

    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)

    # Sanity-check bucket access first (same pattern as scripts/upload_to_oss.py
    # bucket pre-check, with the 5xx-retry baked in).
    try:
        bucket.get_bucket_info()
    except oss2.exceptions.OssError as e:
        print(f"error: bucket check failed ({e.status} {e.code}): {e.message}",
              file=sys.stderr)
        return 2

    for src, key in UPLOADS:
        if not src.exists():
            print(f"error: source missing: {src}", file=sys.stderr)
            return 3
        size = src.stat().st_size
        print(f"[uploading] {src.name} ({size:,} bytes) -> {BUCKET_NAME}/{key}")
        headers = {
            "Content-Type": CONTENT_TYPE,
            "Cache-Control": CACHE_CONTROL,
        }
        with open(src, "rb") as fh:
            result = bucket.put_object(key, fh, headers=headers)
        ok = 200 <= result.status < 300
        print(f"  [{'ok' if ok else 'fail'}] status={result.status} etag={result.etag}")
        if not ok:
            return 4

    print()
    print("All 3 videos uploaded. Verify:")
    for _, key in UPLOADS:
        print(f"  https://ielts.aischool.studio/{key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
