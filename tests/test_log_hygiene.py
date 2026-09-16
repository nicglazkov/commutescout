"""Upstream feed keys must never reach Cloud Logging.

httpx logs "HTTP Request: GET <full url>" at INFO for every call, and
the state-feed URLs carry API keys as query parameters. FastMCP's
import-time basicConfig turns the root logger on at INFO in both
services, so the only safe default is httpx (and httpcore) at WARNING.
"""

import logging

import ca_roads_mcp.server  # noqa: F401 - importing configures logging


def test_httpx_request_lines_are_silenced():
    # Explicit levels: the root logger sits at INFO in production, so an
    # unset (NOTSET) level would inherit INFO and leak.
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING


def test_httpx_info_record_is_dropped(caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("httpx").info(
            "HTTP Request: GET https://example.test/?key=SECRET")
    assert "SECRET" not in caplog.text
