# Putting Cloudflare in front of commutescout.com

Cloudflare's free plan sits between visitors and Cloud Run: static
assets and the 30-second map boot payload get served from Cloudflare's
edge, which makes traffic spikes a Cloudflare problem instead of a
single-instance problem, and adds HTTP/3, Brotli, and DDoS shielding.

The application is already Cloudflare-aware: `trusted_client_ip`
honors `CF-Connecting-IP` only when the platform-vouched peer address
is inside Cloudflare's published ranges, so per-IP limits keep working
behind the proxy and cannot be spoofed by clients hitting the origin
directly. Nothing else in the app changes.

## DNS records (verified against public DNS on 2026-07-27)

Cloudflare's importer finds most of these when the site is added, but
verify every row before switching nameservers. Proxy = orange cloud.

| Name | Type | Value | Proxy |
| --- | --- | --- | --- |
| commutescout.com | A | 216.239.32.21, 216.239.34.21, 216.239.36.21, 216.239.38.21 | Proxied |
| commutescout.com | AAAA | 2001:4860:4802:32::15, :34::15, :36::15, :38::15 | Proxied |
| www | CNAME | commutescout.com | Proxied |
| mcp | CNAME | ghs.googlehosted.com | DNS only |
| commutescout.com | MX | 1 aspmx.l.google.com; 5 alt1/alt2; 10 alt3/alt4 | DNS only |
| commutescout.com | TXT | both google-site-verification strings | DNS only |
| commutescout.com | TXT | "v=spf1 include:dc-aa8e722993._spfm.commutescout.com ~all" | DNS only |
| dc-aa8e722993._spfm | TXT | "v=spf1 include:_spf.google.com ~all" | DNS only |
| google._domainkey | TXT | the long DKIM key (copy verbatim) | DNS only |
| _dmarc | TXT | "v=DMARC1; p=quarantine; adkim=r; aspf=r; rua=mailto:dmarc_rua@onsecureserver.net;" | DNS only |
| send.send | MX | 10 feedback-smtp.us-east-1.amazonses.com | DNS only |
| send.send | TXT | "v=spf1 include:dc-fd741b8612._spfm.send.send.commutescout.com ~all" | DNS only |
| dc-fd741b8612._spfm.send.send | TXT | "v=spf1 include:amazonses.com ~all" | DNS only |
| resend._domainkey.send | TXT | the Resend DKIM key (copy verbatim) | DNS only |

Not carried over: the `www` A records (GoDaddy forwarding, replaced by
the redirect rule below) and `_domainconnect` (a GoDaddy-only helper).

## Cloudflare configuration (before switching nameservers)

1. SSL/TLS mode: **Full (strict)**. The origin serves a valid
   Google-managed certificate for the domain mapping, so strict works.
2. Always Use HTTPS: on.
3. Speed settings: leave Rocket Loader OFF (the page uses large inline
   scripts; do not let Cloudflare rewrite them).
4. Bot Fight Mode: OFF (it would challenge the JSON polling and the
   Cloud Monitoring uptime checks).
5. Redirect rule: `www.commutescout.com/*` -> 301
   `https://commutescout.com/$1` (replaces GoDaddy forwarding, which
   stops working the moment nameservers move).
6. Cache rule: hostname `commutescout.com` AND URI path starts with
   `/api/mapdata` -> Eligible for cache, Edge TTL: respect origin
   Cache-Control. The origin already says `public, max-age=30` for
   full responses and `no-store` while an instance is warming, so the
   edge serves each 30-second snapshot and never caches partial data.
   No other `/api/` path is cache-eligible (Cloudflare does not cache
   non-static paths unless a rule says so).

## Cutover

1. Add the site in Cloudflare (free plan), verify the record table,
   apply the configuration above.
2. At GoDaddy, replace the nameservers with the two Cloudflare assigns.
   GoDaddy remains the registrar; only DNS hosting moves.
3. Propagation takes minutes to hours. Both the old (GoDaddy) and new
   (Cloudflare) answers serve the same origin, so there is no downtime
   window; proxied behavior simply phases in.

## Verify after cutover

- `https://commutescout.com/health` returns ok and the response has a
  `cf-ray` header (proxy active).
- The map loads; `/api/mapdata` boot URL answers fast twice in a row
  and the second response shows `cf-cache-status: HIT`.
- Rate limiting still sees real client IPs: `/api/ask` from one
  machine still 429s after the per-IP burst (spot check).
- `https://www.commutescout.com` 301s to the apex.
- `https://mcp.commutescout.com/mcp` MCP handshake still returns 200
  (unproxied, unchanged).
- Send a test email to an @commutescout.com alias and confirm
  delivery; send a watch-alert test email (Resend) and confirm
  delivery (MX/SPF/DKIM rows all copied correctly).
- Both Cloud Monitoring uptime checks stay green.

## Rollback

Switch the nameservers at GoDaddy back to the previous GoDaddy pair.
Everything keeps working during propagation because the origin serves
the domain directly. The Cloudflare site config keeps; retry later.

## Known watch item

The origin certificate is Google-managed and auto-renews (roughly
every 90 days). With Cloudflare proxying, Google renews against the
domain mapping it already verified, which normally keeps working; if
a renewal ever fails, the `/health` uptime check goes red (it
validates TLS) and the immediate mitigation is flipping the Cloudflare
SSL mode from Full (strict) to Full while investigating.
