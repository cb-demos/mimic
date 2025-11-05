# Mimic

Tool for orchestrating demo scenarios on CloudBees Unify. Provides a CLI, web UI, and MCP server interface.

## Prerequisites

Mimic requires [uv](https://docs.astral.sh/uv/) to be installed on your system. Follow the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/) to install uv.

## Quick Start

### Installation

Install globally with uv:

```bash
uv tool install git+https://github.com/cb-demos/mimic
```

### Upgrading

To upgrade Mimic and all scenario packs to the latest versions:

```bash
mimic upgrade
```

This single command will:
1. Upgrade the Mimic tool itself (equivalent to `uv tool upgrade mimic`)
2. Update all scenario packs by pulling latest changes (equivalent to `mimic scenario-pack update`)

You can also upgrade components separately:

```bash
# Upgrade only the Mimic tool
uv tool upgrade mimic

# Update only scenario packs
mimic scenario-pack update
```

### First-Time Setup

Run the interactive setup wizard:

```bash
mimic setup
```

This will:
1. Add the official CloudBees scenario pack
2. Configure your CloudBees Unify environment (prod/preprod/demo)
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

## Web UI

Mimic includes a local web interface for users who prefer a graphical interface over the command line.

### Starting the Web UI

```bash
# Start the web server (auto-opens browser)
mimic ui

# Specify a custom port
mimic ui --port 3000

# Start without opening browser
mimic ui --no-browser
```

The web UI will automatically:
- Find an available port (default: 8080)
- Start a local FastAPI server
- Open your browser to http://localhost:8080
- Use your existing credentials from the OS keyring

### Features

The web UI provides full feature parity with the CLI:

**Setup & Configuration**
- First-run setup wizard (GitHub + CloudBees credentials)
- Environment management (add, switch, remove environments)
- Credential management (GitHub and CloudBees PATs)
- Scenario pack management (add, remove, enable/disable, update)

**Scenario Execution**
- Browse and search available scenarios
- Filter by scenario pack
- View scenario details and parameters
- Execute scenarios with real-time progress tracking
- Dynamic parameter forms with validation

**Resource Management**
- View all tracked sessions
- Filter by environment or expiration status
- Clean up individual sessions or batch cleanup expired sessions
- Dry-run mode to preview cleanup actions

**Dashboard**
- Overview of active and expired sessions
- Quick access to common actions
- Connection status indicators for GitHub and CloudBees

### Real-time Progress

When running scenarios, the web UI displays live progress updates:
- Current task and overall progress
- Resource creation status (repositories, components, environments, etc.)
- Success/error indicators
- Detailed logs of operations

Progress updates are streamed via Server-Sent Events (SSE) for instant feedback without polling.

### Security Model

The web UI follows the same security model as the CLI:
- **Local-only**: Server binds to localhost (127.0.0.1) only
- **No shared server**: Each user runs their own instance
- **OS Keyring**: Credentials stored securely via OS keyring
- **No authentication**: Not needed since it's local-only

### Development

To develop the web UI:

```bash
# Terminal 1: Start the FastAPI backend
mimic ui

# Terminal 2: Start the Vite dev server (with hot reload)
make dev-ui
# Opens at http://localhost:5173 with API proxy to port 8080
```

To build the production UI:

```bash
# Build React app to src/mimic/web/static/
make build-ui
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

### Backend (Python)

```bash
# Install Python dependencies
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

### Git Hooks

Install git hooks to automatically ensure code quality:

```bash
# Install pre-commit hook
make install-git-hooks
```

This installs:
- **Pre-commit hook**: Runs format, lint, typecheck, test, and build-ui before each commit

### Frontend (Web UI)

```bash
# Install frontend dependencies and build
make build-ui

# Run development server (with hot reload)
make dev-ui
```

### Building Docker Image

```bash
# Build multi-arch image with UI included
make build
# This runs build-ui first, then builds the Docker image
```
