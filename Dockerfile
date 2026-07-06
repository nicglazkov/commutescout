FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# [demo] adds the anthropic SDK so one image serves both Cloud Run services:
# default command runs the MCP server; the demo service overrides the command
# with ca-roads-demo.
RUN pip install --no-cache-dir ".[demo]"

ENV PORT=8080
EXPOSE 8080

CMD ["ca-roads-mcp", "--transport", "http"]
