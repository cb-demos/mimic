# Mimic

A CloudBees demo scenario orchestration service with MCP (Model Context Protocol) support.

## Modes

- **API/UI Mode**: Web interface and REST API for scenario management
- **MCP Mode**: Model Context Protocol server for AI assistants

## MCP Usage

Add this configuration to your MCP client:

```json
{
  "mcpServers": {
    "mimic": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-e", "MODE=mcp", "-e", "GITHUB_TOKEN", "-e", "UNIFY_API_KEY", "cloudbeesdemo/mimic:latest"],
      "env": {
        "GITHUB_TOKEN": "your_github_token_here",
        "UNIFY_API_KEY": "your_unify_api_key_here"
      }
    }
  }
}
```

### Available Tools

- `list_scenarios`: Get available demo scenarios
- `instantiate_scenario`: Execute a scenario with repositories, components, environments, and applications

## API/UI Deployment

Deploy as a web service:

```bash
# Docker run
docker run -p 8000:8000 \
  -e GITHUB_TOKEN=your_token \
  -e UNIFY_API_KEY=your_key \
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
      - MODE=api  # Optional: defaults to api
```

Access the web UI at http://localhost:8000 or use the REST API.

## Scenario Authoring

See [scenarios/README.md](scenarios/README.md) for details on creating new demo scenarios.

## Development

```bash
# Run API/UI mode
make dev

# Run MCP mode  
make mcp

# Run tests
make test

# Build Docker image
make build
```