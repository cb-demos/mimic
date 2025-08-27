# Scenario Authoring Guide

Scenarios are YAML files that define complete CloudBees demo environments including repositories, components, environments, applications, and feature flags.

## Basic Structure

```yaml
id: my-scenario
name: My Demo Scenario  
description: A complete demo environment
repositories:
  - source: template-org/template-repo
    target_org: "${target_org}"
    repo_name_template: "${project_name}-web"
    create_component: true
    replacements:
      PROJECT_NAME: "${project_name}"
    files_to_modify:
      - README.md
applications:
  - name: "${project_name}-app"
    repository: "${target_org}/${project_name}-app"
    components:
      - "${project_name}-web"
    environments:
      - "${project_name}-prod"
environments:
  - name: "${project_name}-prod"
    env:
      - name: ENV_VAR
        value: production
flags:
  - name: new-feature
    type: boolean
parameter_schema:
  properties:
    project_name:
      type: string
      description: Name for the project
    target_org:
      type: string 
      description: GitHub organization to create repositories in
  required:
    - project_name
    - target_org
```

## Template Variables

Use `${variable_name}` syntax for dynamic values:
- Custom parameters defined in `parameter_schema`

## Repository Configuration

- `source`: Template repository in `org/repo` format
- `target_org`: GitHub organization for new repositories
- `repo_name_template`: Name pattern for created repository
- `create_component`: Whether to create a CloudBees component
- `replacements`: String replacements in repository files
- `files_to_modify`: Files to apply replacements to
- `secrets`: Repository secrets to create

## Parameter Schema

Define required and optional parameters:

```yaml
parameter_schema:
  properties:
    param_name:
      type: string|number|boolean
      description: Human-readable description
      pattern: "^[a-z-]+$"  # Optional regex validation
      enum: ["option1", "option2"]  # Optional allowed values
      default: "default-value"  # Optional default
  required:
    - param_name
```

## Examples

See existing scenarios:
- `hackers-app.yaml` - Full application with multiple repos
- `hackers-organized.yaml` - Simple single repository

## Validation

Scenarios are validated on startup. Check logs for syntax errors or missing required fields.