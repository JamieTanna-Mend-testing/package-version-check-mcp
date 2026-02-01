"""Tests for the tool version check MCP server."""

import pytest
from fastmcp import Client

from package_version_check_mcp.main import mcp
from package_version_check_mcp.get_latest_tools_pkg.structs import GetLatestToolVersionsResponse


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client for testing."""
    async with Client(mcp) as client:
        yield client


@pytest.mark.parametrize("tool_name", [
    "terraform",
    "gradle",
    "maven",
    "kubectl",
    "helm",
    "node",
    "python",
    "java",
    "go",
])
async def test_get_latest_tool_versions_success(mcp_client: Client, tool_name):
    """Test fetching valid tool versions from mise."""
    result = await mcp_client.call_tool(
        name="get_latest_tool_versions",
        arguments={
            "tool_names": [tool_name]
        }
    )

    assert result.structured_content is not None
    response = GetLatestToolVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 1, \
        f"Expected 1 result, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert response.result[0].tool_name == tool_name
    assert "." in response.result[0].latest_version, \
        f"Version missing '.': {response.result[0].latest_version}"
    # Ensure the version starts with a digit (not vendor-specific like "zulu-")
    assert response.result[0].latest_version[0].isdigit(), \
        f"Version should start with digit: {response.result[0].latest_version}"
    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"


@pytest.mark.parametrize("tool_name", [
    "this-tool-definitely-does-not-exist-12345678",
    "nonexistent-tool-987654321",
])
async def test_get_latest_tool_versions_not_found(mcp_client: Client, tool_name):
    """Test fetching non-existent tools from mise."""
    result = await mcp_client.call_tool(
        name="get_latest_tool_versions",
        arguments={
            "tool_names": [tool_name]
        }
    )

    assert result.structured_content is not None
    response = GetLatestToolVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 0, \
        f"Expected 0 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"
    assert len(response.lookup_errors) == 1, \
        f"Expected 1 error, got {len(response.lookup_errors)}: {response.lookup_errors}. " \
        f"Results: {response.result}"
    assert response.lookup_errors[0].tool_name == tool_name
    assert (
        "error" in response.lookup_errors[0].error.lower()
        or "not found" in response.lookup_errors[0].error.lower()
    ), f"Error message: {response.lookup_errors[0].error}"


async def test_get_latest_tool_versions_multiple_tools(mcp_client: Client):
    """Test fetching multiple tool versions at once."""
    result = await mcp_client.call_tool(
        name="get_latest_tool_versions",
        arguments={
            "tool_names": ["terraform", "gradle", "kubectl"]
        }
    )

    assert result.structured_content is not None
    response = GetLatestToolVersionsResponse.model_validate(result.structured_content)
    assert len(response.result) == 3, \
        f"Expected 3 results, got {len(response.result)}: {response.result}. " \
        f"Errors: {response.lookup_errors}"

    tool_names = {r.tool_name for r in response.result}
    assert tool_names == {"terraform", "gradle", "kubectl"}, f"Got tool names: {tool_names}"

    for result_item in response.result:
        assert "." in result_item.latest_version, \
            f"Version missing '.' ({result_item.tool_name}): {result_item.latest_version}"
        assert result_item.latest_version[0].isdigit(), \
            f"Version should start with digit ({result_item.tool_name}): " \
            f"{result_item.latest_version}"

    assert len(response.lookup_errors) == 0, \
        f"Expected 0 errors, got {len(response.lookup_errors)}: {response.lookup_errors}"
