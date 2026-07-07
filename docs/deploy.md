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
  --max-instances 2 \
  --concurrency 40
```

The MCP endpoint is `https://<service-url>/mcp`.

## Notes

- No secrets are needed: all upstream feeds are free and public.
- Rate limiting is per-IP in process (token bucket, 20 burst / 30 per
  minute sustained). `--max-instances 2` caps worst-case fan-out to the
  Caltrans feeds.
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
