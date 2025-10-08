import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from mimic.exceptions import ScenarioError, ValidationError

logger = logging.getLogger(__name__)


class ParameterProperty(BaseModel):
    """Schema for a single parameter property."""

    type: str
    pattern: str | None = None
    description: str | None = None
    placeholder: str | None = None
    default: Any = None
    enum: list[str] | None = None


class ParameterSchema(BaseModel):
    """Schema for scenario parameters."""

    properties: dict[str, ParameterProperty]
    required: list[str] = Field(default_factory=list)


class ConditionalFileOperation(BaseModel):
    """Configuration for conditional file operations."""

    condition_parameter: str  # Parameter name that controls this operation
    operation: str = "move"  # Type of operation: "move", "copy", "delete"
    when_true: dict[str, str] = Field(
        default_factory=dict
    )  # source_path -> destination_path when condition is True
    when_false: dict[str, str] = Field(
        default_factory=dict
    )  # source_path -> destination_path when condition is False


class RepositoryConfig(BaseModel):
    """Configuration for a repository to be created from template."""

    source: str  # template_org/template_repo format
    target_org: str  # Target GitHub organization
    repo_name_template: str
    create_component: bool | str = (
        False  # Whether to create a CloudBees component (can be template string)
    )
    replacements: dict[str, str] = Field(default_factory=dict)
    files_to_modify: list[str] = Field(default_factory=list)
    conditional_file_operations: list[ConditionalFileOperation] = Field(
        default_factory=list
    )
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


