# Mimic

Internal CloudBees tool for orchestrating demo scenarios on CloudBees Platform with CLI/TUI/MCP interfaces.

## Quick Start

### Installation

Install globally with uv:

```bash
uv tool install git+https://github.com/cb-demos/mimic
```

### First-Time Setup

Run the interactive setup wizard:

```bash
mimic setup
```

This will:
1. Add the official CloudBees scenario pack
2. Configure your CloudBees Platform environment (prod/preprod/demo)
3. Set up your GitHub credentials

Or configure manually:

```bash
# Add CloudBees environment
mimic env add prod
# Prompts for your CloudBees PAT - stored securely in OS keyring

# Add GitHub credentials
mimic config github-token

# List available scenarios
mimic list

# Run a scenario
mimic run hackers-app
```

## Docker Usage

If you prefer not to install Python locally, you can run Mimic using Docker:

### Running Commands

```bash
# Show help
docker run --rm cloudbeesdemo/mimic:latest --help

# List scenarios (mount config directory for persistence)
docker run --rm -v ~/.mimic:/home/appuser/.mimic cloudbeesdemo/mimic:latest list

# Run a scenario interactively
docker run --rm -it -v ~/.mimic:/home/appuser/.mimic cloudbeesdemo/mimic:latest run hackers-app
```

### TUI Mode

```bash
# Launch interactive terminal UI
docker run --rm -it -v ~/.mimic:/home/appuser/.mimic cloudbeesdemo/mimic:latest tui
```

### MCP Server Mode

```bash
# Start stdio MCP server
docker run --rm -i -v ~/.mimic:/home/appuser/.mimic cloudbeesdemo/mimic:latest mcp
```

### Environment Management

```bash
# Set up environment
docker run --rm -it -v ~/.mimic:/home/appuser/.mimic cloudbeesdemo/mimic:latest env add prod

# Configure GitHub token
docker run --rm -it -v ~/.mimic:/home/appuser/.mimic cloudbeesdemo/mimic:latest config github-token
```

**Note**: The `-v ~/.mimic:/home/appuser/.mimic` mount is required to persist configuration and credentials between container runs.

## Configuration

### Config Directory

By default, Mimic stores configuration in `~/.mimic/`. You can customize this location using the `MIMIC_CONFIG_DIR` environment variable:

```bash
# Use a custom config directory
export MIMIC_CONFIG_DIR=/path/to/config
mimic env list

# Verify files are created in custom location
ls $MIMIC_CONFIG_DIR
# Output: config.yaml  state.json
```

```bash
# Example: Testing with temporary config
export MIMIC_CONFIG_DIR=/tmp/test-mimic
mimic env add prod
# ... test configuration ...
rm -rf /tmp/test-mimic

# Example: Project-specific configuration
export MIMIC_CONFIG_DIR=$(pwd)/.mimic
mimic env add demo
```

### Environment Variables

- **`MIMIC_CONFIG_DIR`**: Custom config directory (default: `~/.mimic`)
- **`MIMIC_ENV`**: Default environment for MCP server
- **`MIMIC_CLOUDBEES_PAT`**: CloudBees PAT (fallback if not in keyring)
- **`MIMIC_GITHUB_PAT`**: GitHub PAT (fallback if not in keyring)

## CLI Usage

### Environment Management

```bash
# Add a preset environment (prod, preprod, demo)
mimic env add prod

# Add a custom environment
mimic env add my-env --url https://api.example.com --endpoint-id abc-123

# List all environments
mimic env list

# Switch to an environment
mimic env select preprod

# Remove an environment
mimic env remove demo

# Configure GitHub credentials
mimic config github-token
```

### Scenario Execution

```bash
# List all available scenarios
mimic list

# Run a scenario (interactive prompts for parameters)
mimic run <scenario-id>

# Example
mimic run hackers-app
```

### Resource Cleanup

```bash
# List all tracked sessions
mimic cleanup list

# Clean up a specific session
mimic cleanup run <session-id>

# Clean up all expired sessions
mimic cleanup expired
```

## TUI Usage

Launch the interactive terminal UI:

```bash
mimic tui
```

## MCP Integration

Use Mimic with AI assistants via stdio MCP:

### Configuration for Claude Desktop

After installing Mimic system-wide, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mimic": {
      "command": "mimic",
      "args": ["mcp"],
      "env": {
        "MIMIC_ENV": "prod"
      }
    }
  }
}
```

The MCP server uses credentials from the OS keyring (configured via `mimic env add` or `mimic setup`).

### Available Tools

- `list_scenarios`: Get available demo scenarios
- `instantiate_scenario`: Execute a scenario with parameters
- `cleanup_session`: Clean up resources from a session

### Authentication

The MCP server loads credentials from:
1. Environment variables (if set): `MIMIC_ENV`, `GITHUB_TOKEN`, `UNIFY_API_KEY`
2. OS keyring (configured via CLI): `mimic env add`

## Scenario Packs

Mimic uses scenario packs to load demo scenarios from git repositories. This allows you to:
- Use the official CloudBees scenario pack (`cb-demos/mimic-scenarios`)
- Create and share custom scenario packs within your team
- Switch between different scenario collections

### Managing Scenario Packs

```bash
# List configured packs
mimic scenario-pack list

# Add the official pack
mimic scenario-pack add official https://github.com/cb-demos/mimic-scenarios

# Add a custom pack (supports SSH URLs for private repos)
mimic scenario-pack add my-team git@github.com:myorg/our-scenarios.git

# Update all packs
mimic scenario-pack update

# Update specific pack
mimic scenario-pack update official

# Enable/disable packs
mimic scenario-pack enable my-team
mimic scenario-pack disable my-team

# Remove a pack
mimic scenario-pack remove my-team
```

### Scenario Loading Priority

Scenarios are loaded in this order (last loaded wins for ID conflicts):
1. Enabled scenario packs (from config)
2. Local `scenarios/` directory (for development/testing)

### Authentication for Private Packs

Scenario packs use your local git configuration for authentication:
- **Public repos**: Use HTTPS URLs - `https://github.com/org/repo`
- **Private repos (SSH)**: Use SSH URLs - `git@github.com:org/repo.git`
- **Private repos (HTTPS)**: Requires git credential helper configured

The pack system delegates all authentication to git, so it works with your existing SSH keys and git credentials.

## Configuration Files

Mimic stores configuration in `~/.mimic/`:

- `config.yaml`: Environment definitions, scenario packs, and settings
- `state.json`: Resource tracking for cleanup
- `scenario_packs/`: Cloned scenario pack repositories

## Scenario Authoring

See [scenarios/README.md](scenarios/README.md) for details on creating new demo scenarios.

## Development

```bash
# Install dependencies
make install

# Run tests
make test

# Run linting
make lint

# Type checking
make typecheck

# Format code
make format
```
