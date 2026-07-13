# Deploying to Cloud Run

The server runs as a single Cloud Run service using the streamable HTTP
transport. Scale-to-zero is fine: cold starts are a few seconds and the data
is fetched fresh anyway.

## Runtime identity (least privilege)

Both Cloud Run services run as a dedicated service account
`ca-roads-run@ca-roads-mcp.iam.gserviceaccount.com`, NOT the default
Compute Engine SA (which carries `roles/editor`). A compromised app
must not inherit project-wide Editor. The runtime SA holds only
`roles/datastore.user`, `roles/bigquery.dataEditor`, and
`roles/secretmanager.secretAccessor` on each mounted secret.

```sh
gcloud iam service-accounts create ca-roads-run \
  --display-name "CA Roads Cloud Run runtime (least privilege)"
SA=ca-roads-run@ca-roads-mcp.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding ca-roads-mcp \
  --member "serviceAccount:$SA" --role roles/datastore.user --condition=None
gcloud projects add-iam-policy-binding ca-roads-mcp \
  --member "serviceAccount:$SA" --role roles/bigquery.dataEditor --condition=None
for s in anthropic-api-key tomtom-api-key bay511-api-key \
         vapid-private-key resend-api-key; do
  gcloud secrets add-iam-policy-binding "$s" --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor
done
```
Always pass `--service-account $SA` on deploy (both service blocks
below do). Residual: the default Compute SA still has Editor and is
used for `--source` builds; migrating builds to a dedicated build SA
would remove that entirely.

## One-time setup

```sh
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

## Deploy

Cloud Build does the container build, so no local Docker is needed:

```sh
gcloud run deploy ca-roads-mcp \
  --source . \
  --region us-west1 \
  --allow-unauthenticated \
  --service-account ca-roads-run@ca-roads-mcp.iam.gserviceaccount.com \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 40
```

The MCP endpoint is `https://<service-url>/mcp`.

## Demo service

Same image, different command. Every rate and cost guard is in-process,
so the demo MUST run with `--max-instances 1`: a second instance would
silently double the per-IP and daily-dollar caps.

```sh
gcloud run deploy ca-roads-demo \
  --source . \
  --command ca-roads-demo \
  --region us-west1 \
  --allow-unauthenticated \
  --service-account ca-roads-run@ca-roads-mcp.iam.gserviceaccount.com \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 1 \
  --concurrency 20 \
  --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars DEMO_MODEL=claude-sonnet-5,TELEMETRY_SALT=<random 32 chars>
```

## Cold starts

The MCP service runs with `--min-instances 0` (scale to zero); the
demo runs with `--min-instances 1` so visitors never pay a cold start,
at roughly five to ten dollars a month of idle time.
Two mitigations ship by default: `--cpu-boost` (faster container boot,
free) and a startup prewarm in the demo that fills all feed caches in
the background while the page is still loading. If the remaining first
load bothers you, `--min-instances 1` on the demo removes cold starts
entirely at roughly ten to fifteen dollars a month of idle instance
time.

## Notes

- The MCP service needs no secrets: all upstream feeds are free and public.
- Rate limiting is per-IP in process (token bucket, 20 burst / 30 per
  minute sustained), which is also why `--max-instances 1` matters.
- Costs: requests are tiny and infrequent; with scale-to-zero this should
  stay pennies per day.

## Verify

```sh
python - <<'EOF'
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("https://<service-url>/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print([t.name for t in (await s.list_tools()).tools])

asyncio.run(main())
EOF
```

## Environment variables (demo service)

| Variable | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Model access; mount from Secret Manager | required |
| `TELEMETRY_SALT` | Random 32+ chars; salts the daily visitor hashes so they can't be brute-forced back to IPs | required in production |
| `DEMO_MODEL` | Answering model | `claude-sonnet-5` |
| `DEMO_DAILY_DOLLARS` | Global daily model-spend cap | `3.0` |
| `DEMO_PER_IP_DAILY` | Questions per visitor per day | `20` |

## Watch areas (optional, demo service)

