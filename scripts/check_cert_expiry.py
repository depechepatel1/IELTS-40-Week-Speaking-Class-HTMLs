#!/usr/bin/env python3
"""Check SSL certificate expiry on this repo's CDN domain — and on
the sibling repo's CDN domain too (lessons + igcse share infra).

Run weekly (manually or via cron). Exits 0 if all certs are healthy,
1 if any cert expires in <30 days (warning), 2 if any cert is missing
or invalid (critical).

Reads this repo's domain from pipeline.yaml; the sibling repo's
domain is the other one (hardcoded fallback list — both subdomains
are well-known production endpoints).
"""
from __future__ import annotations
import socket
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path

# All production domains the school's certs cover. Adding a new course?
# Add its public subdomain here so the cert check covers it.
ALL_PRODUCTION_DOMAINS = [
    "lessons.aischool.studio",   # IELTS course
    "igcse.aischool.studio",     # IGCSE course
]


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
            value = stripped.split(":", 1)[1].strip()
            # Strip YAML inline comment (everything after ' #')
            if " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            return value.strip('"').strip("'")
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
    """Check ALL production domains (this repo's + sibling course's).

    Aliyun CDN free DV certs auto-renew ~30 days before expiry, so a
    healthy state is "all certs > 30 days remaining". A WARNING means
    Aliyun's renewal job hasn't kicked in yet (or failed silently);
    CRITICAL means we're <7 days away from HTTPS breaking.
    """
    repo_root = Path(__file__).resolve().parent.parent
    # Prefer this repo's pipeline.yaml domain; fall back to known production list.
    domains = list(ALL_PRODUCTION_DOMAINS)
    try:
        my_domain = load_domain_from_yaml(repo_root)
        if my_domain not in domains:
            domains.append(my_domain)
    except Exception:
        pass

    worst = 0
    for d in domains:
        code, msg = check_cert(d)
        print(msg)
        worst = max(worst, code)
    if worst == 0:
        print("\nAll production certs healthy. Aliyun CDN auto-renews ~30 days before expiry.")
    elif worst == 1:
        print("\nWARNING: one or more certs <30 days from expiry. Verify renewal in:")
        print("  https://cdn.console.aliyun.com/domain/list")
    else:
        print("\nCRITICAL: cert expired or unreachable. Manual intervention required.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
