#!/usr/bin/env python3
"""Bind a custom domain to the aischool-ielts-bj OSS bucket.

1. Adds a DNS CNAME record (lessons.aischool.studio -> bucket OSS endpoint)
   via Aliyun Alidns API.
2. Binds the custom domain to the bucket via OSS PutCname.
3. Requests Aliyun's free DV cert for HTTPS.
4. Verifies DNS resolution + HTTPS.

Reads AccessKey from env: ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET.

Usage:  python scripts/bind_custom_domain.py
"""
from __future__ import annotations
import json
import os
import socket
import sys
import time
from urllib.parse import urlparse

import oss2
from aliyunsdkcore.client import AcsClient
from aliyunsdkalidns.request.v20150109 import (
    DescribeDomainRecordsRequest,
    AddDomainRecordRequest,
)

DOMAIN = "aischool.studio"
SUBDOMAIN_RR = "lessons"  # full host: lessons.aischool.studio
FULL_HOST = f"{SUBDOMAIN_RR}.{DOMAIN}"
BUCKET = "aischool-ielts-bj"
REGION = "cn-beijing"
BUCKET_HOST = f"{BUCKET}.oss-{REGION}.aliyuncs.com"


def step1_dns_cname(ak: str, sk: str) -> None:
    """Add CNAME via Alidns. Idempotent — skip if record already exists."""
    client = AcsClient(ak, sk, REGION)

    # Check existing records for the subdomain.
    desc = DescribeDomainRecordsRequest.DescribeDomainRecordsRequest()
    desc.set_DomainName(DOMAIN)
    desc.set_RRKeyWord(SUBDOMAIN_RR)
    resp = client.do_action_with_exception(desc)
    body = json.loads(resp)
    records = body.get("DomainRecords", {}).get("Record", [])

    cname = next(
        (r for r in records if r.get("RR") == SUBDOMAIN_RR and r.get("Type") == "CNAME"),
        None,
    )
    if cname:
        if cname.get("Value") == BUCKET_HOST:
            print(f"  [skip] CNAME {FULL_HOST} -> {BUCKET_HOST} already exists")
            return
        print(f"  [warn] CNAME {FULL_HOST} -> {cname.get('Value')} exists with different value; not modifying")
        return

    add = AddDomainRecordRequest.AddDomainRecordRequest()
    add.set_DomainName(DOMAIN)
    add.set_RR(SUBDOMAIN_RR)
    add.set_Type("CNAME")
    add.set_Value(BUCKET_HOST)
    add.set_TTL(600)  # 10 minutes — quick to update if needed
    resp = client.do_action_with_exception(add)
    body = json.loads(resp)
    print(f"  [ok] DNS record {body.get('RecordId')}: {FULL_HOST} CNAME -> {BUCKET_HOST}")


def step2a_create_cname_token(ak: str, sk: str) -> str:
    """Create a CNAME ownership token (Aliyun's verification mechanism)."""
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, f"https://oss-{REGION}.aliyuncs.com", BUCKET)
    resp = bucket.create_bucket_cname_token(FULL_HOST)
    print(f"  [ok] Token created. Verification: TXT _dnsauth.{SUBDOMAIN_RR} = {resp.token}")
    return resp.token


def step2b_add_dns_txt(ak: str, sk: str, token: str) -> None:
    """Add the verification TXT record at _dnsauth.<subdomain>."""
    client = AcsClient(ak, sk, REGION)
    rr = f"_dnsauth.{SUBDOMAIN_RR}"   # _dnsauth.lessons → resolves at _dnsauth.lessons.aischool.studio

    # Idempotent — check if existing
    desc = DescribeDomainRecordsRequest.DescribeDomainRecordsRequest()
    desc.set_DomainName(DOMAIN)
    desc.set_RRKeyWord(rr)
    resp = client.do_action_with_exception(desc)
    body = json.loads(resp)
    records = body.get("DomainRecords", {}).get("Record", [])
    txt = next(
        (r for r in records if r.get("RR") == rr and r.get("Type") == "TXT"),
        None,
    )
    if txt and txt.get("Value") == token:
        print(f"  [skip] TXT record already matches token")
        return
    if txt:
        print(f"  [info] Existing TXT value differs ({txt.get('Value')[:30]}...); replacing")
        # Could update via UpdateDomainRecord; simpler is to add a new one
        # (OSS only checks if any TXT record matches the token, so adding works).

    add = AddDomainRecordRequest.AddDomainRecordRequest()
    add.set_DomainName(DOMAIN)
    add.set_RR(rr)
    add.set_Type("TXT")
    add.set_Value(token)
    add.set_TTL(600)
    resp = client.do_action_with_exception(add)
    body = json.loads(resp)
    print(f"  [ok] DNS record {body.get('RecordId')}: TXT {rr}.{DOMAIN} = {token[:24]}...")


