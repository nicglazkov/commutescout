# Deploying to Cloud Run

The server runs as a single Cloud Run service using the streamable HTTP
transport. Scale-to-zero is fine: cold starts are a few seconds and the data
is fetched fresh anyway.

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
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 20 \
  --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --set-env-vars DEMO_MODEL=claude-sonnet-5,TELEMETRY_SALT=<random 32 chars>
```

## Cold starts

Both services run with `--min-instances 0`, so an idle service costs
nothing and the first visitor after ~15 idle minutes pays a cold start.
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

