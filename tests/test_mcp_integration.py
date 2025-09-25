"""Simple integration test for MCP server functionality."""

import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TestMCPIntegration:
    """Test MCP server integration using a real MCP client."""

    async def test_mcp_server_tools_registration(self):
        """Test that MCP server starts and registers tools correctly."""
        # Set up environment for the server
        env = os.environ.copy()
        env.update({"GITHUB_TOKEN": "test_token", "UNIFY_API_KEY": "test_key"})

        # Start the MCP server as subprocess
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "src.mcp_main"],
            cwd=str(Path(__file__).parent.parent),
            env=env,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the client
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]

                # Verify our tools are registered
                assert "list_scenarios" in tool_names
                assert "instantiate_scenario" in tool_names

                # Test list_scenarios tool
                result = await session.call_tool("list_scenarios", {})
                assert result.isError is False

                # Parse the result content
                content = result.content[0].text if result.content else ""
                scenarios = json.loads(content)

                # Verify we get scenarios back
                assert isinstance(scenarios, list)
                assert len(scenarios) > 0

                # Verify scenario structure
                scenario = scenarios[0]
                assert "id" in scenario
                assert "name" in scenario
                assert "description" in scenario

                # Should have at least the hackers-app scenario
                scenario_ids = [s["id"] for s in scenarios]
                assert "hackers-app" in scenario_ids

    async def test_mcp_instantiate_scenario_validation(self):
        """Test that instantiate_scenario validates parameters correctly."""
        env = os.environ.copy()
        env.update({"GITHUB_TOKEN": "test_token", "UNIFY_API_KEY": "test_key"})

        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "src.mcp_main"],
            cwd=str(Path(__file__).parent.parent),
            env=env,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Test with invalid scenario ID
                result = await session.call_tool(
                    "instantiate_scenario",
                    {
                        "scenario_id": "nonexistent",
                        "organization_id": "test-org",
                        "email": "test@cloudbees.com"
                    },
                )

                assert result.isError is True
                assert "not found" in str(result.content[0].text)

    def test_mcp_server_sync(self):
        """Synchronous wrapper for async tests."""
        asyncio.run(self.test_mcp_server_tools_registration())

    def test_mcp_validation_sync(self):
        """Synchronous wrapper for validation test."""
        asyncio.run(self.test_mcp_instantiate_scenario_validation())
