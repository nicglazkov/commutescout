# Working on ca-roads-mcp

## GCP project pinning (important)

Everything in this repo deploys to GCP project `ca-roads-mcp`
(15002631928, us-west1). This machine runs multiple agent sessions using
DIFFERENT gcloud projects, and the global gcloud config is shared mutable
state - never rely on it.

- Shells started inside this tree get `CLOUDSDK_CORE_PROJECT` and
  `GOOGLE_CLOUD_PROJECT` pinned via `.envrc` (direnv, interactive) and a
  `~/.bashrc` path guard (non-interactive tool shells).
- Before any deploy or gcloud mutation, verify:
  `gcloud config get-value project` must print `ca-roads-mcp`.
- If it does not, prefix the command with the env var or pass
  `--project ca-roads-mcp` explicitly. Never `gcloud config set project`
  (that mutates the shared global config other sessions depend on).

## Ground rules

- `docs-private/` is gitignored and must never be committed, quoted, or
  referenced in tracked files.
- Every change ships as a small PR; merge only after CI is SUCCESS with
  no PENDING checks (poll `gh pr checks --json state`, never trust piped
  output alone).
- Meaningful changes get a GitHub release (bump `pyproject.toml` and
  `server.json` together); both Cloud Run services redeploy after.
- The demo service must run with `--max-instances 1`: every rate and
  cost guard is in-process.
- Windows working tree is CRLF after checkout: normalize line endings
  before string-matching file contents in scripts, or use Read+Edit.
