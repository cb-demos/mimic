# Mimic CLI Guide for AI Agents

Mimic orchestrates CloudBees Unify demo scenarios: GitHub repos, CI/CD components, environments, applications, and feature flags from YAML templates.

## Quick Start

```bash
# First-time setup
mimic setup

# List scenarios
mimic list

# Run scenario (interactive)
mimic run hackers-app

# Run scenario (automated)
mimic run hackers-app \
  --set project_name=demo-123 \
  --set target_org=my-github-org \
  --org-id abc-123-uuid \
  --expires-in 7 \
  --yes

# Cleanup
mimic cleanup list
mimic cleanup expired --force
```

## Core Commands

### Scenarios
```bash
mimic list                               # List available scenarios
mimic run <scenario-id>                  # Interactive mode
mimic run <id> -f params.json --yes     # Automated mode
mimic run <id> --dry-run                # Preview without creating
mimic run <id> --set key=value          # Set parameters inline
mimic run <id> --verbose                # Debug mode
```

### Cleanup
```bash
mimic cleanup list                       # List all instances
mimic cleanup list --expired-only       # Show expired only
mimic cleanup run <id>                   # Clean specific instance
mimic cleanup run <id> --dry-run        # Preview cleanup
mimic cleanup expired                    # Clean all expired
```

### Environments
```bash
mimic env list                           # List environments
mimic env add prod                       # Add preset (prod/preprod/demo)
mimic env add custom --url <url> --endpoint-id <id>
mimic env select <name>                  # Switch environment
mimic env set-property <name> <key> <value>
mimic env remove <name>
```

### Configuration
```bash
mimic config show                        # Show configuration
mimic config github-token                # Update GitHub PAT
mimic config properties                  # Browse org properties/secrets
mimic config add-property                # Add property/secret
```

### Scenario Packs
```bash
mimic pack list                          # List packs
mimic pack add official https://github.com/cb-demos/mimic-scenarios
mimic pack add local ~/dev/my-scenarios # Local development
mimic pack update                        # Update all packs
mimic pack enable/disable <name>
```

## Parameter Files

JSON format for `--file` / `-f`:
```json
{
  "project_name": "my-demo",
  "target_org": "my-github-org",
  "enable_feature": true
}
```

## Environment Variables

```bash
MIMIC_CONFIG_DIR=/custom/path          # Override config location
```

## Common Workflows

**Setup new demo:**
```bash
mimic run hackers-app --set project_name=demo-$(date +%s) --set target_org=acme --yes
```

**Automated cleanup:**
```bash
mimic cleanup expired --force
```

**Multi-environment:**
```bash
mimic env select preprod
mimic run scenario-id -f params.json --yes
```

## Understanding Output

**Success indicators:**
```
✓ Created GitHub repository: org/repo
✓ Created CloudBees component: component-name
✓ Created CloudBees environment: env-name
Instance ID: abc123def456 (expires: 2025-01-15)
```

**Common errors:**
- "No environment configured" → `mimic env add prod`
- "Scenario not found" → `mimic list` or `mimic pack update`
- "Credential validation failed" → `mimic env add prod` (re-add with valid PAT)
- "GitHub App not installed" → Install CloudBees GitHub App (link in error)
- "Required property 'X' not found" → `mimic config add-property`

## Creating Scenarios

Minimal scenario (YAML):
```yaml
id: my-scenario
name: My Demo
summary: Brief description

parameter_schema:
  properties:
    project_name:
      type: string
      pattern: "^[a-z0-9-]+$"
    target_org:
      type: string
  required: [project_name, target_org]

repositories:
  - source: "template-org/template-repo"
    target_org: "${target_org}"
    repo_name_template: "${project_name}"
    create_component: true
    replacements:
      PROJECT_NAME: "${project_name}"
      API_URL: "${env.UNIFY_API}"
    files_to_modify: ["README.md"]

environments:
  - name: "${project_name}-prod"
    create_fm_token_var: true
    flags: ["new-feature"]

applications:
  - name: "${project_name}-app"
    components: ["${project_name}"]
    environments: ["${project_name}-prod"]

flags:
  - name: "new-feature"
    type: boolean
```

Variables: `${param}` for parameters, `${env.PROPERTY}` for environment config, `${organization_id}` runtime var.

See `scenarios/README.md` for full API reference.

## Best Practices

- Use `--dry-run` before creating resources
- Set appropriate `--expires-in` (1, 7, 14, or 30 days)
- Use unique project names: `demo-$(date +%s)`
- Enable `--verbose` for debugging
- Clean up expired resources regularly: `mimic cleanup expired`
- Use parameter files for complex scenarios
- Verify with `mimic cleanup list` after running

## Files

Config location: `~/.mimic/` (override with `MIMIC_CONFIG_DIR`)
- `config.yaml` - Environments, packs, settings
- `state.json` - Tracked instances for cleanup
- `scenario_packs/` - Cloned scenario repositories

## Help

```bash
mimic --help
mimic <command> --help
mimic upgrade               # Update tool and packs
```
