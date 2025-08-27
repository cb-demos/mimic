import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ParameterProperty(BaseModel):
    """Schema for a single parameter property."""

    type: str
    pattern: str | None = None
    description: str | None = None
    default: Any = None
    enum: list[str] | None = None


class ParameterSchema(BaseModel):
    """Schema for scenario parameters."""

    properties: dict[str, ParameterProperty]
    required: list[str] = Field(default_factory=list)


class RepositoryConfig(BaseModel):
    """Configuration for a repository to be created from template."""

    source: str  # template_org/template_repo format
    target_org: str  # Target GitHub organization
    repo_name_template: str
    create_component: bool = False  # Whether to create a CloudBees component
    replacements: dict[str, str] = Field(default_factory=dict)
    files_to_modify: list[str] = Field(default_factory=list)
    secrets: dict[str, str] = Field(default_factory=dict)

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError("source must be in format 'org/repo'")
        return v


class EnvironmentVariable(BaseModel):
    """Environment variable configuration."""

    name: str
    value: str


class EnvironmentConfig(BaseModel):
    """Configuration for a CloudBees environment."""

    name: str
    env: list[EnvironmentVariable] = Field(default_factory=list)
    create_fm_token_var: bool = False  # Whether to create FM_TOKEN secret
    flags: list[str] = Field(default_factory=list)  # List of flag names to configure


class FlagConfig(BaseModel):
    """Configuration for a feature flag."""

    name: str
    type: str = "boolean"  # boolean, string, number, etc.


class ApplicationConfig(BaseModel):
    """Configuration for a CloudBees application."""

    name: str
    repository: str | None = None  # Optional repository URL
    components: list[str] = Field(default_factory=list)  # Component name templates
    environments: list[str] = Field(default_factory=list)  # Environment name templates


class Scenario(BaseModel):
    """A complete scenario definition."""

    id: str
    name: str
    description: str
    repositories: list[RepositoryConfig]
    applications: list[ApplicationConfig] = Field(default_factory=list)
    environments: list[EnvironmentConfig] = Field(default_factory=list)
    flags: list[FlagConfig] = Field(default_factory=list)
    parameter_schema: ParameterSchema | None = None

    def resolve_template_variables(self, values: dict[str, Any]) -> "Scenario":
        """
        Resolve ${variable} patterns in the scenario configuration.

        Args:
            values: Dictionary of parameter values

        Returns:
            A copy of the scenario with all template variables resolved
        """
        import json

        # Convert scenario to dict for easier manipulation
        scenario_dict = json.loads(self.model_dump_json())

        # Pattern to match ${variable_name}
        pattern = re.compile(r"\$\{([^}]+)\}")

        def replace_in_value(value: Any) -> Any:
            """Recursively replace template variables in any value."""
            if isinstance(value, str):
                # Replace all ${var} patterns with actual values
                def replacer(match):
                    var_name = match.group(1)
                    if var_name not in values:
                        raise ValueError(
                            f"Variable '{var_name}' not provided in values"
                        )
                    return str(values[var_name])

                return pattern.sub(replacer, value)
            elif isinstance(value, dict):
                return {k: replace_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(item) for item in value]
            else:
                return value

        # Apply replacements throughout the scenario
        resolved = replace_in_value(scenario_dict)

        # Create a new Scenario instance from the resolved dict
        return Scenario(**resolved)

    def validate_input(self, values: dict[str, Any]) -> None:
        """
        Validate input values against the parameter schema.

        Args:
            values: Dictionary of parameter values to validate

        Raises:
            ValueError: If validation fails
        """
        if not self.parameter_schema:
            if values:
                raise ValueError("This scenario doesn't accept parameters")
            return

        # Check required parameters
        for required in self.parameter_schema.required:
            if required not in values:
                raise ValueError(f"Required parameter '{required}' not provided")

        # Validate each provided parameter
        for key, value in values.items():
            if key not in self.parameter_schema.properties:
                raise ValueError(f"Unknown parameter '{key}'")

            prop = self.parameter_schema.properties[key]

            # Validate type
            if prop.type == "string" and not isinstance(value, str):
                raise ValueError(f"Parameter '{key}' must be a string")
            elif prop.type == "number" and not isinstance(value, int | float):
                raise ValueError(f"Parameter '{key}' must be a number")
            elif prop.type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"Parameter '{key}' must be a boolean")

            # Validate pattern if specified
            if prop.pattern and isinstance(value, str):
                if not re.match(prop.pattern, value):
                    raise ValueError(
                        f"Parameter '{key}' doesn't match pattern '{prop.pattern}'"
                    )

            # Validate enum if specified
            if prop.enum and value not in prop.enum:
                raise ValueError(f"Parameter '{key}' must be one of {prop.enum}")


