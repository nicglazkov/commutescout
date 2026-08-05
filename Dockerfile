FROM node:22-slim AS site
WORKDIR /site
COPY site/package.json site/package-lock.json ./
RUN npm ci
COPY site/ ./
# globals.css imports the shared token sheet by the relative path
# ../../src/ca_roads_demo/static/tokens.css (from site/app/), and
# next.config.ts widens turbopack's root to one level above site/ for the
# same reason. Recreate that "site/ next to src/" layout here: WORKDIR is
# /site, so the sibling path one level up is /, and copying tokens.css to
# /src/ca_roads_demo/static/tokens.css makes both the CSS import and the
# turbopack root resolve exactly as they do in the repo checkout.
COPY src/ca_roads_demo/static/tokens.css /src/ca_roads_demo/static/tokens.css
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY src ./src
COPY --from=site /site/out ./src/ca_roads_demo/static/site

# [demo] adds the anthropic SDK so one image serves both Cloud Run services:
# default command runs the MCP server; the demo service overrides the command
# with ca-roads-demo.
#
# -c constraints.txt is not optional: without it the image resolves every
# dependency to whatever is newest at build time, so a release upstream
# breaks the deploy with no code change on our side. That happened on
# 2026-07-28, when a new mcp release dropped mcp.server.fastmcp and the
# container died on import while CI (which does use the constraints) stayed
# green.
RUN pip install --no-cache-dir -c constraints.txt ".[demo]"

# Run as a non-root user; nothing in the image needs write access.
RUN useradd --create-home --uid 1001 app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["ca-roads-mcp", "--transport", "http"]
