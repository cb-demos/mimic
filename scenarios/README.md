# Scenario Templating System API Reference

Scenarios are YAML files defining complete CloudBees demo environments with repositories, components, environments, applications, and feature flags.

## Core Structure

```yaml
id: scenario-id                    # Required: Unique scenario identifier
name: Display Name                 # Required: Human-readable scenario name
description: Brief description     # Required: What this scenario creates
wip: true                         # Optional: Mark as work-in-progress
```

## Template Variables

Use `${variable_name}` syntax for dynamic substitution throughout any YAML value:
- Parameters from `parameter_schema`
- Computed variables from `computed_variables`
- Environment properties via `${env.property_name}`

### Environment Properties

Environment properties allow scenarios to access configuration specific to the CloudBees environment being used (prod, preprod, demo, or custom). These are automatically available in all scenarios using the `${env.property_name}` syntax.

**Built-in Properties** (always available):
- `${env.UNIFY_API}` - The CloudBees Unify API URL
- `${env.ENDPOINT_ID}` - The CloudBees endpoint ID

**Preset Environment Properties:**

| Environment | USE_VPC | FM_INSTANCE |
|------------|---------|-------------|
| `prod` | `false` | `cloudbees.io` |
| `preprod` | `true` | `saas-preprod.beescloud.com` |
| `demo` | `true` | `demo1.cloudbees.io` |

**Custom Properties** can be set per-environment:
```bash
# Set a property for an environment
mimic env set-property demo CUSTOM_PROP value

# Add environment with properties
mimic env add custom --url ... --endpoint-id ... --property USE_VPC=false
```

**Usage in Scenarios:**
```yaml
replacements:
  "API_URL": "${env.UNIFY_API}"          # Built-in property
  "USE_VPC": "${env.USE_VPC}"            # Custom property
  "FM_INSTANCE": "${env.FM_INSTANCE}"    # Custom property
  "PROJECT_NAME": "${project_name}"       # User parameter
```

## Required Properties and Secrets

Define organization-level properties or secrets that must exist before the scenario runs. Mimic will check for these and prompt the user to create any that are missing.

```yaml
# Simple list of property names (non-secret)
required_properties:
  - hostname
  - namespace
  - ENVIRONMENT_NAME

# Simple list of secret names (will be masked in UI)
required_secrets:
  - kubeconfig
  - JIRA_URL
  - JIRA_TOKEN
```

**Pre-flight Check Behavior:**
- Before running a scenario, Mimic checks if all required properties/secrets exist in the target organization
- If any are missing, the user is prompted to create them interactively
- Secrets are entered with hidden input and confirmation
- User can optionally skip and set them later
- All properties/secrets are created at the organization level

**Managing Properties:**
```bash
# Browse org properties/secrets
mimic config properties

# Add a new property/secret interactively
mimic config add-property
```

## Repository Configuration

```yaml
repositories:
  - source: "org/repo"                      # Required: template repo (org/repo format)
    target_org: "${target_org}"             # Required: destination GitHub org
    repo_name_template: "${project_name}"   # Required: new repository name
    create_component: true                   # Optional: create CloudBees component (boolean or template)

    # Content modification
    replacements:                            # Optional: string replacements in files
      OLD_TEXT: "${new_value}"
      PROJECT_NAME: "${project_name}"
    files_to_modify:                         # Required if replacements: files to modify
      - README.md
      - package.json

    # GitHub Actions secrets
    secrets:                                 # Optional: repository secrets to create
      SECRET_NAME: "${secret_value}"
      API_KEY: "hardcoded-value"

    # Conditional file operations
    conditional_file_operations:             # Optional: file moves based on parameters
      - condition_parameter: "auto_setup"    # Parameter that controls operation
        operation: "move"                    # Operation type (move, copy, delete)
        when_true:                           # Operations when parameter is true
          "source.yaml": ".cloudbees/workflows/source.yaml"
        when_false:                          # Operations when parameter is false
          "source.yaml": "unused/source.yaml"
```

## Environment Configuration

```yaml
environments:
  - name: "${env_name}"                      # Required: environment name
    env:                                     # Optional: environment variables
      - name: "NAMESPACE"                    # Variable name
        value: "${project_name}-prod"        # Variable value (supports templates)
    create_fm_token_var: true               # Optional: auto-create FM_TOKEN from SDK key
    flags:                                   # Optional: flags to enable in this environment
      - "feature-toggle"
      - "debug-mode"
```