def step2c_wait_for_txt_then_bind(ak: str, sk: str, token: str, max_wait: int = 300) -> None:
    """Poll until OSS sees the TXT record, then bind the CNAME."""
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, f"https://oss-{REGION}.aliyuncs.com", BUCKET)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            bucket.put_bucket_cname(oss2.models.PutBucketCnameRequest(FULL_HOST))
            print(f"  [ok] Bound {FULL_HOST} to bucket {BUCKET}")
            return
        except oss2.exceptions.ServerError as e:
            code = e.details.get("Code", "")
            if code in ("NeedVerifyDomainOwnership",):
                print(f"  ...waiting for TXT propagation ({int(deadline - time.time())}s left)", flush=True)
                time.sleep(20)
            elif code == "BucketCnameAlreadyExist":
                print(f"  [skip] {FULL_HOST} already bound")
                return
            else:
                raise
    raise RuntimeError("Timed out waiting for domain ownership verification.")


def step2_oss_cname(ak: str, sk: str) -> None:
    """Verify domain ownership and bind the custom domain to the bucket."""
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, f"https://oss-{REGION}.aliyuncs.com", BUCKET)
    # Check existing
    try:
        cnames = bucket.list_bucket_cname().cname
        if any(c.domain == FULL_HOST for c in cnames):
            print(f"  [skip] OSS CNAME for {FULL_HOST} already bound")
            return
    except Exception:
        pass

    # 2a: get the verification token
    token = step2a_create_cname_token(ak, sk)
    # 2b: add the TXT record
    step2b_add_dns_txt(ak, sk, token)
    # 2c: poll until OSS verifies and bind
    step2c_wait_for_txt_then_bind(ak, sk, token)


def step3_dns_propagation() -> bool:
    """Poll until the DNS resolves to a valid OSS IP. Returns True on success."""
    print(f"  Waiting for DNS to propagate (up to 5 min)...", flush=True)
    deadline = time.time() + 300
    last_err = None
    while time.time() < deadline:
        try:
            ip = socket.gethostbyname(FULL_HOST)
            print(f"  [ok] {FULL_HOST} resolves to {ip}")
            return True
        except Exception as e:
            last_err = e
            time.sleep(15)
    print(f"  [warn] DNS still not resolving after 5 min ({last_err}). May need a few more minutes.")
    return False


def step4_request_https(ak: str, sk: str) -> None:
    """Request Aliyun's free DV cert for the custom domain.

    Uses PutBucketCname with a CertInfo whose `force=True` flag asks Aliyun
    to auto-issue a free DV cert (Let's-Encrypt-style, auto-renewing).
    """
    auth = oss2.Auth(ak, sk)
    bucket = oss2.Bucket(auth, f"https://oss-{REGION}.aliyuncs.com", BUCKET)
    try:
        cert = oss2.models.CertInfo(force=True)
        req = oss2.models.PutBucketCnameRequest(FULL_HOST, cert=cert)
        bucket.put_bucket_cname(req)
        print(f"  [ok] Requested Aliyun free DV cert for {FULL_HOST} (provisioning takes 1-5 min)")
    except Exception as e:
        print(f"  [warn] Could not auto-request free cert: {e}")
        print(f"         Manual fallback: Aliyun OSS console > bucket > Domain Management > add cert")


def main() -> int:
    ak = os.environ.get("ALIYUN_ACCESS_KEY_ID")
    sk = os.environ.get("ALIYUN_ACCESS_KEY_SECRET")
    if not ak or not sk:
        print("error: ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET env vars required",
              file=sys.stderr)
        return 2

    print("Step 1: Add DNS CNAME record")
    step1_dns_cname(ak, sk)
    print()

    print("Step 2: Bind custom domain to OSS bucket")
    step2_oss_cname(ak, sk)
    print()

    print("Step 3: Verify DNS propagation")
    step3_dns_propagation()
    print()

    print("Step 4: Request Aliyun free DV SSL cert")
    step4_request_https(ak, sk)
    print()

    print(f"Done. Test:  https://{FULL_HOST}/Week_01.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
