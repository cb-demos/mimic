# Mimic

A CloudBees demo scenario orchestration service with MCP (Model Context Protocol) support.

## Features

- **Web Interface**: Interactive UI for scenario management and resource cleanup
- **REST API**: Programmatic access to scenario execution and management
- **MCP Integration**: Model Context Protocol server for AI assistants (available at `/mcp`)

## MCP Usage

### For HTTP-compatible clients (Cursor, Claude Desktop, etc.)

```json
{
  "mcpServers": {
    "mimic": {
      "url": "https://mimic.cb-demos.io/mcp",
      "headers": {
        "EMAIL": "your-email@cloudbees.com",
        "UNIFY_API_KEY": "your_unify_api_key_here",
        "GITHUB_TOKEN": "optional_github_pat",
        "GITHUB_USERNAME": "optional_github_username"
      }
    }
  }
}
```

### For stdio-only clients (Amazon Q, etc.)

Use `mcp-remote` to wrap the HTTP endpoint:

```json
{
  "mcpServers": {
    "mimic": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://mimic.cb-demos.io/mcp",
        "--header",
        "EMAIL: ${EMAIL}",
        "--header",
        "UNIFY_API_KEY: ${UNIFY_API_KEY}",
        "--header",
        "GITHUB_TOKEN: ${GITHUB_TOKEN}",
        "--header",
        "GITHUB_USERNAME: ${GITHUB_USERNAME}"
      ],
      "env": {
        "EMAIL": "your-email@cloudbees.com",
        "UNIFY_API_KEY": "your_unify_api_key_here",
        "GITHUB_TOKEN": "optional_github_pat",
        "GITHUB_USERNAME": "optional_github_username"
      }
    }
  }
}
```

**Parameters:**
- `EMAIL`: Your CloudBees email address (required)
- `UNIFY_API_KEY`: Your CloudBees Unify API token (required)
- `GITHUB_TOKEN`: Custom GitHub PAT for private access (optional, defaults to service account)
- `GITHUB_USERNAME`: Your GitHub username (optional, used as default invitee)

### Available Tools

- `list_scenarios`: Get available demo scenarios
- `instantiate_scenario`: Execute a scenario with repositories, components, environments, and applications

## Deployment

Deploy as a web service with integrated MCP endpoint:

```bash
# Docker run
docker run -p 8000:8000 \
  -e GITHUB_TOKEN=your_token \
  -e UNIFY_API_KEY=your_key \
  -e PAT_ENCRYPTION_KEY=your_encryption_key \
  cloudbeesdemo/mimic:latest

# Docker Compose
services:
  mimic:
    image: cloudbeesdemo/mimic:latest
    ports:
      - "8000:8000"
    environment:
      - GITHUB_TOKEN=your_token
      - UNIFY_API_KEY=your_key
      - PAT_ENCRYPTION_KEY=your_encryption_key
```

- Web UI: http://localhost:8000
- REST API: http://localhost:8000/api/
- MCP endpoint: http://localhost:8000/mcp

## Scenario Authoring

See [scenarios/README.md](scenarios/README.md) for details on creating new demo scenarios.

## Development

```bash
# Run development server (includes MCP at /mcp)
make dev

# Run tests
make test

# Build Docker image
make build
```