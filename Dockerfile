FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY src ./src

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
