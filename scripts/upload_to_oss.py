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
import os
import sys
from pathlib import Path

import oss2

REPO = Path(__file__).resolve().parents[1]
BUCKET_NAME = "aischool-ielts-bj"
ENDPOINT = "https://oss-cn-beijing.aliyuncs.com"


def main() -> int:
    ak = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    sk = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
    if not ak or not sk:
        print("error: ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET env vars required",
              file=sys.stderr)
        return 2

    auth = oss2.Auth(ak, sk)
    service = oss2.Service(auth, ENDPOINT)

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

    # 2. Upload 40 interactive HTMLs with Text/HTML mime.
    interactive = REPO / "Interactive"
    htmls = sorted(interactive.glob("Week_*_Lesson_Plan.html"))
    print(f"\nUploading {len(htmls)} HTML files...")
    for f in htmls:
        bucket.put_object_from_file(
            f.name,
            str(f),
            headers={"Content-Type": "Text/HTML; charset=utf-8"},
        )
        print(f"  [ok] {f.name}")

    # 3. Upload pronunciations.json.
    pron = REPO / "pronunciations.json"
    if pron.exists():
        bucket.put_object_from_file(
            "pronunciations.json",
            str(pron),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        print(f"  [ok] pronunciations.json")
    else:
        print("  WARN: pronunciations.json not found at repo root", file=sys.stderr)

    print(f"\nPublic base URL:")
    print(f"  https://{BUCKET_NAME}.oss-cn-beijing.aliyuncs.com/")
    print(f"\nSample file:")
    print(f"  https://{BUCKET_NAME}.oss-cn-beijing.aliyuncs.com/Week_1_Lesson_Plan.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