class ScenarioManager:
    """Manages loading and accessing scenarios."""

    def __init__(self, scenarios_dir: Path | str = "scenarios"):
        self.scenarios_dir = Path(scenarios_dir)
        self.scenarios: dict[str, Scenario] = {}
        self.load_scenarios()

    def load_scenarios(self) -> None:
        """Load all YAML scenario files from the scenarios directory."""
        if not self.scenarios_dir.exists():
            raise FileNotFoundError(
                f"Scenarios directory not found: {self.scenarios_dir}"
            )

        yaml_files = self.scenarios_dir.glob("*.yaml")
        yaml_files = list(yaml_files) + list(self.scenarios_dir.glob("*.yml"))

        if not yaml_files:
            print(f"Warning: No scenario files found in {self.scenarios_dir}")
            return

        for yaml_file in yaml_files:
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)

                # Parse parameter schema if present
                if "parameter_schema" in data and data["parameter_schema"]:
                    # Convert nested dicts to proper models
                    properties = {}
                    for prop_name, prop_data in (
                        data["parameter_schema"].get("properties", {}).items()
                    ):
                        properties[prop_name] = ParameterProperty(**prop_data)

                    data["parameter_schema"] = ParameterSchema(
                        properties=properties,
                        required=data["parameter_schema"].get("required", []),
                    )

                # Parse repository configs
                repos = []
                for repo_data in data.get("repositories", []):
                    repos.append(RepositoryConfig(**repo_data))
                data["repositories"] = repos

                # Parse application configs
                apps = []
                for app_data in data.get("applications", []):
                    apps.append(ApplicationConfig(**app_data))
                data["applications"] = apps

                # Parse environment configs
                envs = []
                for env_data in data.get("environments", []):
                    # Convert nested env vars
                    env_vars = []
                    for var_data in env_data.get("env", []):
                        env_vars.append(EnvironmentVariable(**var_data))
                    env_data["env"] = env_vars
                    envs.append(EnvironmentConfig(**env_data))
                data["environments"] = envs

                # Parse flag configs
                flags = []
                for flag_data in data.get("flags", []):
                    flags.append(FlagConfig(**flag_data))
                data["flags"] = flags

                # Create and validate scenario
                scenario = Scenario(**data)
                self.scenarios[scenario.id] = scenario
                print(f"✓ Loaded scenario: {scenario.id} ({yaml_file.name})")

            except Exception as e:
                print(f"✗ Failed to load {yaml_file.name}: {e}")
                raise

    def get_scenario(self, scenario_id: str) -> Scenario | None:
        """Get a scenario by ID."""
        return self.scenarios.get(scenario_id)

    def list_scenarios(self) -> list[dict[str, Any]]:
        """List all available scenarios with their schemas."""
        result: list[dict[str, Any]] = []
        for scenario in self.scenarios.values():
            scenario_info: dict[str, Any] = {
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
            }

            # Include parameter schema if present
            if scenario.parameter_schema:
                schema_dict = {}
                for prop_name, prop in scenario.parameter_schema.properties.items():
                    schema_dict[prop_name] = {
                        "type": prop.type,
                        "description": prop.description,
                        "pattern": prop.pattern,
                        "enum": prop.enum,
                        "required": prop_name in scenario.parameter_schema.required,
                    }
                scenario_info["parameters"] = schema_dict

            result.append(scenario_info)

        return result


# Global instance to be created at startup
scenario_manager: ScenarioManager | None = None


def initialize_scenarios(scenarios_dir: Path | str = "scenarios") -> ScenarioManager:
    """Initialize the global scenario manager."""
    global scenario_manager
    scenario_manager = ScenarioManager(scenarios_dir)
    return scenario_manager


def get_scenario_manager() -> ScenarioManager:
    """Get the global scenario manager instance."""
    if scenario_manager is None:
        raise RuntimeError(
            "Scenario manager not initialized. Call initialize_scenarios() first."
        )
    return scenario_manager