class ComputedVariable(BaseModel):
    """Configuration for a computed variable."""

    default_from: str  # Parameter name to use as default
    fallback_template: str  # Template to use if default_from is empty/missing


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
    summary: str
    details: str | None = None
    repositories: list[RepositoryConfig]
    applications: list[ApplicationConfig] = Field(default_factory=list)
    environments: list[EnvironmentConfig] = Field(default_factory=list)
    flags: list[FlagConfig] = Field(default_factory=list)
    parameter_schema: ParameterSchema | None = None
    computed_variables: dict[str, ComputedVariable] = Field(default_factory=dict)
    wip: bool = False
    pack_source: str | None = None  # Track which pack this scenario came from

    def resolve_template_variables(
        self, values: dict[str, Any], env_properties: dict[str, str] | None = None
    ) -> "Scenario":
        """
        Resolve ${variable} and ${env.property} patterns in the scenario configuration.

        Args:
            values: Dictionary of parameter values
            env_properties: Optional dictionary of environment properties (accessible via ${env.X})

        Returns:
            A copy of the scenario with all template variables resolved
        """
        import json

        # Create a copy of values and add computed variables
        resolved_values = values.copy()
        env_props = env_properties or {}

        # Process computed variables
        for var_name, computed_var in self.computed_variables.items():
            # Check if the default_from parameter has a non-empty value
            if (
                computed_var.default_from in resolved_values
                and resolved_values[computed_var.default_from]
                and str(resolved_values[computed_var.default_from]).strip()
            ):
                # Use the value from default_from parameter
                resolved_values[var_name] = resolved_values[computed_var.default_from]
            else:
                # Use the fallback template - need to resolve it first
                fallback_pattern = re.compile(r"\$\{([^}]+)\}")

                def fallback_replacer(match, current_var_name=var_name):
                    fallback_var_name = match.group(1)
                    if fallback_var_name not in resolved_values:
                        raise ValueError(
                            f"Variable '{fallback_var_name}' not provided in values for computed variable '{current_var_name}'"
                        )
                    return str(resolved_values[fallback_var_name])

                resolved_values[var_name] = fallback_pattern.sub(
                    fallback_replacer, computed_var.fallback_template
                )

        # Convert scenario to dict for easier manipulation
        scenario_dict = json.loads(self.model_dump_json())

        # Pattern to match ${variable_name} or ${env.property_name}
        pattern = re.compile(r"\$\{([^}]+)\}")

        def replace_in_value(value: Any) -> Any:
            """Recursively replace template variables in any value."""
            if isinstance(value, str):
                # Replace all ${var} and ${env.prop} patterns with actual values
                def replacer(match):
                    var_name = match.group(1)

                    # Check if this is an environment property reference (env.PROPERTY)
                    if var_name.startswith("env."):
                        prop_name = var_name[4:]  # Remove "env." prefix
                        if prop_name not in env_props:
                            raise ValueError(
                                f"Environment property '{prop_name}' not available. "
                                f"Available properties: {list(env_props.keys())}"
                            )
                        return str(env_props[prop_name])
                    else:
                        # Regular user parameter
                        if var_name not in resolved_values:
                            raise ValueError(
                                f"Variable '{var_name}' not provided in values"
                            )
                        return str(resolved_values[var_name])

                return pattern.sub(replacer, value)
            elif isinstance(value, dict):
                return {k: replace_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(item) for item in value]
            else:
                return value

        # Apply replacements throughout the scenario
        resolved = replace_in_value(scenario_dict)

        # Post-process resolved data to convert string booleans to actual booleans
        self._convert_string_booleans(resolved)

        # Create a new Scenario instance from the resolved dict
        return Scenario(**resolved)

    def _convert_string_booleans(self, data: Any) -> None:
        """Convert string representations of booleans to actual boolean values."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "create_component" and isinstance(value, str):
                    # Convert string boolean to actual boolean
                    if value.lower() == "true":
                        data[key] = True
                    elif value.lower() == "false":
                        data[key] = False
                elif isinstance(value, dict | list):
                    self._convert_string_booleans(value)
        elif isinstance(data, list):
            for item in data:
                self._convert_string_booleans(item)

    def _preprocess_form_data(self, values: dict[str, Any]) -> dict[str, Any]:
        """
        Preprocess form data to handle checkbox values and other form-specific conversions.

        Args:
            values: Raw form data

        Returns:
            Processed values with proper types
        """
        if not self.parameter_schema:
            return values

        processed = values.copy()

        for prop_name, prop in self.parameter_schema.properties.items():
            if prop.type == "boolean":
                # Handle checkbox form data: missing = False, "on" = True, actual boolean = pass through
                if prop_name in processed:
                    value = processed[prop_name]
                    if value == "on" or value == "true" or value is True:
                        processed[prop_name] = True
                    elif (
                        value == "off"
                        or value == "false"
                        or value == ""
                        or value is False
                    ):
                        processed[prop_name] = False
                else:
                    # Checkbox not present in form = False
                    processed[prop_name] = False

        return processed

    def validate_input(self, values: dict[str, Any]) -> dict[str, Any]:
        """
        Validate input values against the parameter schema.

        Args:
            values: Dictionary of parameter values to validate

        Returns:
            Preprocessed and validated parameter values

        Raises:
            ValueError: If validation fails
        """
        if not self.parameter_schema:
            if values:
                raise ValidationError("This scenario doesn't accept parameters")
            return {}

        # Preprocess form data (handle checkboxes, etc.)
        processed_values = self._preprocess_form_data(values)

        # Check required parameters
        for required in self.parameter_schema.required:
            if required not in processed_values:
                raise ValidationError(
                    f"Required parameter '{required}' not provided", required
                )

        # Validate each provided parameter
        for key, value in processed_values.items():
            if key not in self.parameter_schema.properties:
                raise ValidationError(f"Unknown parameter '{key}'", key)

            prop = self.parameter_schema.properties[key]

            # Validate type
            if prop.type == "string" and not isinstance(value, str):
                raise ValidationError(f"Parameter '{key}' must be a string", key, value)
            elif prop.type == "number" and not isinstance(value, int | float):
                raise ValidationError(f"Parameter '{key}' must be a number", key, value)
            elif prop.type == "boolean" and not isinstance(value, bool):
                raise ValidationError(
                    f"Parameter '{key}' must be a boolean", key, value
                )

            # Validate pattern if specified (skip for empty optional parameters)
            if prop.pattern and isinstance(value, str):
                # Only validate pattern if value is non-empty or parameter is required
                is_required = key in self.parameter_schema.required
                if value or is_required:
                    if not re.match(prop.pattern, value):
                        raise ValidationError(
                            f"Parameter '{key}' doesn't match pattern '{prop.pattern}'",
                            key,
                            value,
                        )

            # Validate enum if specified
            if prop.enum and value not in prop.enum:
                raise ValidationError(
                    f"Parameter '{key}' must be one of {prop.enum}", key, value
                )

        return processed_values


class ScenarioManager:
    """Manages loading and accessing scenarios."""

    def __init__(
        self,
        scenarios_dirs: list[tuple[Path | str, str]] | None = None,
        local_dir: Path | str | None = "scenarios",
    ):
        """Initialize the scenario manager.

        Args:
            scenarios_dirs: List of (directory_path, pack_name) tuples to load from.
                          If None, only loads from local_dir.
            local_dir: Local scenarios directory (lowest priority). Set to None to disable.
        """
        self.scenarios_dirs = (
            [(Path(d), name) for d, name in scenarios_dirs] if scenarios_dirs else []
        )
        self.local_dir = Path(local_dir) if local_dir else None
        self.scenarios: dict[str, Scenario] = {}
        self.load_scenarios()

    def load_scenarios(self) -> None:
        """Load all YAML scenario files from configured directories.

        Loads scenarios in order:
        1. Scenario packs (from scenarios_dirs)
        2. Local scenarios directory (lowest priority)

        If there are ID conflicts, the last loaded scenario wins.
        """
        # Load from scenario packs first (higher priority)
        for scenarios_dir, pack_name in self.scenarios_dirs:
            self._load_from_directory(scenarios_dir, pack_name)

        # Load from local directory last (lowest priority)
        if self.local_dir and self.local_dir.exists():
            self._load_from_directory(self.local_dir, "local")

    def _load_from_directory(self, directory: Path, pack_name: str) -> None:
        """Load scenarios from a specific directory.

        Args:
            directory: Directory to load scenarios from.
            pack_name: Name of the pack (for tracking source).
        """
        if not directory.exists():
            logger.warning(f"Scenarios directory not found: {directory}")
            return

        yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))

        if not yaml_files:
            logger.debug(f"No scenario files found in {directory}")
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

                # Parse computed variables if present
                if "computed_variables" in data and data["computed_variables"]:
                    computed_vars = {}
                    for var_name, var_data in data["computed_variables"].items():
                        computed_vars[var_name] = ComputedVariable(**var_data)
                    data["computed_variables"] = computed_vars

                # Parse repository configs
                repos = []
                for repo_data in data.get("repositories", []):
                    # Parse conditional file operations if present
                    if "conditional_file_operations" in repo_data:
                        conditional_ops = []
                        for op_data in repo_data["conditional_file_operations"]:
                            conditional_ops.append(ConditionalFileOperation(**op_data))
                        repo_data["conditional_file_operations"] = conditional_ops

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
                scenario.pack_source = pack_name

                # Check for ID conflicts
                if scenario.id in self.scenarios:
                    existing_source = self.scenarios[scenario.id].pack_source
                    logger.warning(
                        f"Scenario ID conflict: '{scenario.id}' from '{pack_name}' "
                        f"overrides existing from '{existing_source}'"
                    )

                self.scenarios[scenario.id] = scenario
                print(
                    f"✓ Loaded scenario: {scenario.id} ({yaml_file.name}) from {pack_name}"
                )

            except yaml.YAMLError as e:
                error_msg = f"YAML parsing error in {yaml_file.name}: {e}"
                logger.error(error_msg)
                raise ScenarioError(error_msg) from e
            except Exception as e:
                error_msg = f"Failed to load scenario {yaml_file.name}: {e}"
                logger.error(error_msg)
                raise ScenarioError(error_msg) from e

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
                "summary": scenario.summary,
                "details": scenario.details,
                "pack_source": scenario.pack_source,
            }

            # Include parameter schema if present
            if scenario.parameter_schema:
                schema_dict = {}
                for prop_name, prop in scenario.parameter_schema.properties.items():
                    schema_dict[prop_name] = {
                        "type": prop.type,
                        "description": prop.description,
                        "placeholder": prop.placeholder,
                        "pattern": prop.pattern,
                        "enum": prop.enum,
                        "required": prop_name in scenario.parameter_schema.required,
                    }
                scenario_info["parameters"] = schema_dict

            result.append(scenario_info)

        return result


# Global instance to be created at startup
scenario_manager: ScenarioManager | None = None


def initialize_scenarios(
    scenarios_dirs: list[tuple[Path | str, str]] | Path | str | None = None,
    local_dir: Path | str | None = "scenarios",
) -> ScenarioManager:
    """Initialize the global scenario manager.

    Args:
        scenarios_dirs: List of (directory_path, pack_name) tuples to load from,
                       or a single directory path string for backward compatibility.
        local_dir: Local scenarios directory (lowest priority).

    Returns:
        Initialized ScenarioManager instance.
    """
    global scenario_manager

    # Handle backward compatibility: if scenarios_dirs is a string/Path, treat it as local_dir
    if isinstance(scenarios_dirs, str | Path):
        local_dir = scenarios_dirs
        scenarios_dirs = None

    scenario_manager = ScenarioManager(scenarios_dirs, local_dir)
    return scenario_manager


def get_scenario_manager() -> ScenarioManager:
    """Get the global scenario manager instance."""
    if scenario_manager is None:
        raise RuntimeError(
            "Scenario manager not initialized. Call initialize_scenarios() first."
        )
    return scenario_manager


def initialize_scenarios_from_config() -> ScenarioManager:
    """Initialize scenario manager from config file.

    Loads scenarios from enabled packs defined in config.yaml.

    Returns:
        Initialized ScenarioManager instance.
    """
    from mimic.config_manager import ConfigManager
    from mimic.scenario_pack_manager import ScenarioPackManager

    config_manager = ConfigManager()
    pack_manager = ScenarioPackManager(config_manager.packs_dir)

    # Get enabled scenario packs
    packs_config = config_manager.list_scenario_packs()
    scenarios_dirs = []

    for pack_name, pack_config in packs_config.items():
        if not pack_config.get("enabled", True):
            continue

        pack_path = pack_manager.get_pack_path(pack_name)
        if pack_path:
            scenarios_dirs.append((pack_path, pack_name))
        else:
            logger.warning(
                f"Scenario pack '{pack_name}' is enabled but not installed. "
                f"Run 'mimic scenario-pack update {pack_name}' to install it."
            )

    return initialize_scenarios(scenarios_dirs=scenarios_dirs, local_dir=None)
