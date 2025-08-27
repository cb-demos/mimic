"""
MCP server entrypoint for Mimic application.

This module provides the main entry point for running Mimic as an MCP server,
allowing AI assistants to interact with the scenario management capabilities.
"""

from src.mcp_server import mcp
from src.scenarios import initialize_scenarios


def main():
    """Main entry point for MCP server."""
    # Initialize scenario manager at startup
    initialize_scenarios("scenarios")
    print("✓ Scenario manager initialized for MCP server")

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
