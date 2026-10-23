"""uvicorn's access lines never carry a precise position."""

import io
import logging
import logging.config

from ca_roads_mcp.telemetry import uvicorn_log_config


def test_access_lines_round_coordinates_to_about_a_kilometer(monkeypatch):
    out = io.StringIO()
    config = uvicorn_log_config()
    config["handlers"]["access"]["stream"] = out
    logging.config.dictConfig(config)
    try:
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "10.0.0.1:1", "GET",
            "/api/speedlimit?lat=37.123456&lon=-121.987654&heading=270", "1.1", 200)
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "10.0.0.1:1", "GET",
            "/api/mapdata?at=28.61234%2C-81.54071&bbox=28.6,-81.6,28.7,-81.5", "1.1", 200)
    finally:
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})
    text = out.getvalue()
    assert "lat=37.12&lon=-121.99&heading=270" in text
    assert "at=28.61%2C-81.54" in text
    assert "123456" not in text and "54071" not in text
