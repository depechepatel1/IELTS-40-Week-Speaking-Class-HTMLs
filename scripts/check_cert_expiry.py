#!/usr/bin/env python3
"""Check the SSL certificate expiry on the public CDN domain.

Run weekly (manually or via cron). Exits 0 with a summary if cert is healthy,
1 with a warning if cert expires in <30 days, 2 if cert is missing/invalid.

Reads domain from pipeline.yaml (no hardcoded values).
"""
from __future__ import annotations
import socket
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_domain_from_yaml(repo_root: Path) -> str:
    """Read the CDN domain from pipeline.yaml. Avoid PyYAML dep — naive parse."""
    yaml_path = repo_root / "pipeline.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"{yaml_path} not found — can't determine cert domain")
    in_cdn_block = False
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("cdn:"):
            in_cdn_block = True
            continue
        if in_cdn_block and stripped.startswith("domain:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if in_cdn_block and line and not line.startswith(" ") and not stripped.startswith("#"):
            in_cdn_block = False
    raise ValueError("Could not find cdn.domain in pipeline.yaml")


def check_cert(domain: str) -> tuple[int, str]:
    """Returns (exit_code, message)."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                # Parse 'notAfter': 'Jul 29 23:59:59 2026 GMT'
                expiry = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc
                )
                now = datetime.now(timezone.utc)
                days = (expiry - now).days
                if days < 0:
                    return 2, f"EXPIRED: {domain} cert expired {-days} days ago ({expiry.date()})"
                if days < 7:
                    return 1, f"CRITICAL: {domain} cert expires in {days} days ({expiry.date()}) — renew NOW"
                if days < 30:
                    return 1, f"WARNING: {domain} cert expires in {days} days ({expiry.date()})"
                return 0, f"OK: {domain} cert valid for {days} more days (expires {expiry.date()})"
    except Exception as e:
        return 2, f"ERROR checking {domain}: {type(e).__name__}: {e}"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        domain = load_domain_from_yaml(repo_root)
    except Exception as e:
        print(f"error loading config: {e}", file=sys.stderr)
        return 2
    code, msg = check_cert(domain)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
