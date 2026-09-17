"""The Developers page renders site/lib/api-reference.json, generated
from the tools' schemas by scripts/gen_api_reference.py. The committed
file must match the generator, so the page cannot drift from the server."""

import json
import runpy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JSON_PATH = REPO / "site" / "lib" / "api-reference.json"
PAGE = (REPO / "site" / "app" / "developers" / "page.tsx").read_text(encoding="utf-8")


def _generator():
    return runpy.run_path(str(REPO / "scripts" / "gen_api_reference.py"), run_name="not_main")


def test_committed_reference_matches_the_tool_schemas():
    built = _generator()["build"]()
    committed = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert committed == built, "run scripts/gen_api_reference.py"
    assert len(built["tools"]) == 10
    for tool in built["tools"]:
        assert tool["params"], tool["name"]
        assert tool["example"].startswith(tool["name"] + "?") or tool["example"] == tool["name"]
        assert tool["poll_s"] >= 60
        for p in tool["params"]:
            assert p["doc"].endswith("."), (tool["name"], p["name"])


def test_page_renders_the_reference_and_covers_the_contract():
    assert 'from "@/lib/api-reference.json"' in PAGE
    for anchor in ("quickstart", "basics", "keys", "responses", "errors", "rules", "tools",
                   "mcp", "bulk", "flare", "terms"):
        assert f'id="{anchor}"' in PAGE, anchor
    # The error table names every code the bridge and the key middleware emit.
    rest = (REPO / "src" / "ca_roads_mcp" / "rest.py").read_text(encoding="utf-8")
    limiter = (REPO / "src" / "ca_roads_mcp" / "ratelimit.py").read_text(encoding="utf-8")
    for code in ("unknown_tool", "unknown_parameter", "missing_parameter", "invalid_parameter",
                 "tool_error", "upstream_error"):
        assert code in rest and f'"{code}"' in PAGE, code
    for code in ("invalid_key", "rate_limited", "daily_limit", "keys_unavailable"):
        assert code in limiter and f'"{code}"' in PAGE, code
    assert '"2,000"' in PAGE and '"10,000"' in PAGE  # Nic's tiers
    assert "Do not put a key in a web page" in PAGE
