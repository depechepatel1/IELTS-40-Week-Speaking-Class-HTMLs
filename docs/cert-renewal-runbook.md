# SSL Cert Renewal Runbook — `lessons.aischool.studio`

## Why this exists

The current SSL cert for `lessons.aischool.studio` is a **free DV cert** from Aliyun's "Personal Test Certificate" tier. It's free, but **does not auto-renew** and is valid for only **90 days**. You need to manually issue a new cert before the current one expires, or HTTPS at `https://lessons.aischool.studio/...` will start showing browser warnings.

## Current cert (as of issuance)

| Field | Value |
|---|---|
| Cert instance ID | `cert-7u7ojx` |
| Subscription ID | `cas_dv-cn-wjd4r9x5o01p` |
| Brand / algorithm | DigiCert RSA_2048 |
| Type | DV single-domain |
| Domain | `lessons.aischool.studio` |
| Issued | 2026-04-26 |
| **Expires** | **2026-07-24** |
| Renewal reminder | **2026-07-17** (1 week before) |
| Free quota used | 1 of 20 / year |

## Renewal procedure (every ~90 days)

⚠️ The Aliyun OSS console has a misleading "Apply for Free Cert" button that now routes to the paid ¥2498 tier. **Do not use that path.** Use the SSL Certificate Service console directly (instructions below).

### 1. Order a new free cert

1. Open <https://yundun.console.aliyun.com/?p=cas> (Aliyun SSL Certificate Service).
2. Click **个人测试证书 (原免费证书)** / *Personal Test Certificate (formerly Free Certificate)*.
3. Click **立即购买** (Buy Now). The cost is ¥0 — Aliyun routes everything through the unified order flow.
4. Check the agreement box, click **立即购买**.

### 2. Apply / issue the cert

5. Go back to the SSL Certificate console. Find the new cert (status: **待签发** / Pending Issuance).
6. Click **申请证书** / Apply.
7. Domain: `lessons.aischool.studio`
8. Validation method: **DNS validation** (DNS 验证)
9. CSR: **System-generated** (系统生成 CSR)
10. Aliyun shows a TXT record to add at `_dnsauth.lessons.aischool.studio`.
11. Add it via Aliyun DNS console (or run the helper script in step 13):
    - Open <https://dns.console.aliyun.com/> → `aischool.studio`
    - Add Record: Type=TXT, Host=`_dnsauth.lessons`, Value=*(the value Aliyun showed)*, TTL=600
    - **Note:** there's already an OSS-binding TXT at the same host. DNS allows multiple TXT values — add the new one alongside, do NOT delete the old one.
12. Wait 1-30 min. Cert status → **已签发** (Issued).

### 3. Bind the new cert to OSS

13. Open <https://oss.console.aliyun.com/> → bucket `aischool-ielts-bj` → 传输管理 → 域名管理.
14. Find `lessons.aischool.studio` → click **证书管理** (Certificate Management).
15. Choose **选择已购买证书** (Select existing cert) → pick the cert from step 12.
16. Save. Aliyun says ≤15 min to propagate; usually live in seconds.

### 4. Verify

17. Open `https://lessons.aischool.studio/Week_1_Lesson_Plan.html` in a fresh tab.
18. Confirm: padlock icon, no "Not Secure" warning, page renders normally.
19. Click the padlock → certificate → check expiry date is now ~90 days out.

### 5. Cleanup

20. **Optional:** delete the old expired cert from the SSL Certificate console to keep the list clean. Doesn't affect anything (OSS is now bound to the new cert).
21. **Optional:** delete the old TXT validation record from DNS (the new one supersedes it).

## When you might want to switch to a paid cert

Manual renewal every 90 days is annoying. If that becomes a real burden, Aliyun's paid SSL tier supports **auto-renewal**. Cost:
- DV (Domain Validation): ~¥218/year for a 1-domain cert (auto-renewed, 1-year validity)
- That's ~¥18/month for never having to think about this again

For 1 domain serving free educational content to ~40 students, the free 90-day-manual path is fine. Bump to paid the first time you forget and HTTPS goes down for a day.

## Future automation idea

A `scripts/renew_cert.py` could automate steps 1-3 by chaining Aliyun's
- `cas:CreateCertificateForPackageRequest` (order)
- `cas:DescribeCertificateApplyRequest` (poll for issuance)
- Aliyun DNS `AddDomainRecord` (the TXT, similar to `bind_custom_domain.py`)
- `oss:PutBucketCname` (bind to OSS)

The reason it doesn't exist yet: writing it requires installing the Aliyun
CAS SDK and Aliyun's free-cert "purchase" REST API path that's primarily
documented in Chinese. Worth doing when the first renewal comes around if
the manual flow above proves painful.