The /watch feature needs four things beyond the base demo: a Firebase
Identity Platform project (sign-in), Firestore (storage), a VAPID key
(web push), and Cloud Scheduler (the checker heartbeat). Without them
the rest of the demo works fine and /watch shows sign-in but cannot
authenticate.

```sh
# one-time: enable APIs, create the Firestore database
gcloud services enable identitytoolkit.googleapis.com firestore.googleapis.com cloudscheduler.googleapis.com firebase.googleapis.com
gcloud firestore databases create --location=us-west1 --type=firestore-native

# add Firebase to the project and register a web app in the Firebase
# console, then enable the Google and Email link sign-in providers and
# add your service domain to the authorized domains. Put the web app's
# apiKey/appId in FIREBASE_API_KEY / FIREBASE_APP_ID env vars.

# VAPID keypair for web push
python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.private_pem().decode())" | gcloud secrets create vapid-private-key --data-file=-

# checker heartbeat every 5 minutes
gcloud iam service-accounts create watch-checker
gcloud scheduler jobs create http watch-checker --location us-west1 \
  --schedule "*/5 * * * *" --http-method POST \
  --uri https://<demo-url>/api/check-watches \
  --oidc-service-account-email watch-checker@<project>.iam.gserviceaccount.com \
  --oidc-token-audience https://<demo-url>/api/check-watches
```

| Variable | Purpose |
|---|---|
| `VAPID_PRIVATE_KEY` | Web-push signing key PEM; mount from Secret Manager |
| `VAPID_SUBJECT` | `mailto:` contact sent to push services |
| `ADMIN_EMAILS` | Comma-separated Google emails allowed into /admin |
| `FIREBASE_API_KEY` / `FIREBASE_APP_ID` | Your Firebase web app's public client config |
| `CHECKER_AUDIENCE` | The check-watches URL; must match the scheduler job's audience |
| `CHECKER_SA` | The scheduler job's service-account email |
| `RESEND_API_KEY` / `ALERT_FROM_EMAIL` | Optional; enables email alerts once a sending domain is verified |

The demo's service account needs `roles/datastore.user` for Firestore
and secretAccessor on the VAPID secret.

Deploy the deny-all Firestore rules (clients never touch the database
directly; the server uses the service-account SDK, which bypasses
rules):

```sh
# once, and whenever firestore.rules changes
gcloud firestore databases update --project ca-roads-mcp   # or via the Firebase Rules API / console: publish firestore.rules
```
The repo's `firestore.rules` is the source of truth; it is currently
released to `cloud.firestore`.

## Optional data-source keys (both services)

Three sources activate only when their key is present; everything else
works without them. Store keys in Secret Manager and mount them as env
vars so they never touch code or shell history:

```sh
# one time per key: paste the key when prompted, then Ctrl-D
gcloud secrets create tomtom-api-key --data-file=-
gcloud secrets create bay511-api-key --data-file=-
gcloud secrets create nvroads-api-key --data-file=-

# grant Cloud Run access (once per secret)
gcloud secrets add-iam-policy-binding tomtom-api-key   --member="serviceAccount:15002631928-compute@developer.gserviceaccount.com"   --role="roles/secretmanager.secretAccessor"

# attach to a service (repeat --set-secrets values you already use)
gcloud run services update ca-roads-mcp --region us-west1   --set-secrets TOMTOM_API_KEY=tomtom-api-key:latest,BAY511_API_KEY=bay511-api-key:latest,NVROADS_API_KEY=nvroads-api-key:latest
gcloud run services update ca-roads-demo --region us-west1   --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest,TOMTOM_API_KEY=tomtom-api-key:latest,BAY511_API_KEY=bay511-api-key:latest,NVROADS_API_KEY=nvroads-api-key:latest
```

| Variable | Source | Get a key at | Enables |
|---|---|---|---|
| `TOMTOM_API_KEY` | TomTom Traffic | developer.tomtom.com (free, 2,500 req/day) | Live speeds vs free-flow in check_route |
| `BAY511_API_KEY` | 511 SF Bay | 511.org/open-data/token (free) | Bay Area events in check_region |
| `NVROADS_API_KEY` | Nevada DOT | nvroads.com developer signup (free) | I-80/US-50/I-15 continuations past the state line |

