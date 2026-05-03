# SSL Cert Runbook — `*.aischool.studio` (wildcard)

## Why this exists

Cert lifecycle for the school's CDN domains. As of **2026-05-03**, all three
public subdomains (`ielts.aischool.studio`, `igcse.aischool.studio`,
`lessons.aischool.studio`) share a single **wildcard cert**, which auto-renews
mid-cycle. Adding a new subdomain (e.g. `app.`, `api.`, `www.`) just needs a
small SDK call — no new cert purchase.

## Current cert (as of 2026-05-03)

| Field | Value |
|---|---|
| Cert ID | `24792685` |
| Brand | Wosign DV |
| Type | Wildcard `*.aischool.studio` |
| Issued | 2026-05-03 |
| **Expires** | **2026-11-17** |
| Auto-renew | Yes (Aliyun rotates the cert mid-cycle) |
| Subscription expires | 2027-05-03 |
| Subscription manual renewal reminder | **2027-04-03** (~30 days early) |
| Bound CDN domains | `ielts.aischool.studio`, `igcse.aischool.studio`, `lessons.aischool.studio` |

## Health check (run anytime)

```bash
python scripts/check_cert_expiry.py
```

Should report `OK: <domain> cert valid for ~180+ more days`. Exit code 0 = clean,
1 = warning (<30 days), 2 = critical/unreachable.

## Cert auto-renewal — how it works

Aliyun runs a subscription-style cert: the underlying cert is reissued every
~6 months mid-subscription, and the subscription itself runs ~12 months. The
CDN auto-binds new revisions of the wildcard. **No human action needed
between subscription renewals.**

The only manual step is **renewing the subscription** before 2027-05-03.
Calendar reminder is set for 2027-04-03 (30 days early).

## Adding a NEW subdomain (e.g. `api.aischool.studio`)

Don't buy a new cert — bind the existing wildcard.

```python
import os
from alibabacloud_cdn20180510.client import Client as CdnClient
from alibabacloud_cdn20180510 import models as cdn_models
from alibabacloud_tea_openapi import models as open_api_models

ak = os.environ['ALIYUN_ACCESS_KEY_ID']
sk = os.environ['ALIYUN_ACCESS_KEY_SECRET']
client = CdnClient(open_api_models.Config(
    access_key_id=ak, access_key_secret=sk, endpoint='cdn.aliyuncs.com'))

# 1. Bind the wildcard cert to the new CDN domain
client.set_cdn_domain_sslcertificate(
    cdn_models.SetCdnDomainSSLCertificateRequest(
        domain_name='<new-subdomain>.aischool.studio',
        sslprotocol='on',
        cert_type='cas',
        cert_id='24792685',
        cert_region='cn-hangzhou',
    )
)

# 2. Force HTTPS redirect (matches the other subdomains)
import json
client.batch_set_cdn_domain_config(
    cdn_models.BatchSetCdnDomainConfigRequest(
        domain_names='<new-subdomain>.aischool.studio',
        functions=json.dumps([{
            'functionName': 'https_force',
            'functionArgs': [{'argName': 'enable', 'argValue': 'on'}],
        }]),
    )
)
```

Prerequisite: the new CDN domain must already exist (use `AddCdnDomain` first;
see `scripts/bind_custom_domain.py` for DNS + bucket binding pattern).

## Subscription renewal (2027-04-03)

When the calendar reminder fires:

1. Open <https://yundun.console.aliyun.com/?p=cas> (Aliyun SSL Certificate
   Service console).
2. Find the cert `24792685` / subscription. Click **续费** (Renew).
3. Confirm the order. Aliyun re-issues a new wildcard cert under the same
   subscription; bound CDN domains pick it up automatically.
4. Run `python scripts/check_cert_expiry.py` to confirm the new expiry date.

If for some reason you missed the renewal and the subscription expired:
- Fall back to ordering a new wildcard cert (the same Wosign DV product)
- Bind to all three CDN domains via the `set_cdn_domain_sslcertificate`
  snippet above (with the NEW cert_id)
- Update `pipeline.yaml` `cdn.cert_id` and the Cert Renewal section in
  `CLAUDE.md` for both repos.

## Other certs in the account

- `db.aischool.studio` — single-domain cert id `24239187` (GeoTrust, expires
  2026-10-15). Not on the wildcard. Non-urgent; can be migrated to the
  wildcard later by re-binding via the same snippet above.

## What NOT to do

- ❌ Don't buy new free DV certs from Aliyun's "Personal Test Certificate"
  pool — quota is exhausted on this account.
- ❌ Don't manually rebind the cert in OSS — the CDN handles it now.
- ❌ Don't change DNS away from the CDN edge endpoint
  (`<subdomain>.aischool.studio.w.kunlunaq.com`); the cert auto-rotation
  expects DNS pointing at the CDN.
