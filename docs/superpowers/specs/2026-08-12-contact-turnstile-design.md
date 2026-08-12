# Contact form bot protection with Cloudflare Turnstile

Date: 2026-08-12
Status: approved (Nic, 2026-08-12), pending key setup

## Goal

Stop automated contact form spam so that hello@commutescout.com receives
mail only from real people. The owner accepts hard blocking: a visitor
who cannot pass the bot check cannot submit the form.

## Non-goals

- Protecting the Pro waitlist or sign-in endpoints. They do not send
  mail to the owner and already have their own abuse caps. They can
  adopt the same pattern later if needed.
- Content filtering (URL blocking, language heuristics). Real users
  paste URLs; heuristics cannot reach zero.

## Design

### Client (site/app/contact/page.tsx)

- Embed Turnstile in implicit rendering mode: one script tag loading
  `https://challenges.cloudflare.com/turnstile/v0/api.js` (async,
  defer) and one `<div class="cf-turnstile" data-sitekey="...">` inside
  the form, above the submit button.
- Implicit mode injects a hidden `cf-turnstile-response` input into the
  form automatically. No custom JavaScript.
- The widget runs in managed mode (configured on the Cloudflare side):
  invisible for most visitors, an interactive check only for suspicious
  clients.
- The sitekey is a public identifier (same class as the Firebase web
  apiKey) and is hardcoded in the page as a named constant. Until the
  real sitekey exists, a placeholder value ships; the widget errors
  quietly and the server does not yet enforce, so behavior is unchanged.

### Server (src/ca_roads_demo/app.py, api_contact)

- After the existing honeypot check, read `cf-turnstile-response` from
  the form.
- If the environment variable `TURNSTILE_SECRET_KEY` is unset or empty,
  skip verification entirely. Local dev, tests, CI, and self-hosters
  keep current behavior. This mirrors the REQUIRE_CLOUDFLARE pattern.
- If set, POST `secret`, `response`, and `remoteip` (from
  trusted_client_ip) to
  `https://challenges.cloudflare.com/turnstile/v0/siteverify` with a
  short timeout (5 s).
- Missing token, `success: false`, a non-200 reply, or a network error
  all reject the submission with 403 and a clear message telling the
  visitor the verification failed and to retry. Fail closed: an
  unreachable siteverify API blocks submissions rather than letting
  bots through, and the failure cause is logged at WARNING level.
- The Resend call happens only after verification passes.

### CSP (SecurityHeaders in app.py)

- script-src adds `https://challenges.cloudflare.com`.
- frame-src adds `https://challenges.cloudflare.com`.
- No connect-src change: the widget's calls happen inside its iframe.

### Configuration and deploy

- Secret Manager secret `turnstile-secret-key`; runtime SA
  ca-roads-run@ gets secretAccessor on it.
- Demo deploy adds `--update-secrets
  TURNSTILE_SECRET_KEY=turnstile-secret-key:latest` (merge semantics).
- Rollout is two-phase: (1) merge code with placeholder sitekey and no
  prod secret, behavior unchanged; (2) once the Cloudflare widget
  exists, swap in the real sitekey and mount the secret, enforcement
  on. Rollback at any time: remove the env mounting; the widget's
  token, present or absent, is then ignored.

### Owner setup (one of two paths)

- Dashboard path: Cloudflare dashboard > Turnstile > Add widget,
  hostname commutescout.com, mode Managed. Yields sitekey (public) and
  secret key.
- API path: create a Cloudflare API token with Account > Turnstile >
  Edit permission and hand it over; the widget is then created via the
  API and only the resulting secret is stored in Secret Manager.

## Error handling summary

| Case | Behavior |
| --- | --- |
| No TURNSTILE_SECRET_KEY env | Verification skipped, form works as today |
| Token missing from form | 403, "verification failed" message |
| siteverify says success=false | 403, same message |
| siteverify unreachable or non-200 | 403, same message, WARNING logged |
| Honeypot tripped | Existing behavior, unchanged, checked first |

## Testing

TDD, in tests/test_contact.py or a sibling file, with siteverify
mocked (monkeypatched httpx call), never called live:

1. Env unset: submission without a token still sends (current tests
   keep passing).
2. Env set, token missing: 403, no Resend call.
3. Env set, siteverify success=false: 403, no Resend call.
4. Env set, siteverify network error: 403, no Resend call (fail
   closed).
5. Env set, siteverify success=true: mail path proceeds.
6. Honeypot still short-circuits before any siteverify call.
