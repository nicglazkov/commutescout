"""initialize reports CommuteScout's version, not the MCP SDK's."""

from importlib.metadata import version

from ca_roads_mcp import server


def test_server_info_carries_the_app_version():
    opts = server.mcp._mcp_server.create_initialization_options()
    assert opts.server_name == "CommuteScout"
    assert opts.server_version == version("ca-roads-mcp")
    assert opts.server_version != version("mcp")
