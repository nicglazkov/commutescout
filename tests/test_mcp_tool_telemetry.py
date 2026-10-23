"""One mcp_tool event per tool call over HTTP, and nothing over stdio."""

import json

import pytest

from ca_roads_mcp import server


@pytest.fixture
def counted(monkeypatch):
    monkeypatch.setattr(server.mcp, "count_calls", True)


async def test_a_tool_call_logs_its_name_outcome_and_time_but_not_its_arguments(counted, capsys):
    await server.mcp.call_tool("rank_routes", {"by": "activity", "limit": 1})
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()
              if '"mcp_tool"' in line]
    assert len(events) == 1
    event = events[0]
    assert event["tool"] == "rank_routes"
    assert event["ok"] is True
    assert isinstance(event["duration_ms"], int)
    assert "arguments" not in event and "activity" not in json.dumps(event)


async def test_an_unknown_tool_is_logged_as_a_failure(counted, capsys):
    with pytest.raises(Exception):  # noqa: B017 - the SDK's ToolError
        await server.mcp.call_tool("no_such_tool", {})
    out = capsys.readouterr().out
    assert '"tool": "no_such_tool"' in out and '"ok": false' in out


async def test_stdio_stays_silent(capsys):
    assert server.mcp.count_calls is False
    with pytest.raises(Exception):  # noqa: B017
        await server.mcp.call_tool("no_such_tool", {})
    assert "mcp_tool" not in capsys.readouterr().out