## Application Configuration

```yaml
applications:
  - name: "${app_name}"                      # Required: application name
    repository: "${target_org}/${repo_name}" # Optional: primary repository URL
    components:                              # Optional: linked component names
      - "${project_name}-web"
      - "${project_name}-api"
    environments:                            # Optional: linked environment names
      - "${project_name}-prod"
      - "${project_name}-staging"
```

## Feature Flags

```yaml
flags:
  - name: "feature-name"                     # Required: flag name
    type: "boolean"                          # Required: boolean, string, number
```

## Parameter Schema

Define user inputs with validation:

```yaml
parameter_schema:
  properties:
    param_name:
      type: string                           # Required: string, number, boolean
      description: "User-facing description" # Optional: help text
      placeholder: "example-value"           # Optional: input placeholder
      pattern: "^[a-z0-9-]+$"               # Optional: regex validation
      enum: ["dev", "staging", "prod"]       # Optional: allowed values
      default: "default-value"               # Optional: default value
  required:                                  # Optional: list of required parameters
    - param_name
```

## Computed Variables

Create variables from other parameters:

```yaml
computed_variables:
  computed_name:
    default_from: "source_parameter"         # Use this parameter's value if non-empty
    fallback_template: "${other_param}-suffix" # Use this template if source_parameter is empty
```

## Template Variable Resolution Order

1. User-provided parameters (from `parameter_schema`)
2. Computed variables (processed in definition order)
3. Environment properties (from current environment configuration)
4. Template substitution using `${variable_name}` and `${env.property}` syntax
5. Type conversion (string booleans → actual booleans)

**Variable Precedence:**
- User parameters: `${parameter_name}` - from user input
- Environment properties: `${env.property_name}` - from environment config
- If a property exists in both namespaces, they remain separate (no conflicts)

## File Operations

### Content Replacements
Applied to files listed in `files_to_modify`:
- String-based find/replace using `replacements` map
- Supports template variables in replacement values

### Conditional File Operations
Based on boolean parameter values:
- `move`: Relocate files (delete source, create destination)
- `copy`: Duplicate files (keep source, create destination)
- `delete`: Remove files

### GitHub Actions Secrets
Automatically encrypted and stored as repository secrets:
- Uses repository's public key for encryption
- Supports template variables in secret values

## Validation Rules

### Startup Validation
- YAML syntax correctness
- Required fields presence
- Schema structure validation
- Source repository format (`org/repo`)

### Runtime Validation
- Parameter type checking
- Required parameter presence
- Pattern matching (regex)
- Enum value validation
- Template variable resolution

## Processing Pipeline

1. **Repository Creation**: Clone from templates, apply content modifications
2. **Component Creation**: Create CloudBees components for flagged repositories
3. **Flag Storage**: Store flag definitions for later application creation
4. **Environment Creation**: Create environments with custom variables
5. **Application Creation**: Link components and environments
6. **FM_TOKEN Injection**: Add SDK keys to environments requiring them
7. **Flag Configuration**: Enable flags across specified environments (initially off)

## Examples

### Simple Single Repository
```yaml
id: basic-demo
name: Basic Demo
description: Single repository setup
repositories:
  - source: "templates/basic-app"
    target_org: "${target_org}"
    repo_name_template: "${project_name}"
    create_component: false
parameter_schema:
  properties:
    project_name:
      type: string
      pattern: "^[a-z0-9-]+$"
    target_org:
      type: string
  required: [project_name, target_org]
```

### More complex setup
```yaml
id: microservices
name: Microservices Demo
description: Multi-service application with feature flags
repositories:
  - source: "templates/web-app"
    target_org: "${target_org}"
    repo_name_template: "${project_name}-web"
    create_component: true
    replacements:
      PROJECT_NAME: "${project_name}"
    files_to_modify: ["README.md", "package.json"]
applications:
  - name: "${project_name}-app"
    components: ["${project_name}-web"]
    environments: ["${project_name}-prod"]
environments:
  - name: "${project_name}-prod"
    create_fm_token_var: true
    flags: ["new-ui"]
flags:
  - name: "new-ui"
    type: boolean
```
