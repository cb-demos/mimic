import pytest

from mimic.exceptions import ValidationError
from mimic.scenarios import (
    ComputedVariable,
    EnvironmentConfig,
    EnvironmentVariable,
    ParameterProperty,
    ParameterSchema,
    RepositoryConfig,
    Scenario,
)


class TestComputedVariable:
    """Test ComputedVariable functionality."""

    def test_computed_variable_creation(self):
        """Test creating a ComputedVariable."""
        computed_var = ComputedVariable(
            default_from="custom_environment", fallback_template="${project_name}-prod"
        )
        assert computed_var.default_from == "custom_environment"
        assert computed_var.fallback_template == "${project_name}-prod"


class TestScenarioTemplateResolution:
    """Test scenario template resolution with computed variables."""

    def create_test_scenario(self) -> Scenario:
        """Create a test scenario with computed variables."""
        # Parameter schema
        parameter_schema = ParameterSchema(
            properties={
                "project_name": ParameterProperty(
                    type="string", description="Project name"
                ),
                "target_org": ParameterProperty(
                    type="string", description="Target organization"
                ),
                "create_component": ParameterProperty(
                    type="boolean",
                    default=False,
                    description="Create CloudBees component",
                ),
                "custom_environment": ParameterProperty(
                    type="string", description="Custom environment name"
                ),
            },
            required=["project_name", "target_org"],
        )

        # Computed variables
        computed_variables = {
            "environment_name": ComputedVariable(
                default_from="custom_environment",
                fallback_template="${project_name}-prod",
            )
        }

        # Repository config with template strings
        repository_config = RepositoryConfig(
            source="test-org/test-repo",
            target_org="${target_org}",
            repo_name_template="${project_name}",
            create_component="${create_component}",
            replacements={"PROJECT_NAME": "${project_name}"},
        )

        # Environment config
        environment_config = EnvironmentConfig(
            name="${environment_name}",
            env=[EnvironmentVariable(name="namespace", value="${environment_name}")],
        )

        return Scenario(
            id="test-scenario",
            name="Test Scenario",
            summary="Test scenario for computed variables",
            repositories=[repository_config],
            environments=[environment_config],
            parameter_schema=parameter_schema,
            computed_variables=computed_variables,
        )

    def test_computed_variable_fallback(self):
        """Test computed variable uses fallback when default_from is empty."""
        scenario = self.create_test_scenario()

        # Parameters without custom_environment
        params = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": True,
        }

        resolved = scenario.resolve_template_variables(params)

        # Should use fallback template
        assert resolved.environments[0].name == "test-project-prod"
        assert resolved.environments[0].env[0].value == "test-project-prod"

    def test_computed_variable_default_from(self):
        """Test computed variable uses default_from when provided."""
        scenario = self.create_test_scenario()

        # Parameters with custom_environment
        params = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": False,
            "custom_environment": "my-custom-env",
        }

        resolved = scenario.resolve_template_variables(params)

        # Should use custom_environment value
        assert resolved.environments[0].name == "my-custom-env"
        assert resolved.environments[0].env[0].value == "my-custom-env"

    def test_computed_variable_empty_string_uses_fallback(self):
        """Test computed variable uses fallback when default_from is empty string."""
        scenario = self.create_test_scenario()

        # Parameters with empty custom_environment
        params = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": True,
            "custom_environment": "",
        }

        resolved = scenario.resolve_template_variables(params)

        # Should use fallback template because custom_environment is empty
        assert resolved.environments[0].name == "test-project-prod"

    def test_boolean_template_resolution(self):
        """Test boolean template resolution from string to boolean."""
        scenario = self.create_test_scenario()

        # Test with True
        params_true = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": True,
        }

        resolved_true = scenario.resolve_template_variables(params_true)
        assert resolved_true.repositories[0].create_component is True
        assert isinstance(resolved_true.repositories[0].create_component, bool)

        # Test with False
        params_false = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": False,
        }

        resolved_false = scenario.resolve_template_variables(params_false)
        assert resolved_false.repositories[0].create_component is False
        assert isinstance(resolved_false.repositories[0].create_component, bool)

    def test_missing_computed_variable_dependency_raises_error(self):
        """Test that missing dependencies for computed variables raise errors."""
        scenario = self.create_test_scenario()

        # Parameters missing project_name (needed for fallback template)
        params = {"target_org": "test-org", "create_component": True}

        with pytest.raises(ValueError, match="Variable 'project_name' not provided"):
            scenario.resolve_template_variables(params)

    def test_parameter_validation_with_optional_params(self):
        """Test parameter validation with optional parameters."""
        scenario = self.create_test_scenario()

        # Required parameters only - should pass
        required_params = {"project_name": "test-project", "target_org": "test-org"}
        scenario.validate_input(required_params)

        # All parameters - should pass
        all_params = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": True,
            "custom_environment": "custom-env",
        }
        scenario.validate_input(all_params)

        # Missing required parameter - should fail
        missing_required = {
            "project_name": "test-project"
            # missing target_org
        }
        with pytest.raises(
            ValidationError, match="Required parameter 'target_org' not provided"
        ):
            scenario.validate_input(missing_required)

    def test_boolean_parameter_type_validation(self):
        """Test boolean parameter type validation."""
        scenario = self.create_test_scenario()

        # Valid boolean parameter
        valid_params = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": True,
        }
        scenario.validate_input(valid_params)

        # Invalid boolean parameter type
        invalid_params = {
            "project_name": "test-project",
            "target_org": "test-org",
            "create_component": "not_a_boolean",
        }
        with pytest.raises(
            ValidationError, match="Parameter 'create_component' must be a boolean"
        ):
            scenario.validate_input(invalid_params)


class TestRepositoryConfig:
    """Test RepositoryConfig with template strings."""

    def test_repository_config_with_boolean_template(self):
        """Test RepositoryConfig accepts boolean template strings."""
        repo_config = RepositoryConfig(
            source="test/repo",
            target_org="${target_org}",
            repo_name_template="${project_name}",
            create_component="${create_component}",
        )

        assert repo_config.create_component == "${create_component}"
        assert repo_config.source == "test/repo"

    def test_repository_config_with_boolean_value(self):
        """Test RepositoryConfig accepts boolean values."""
        repo_config = RepositoryConfig(
            source="test/repo",
            target_org="${target_org}",
            repo_name_template="${project_name}",
            create_component=True,
        )

        assert repo_config.create_component is True


class TestParameterPlaceholders:
    """Test parameter placeholder functionality."""

    def test_parameter_property_with_placeholder(self):
        """Test that ParameterProperty can have a placeholder."""
        param = ParameterProperty(
            type="string",
            description="Project name",
            placeholder="e.g., my-awesome-app",
        )
        assert param.placeholder == "e.g., my-awesome-app"
        assert param.description == "Project name"

    def test_scenario_with_placeholders_in_list(self):
        """Test that scenario listing includes placeholder information."""
        from mimic.scenarios import initialize_scenarios

        manager = initialize_scenarios("scenarios")
        scenarios = manager.list_scenarios()

        # Find param-demo scenario (has parameters)
        param_demo = next((s for s in scenarios if s["id"] == "param-demo"), None)
        assert param_demo is not None

        # Check that parameters include placeholders
        params = param_demo["parameters"]

        # project_name should have a placeholder
        project_name_param = params.get("project_name")
        assert project_name_param is not None
        assert project_name_param.get("placeholder") is not None
        assert project_name_param["placeholder"] == "my-project"
        assert project_name_param["description"] == "Project name"

        # target_org should have a placeholder
        target_org_param = params.get("target_org")
        assert target_org_param is not None
        assert target_org_param.get("placeholder") is not None
        assert target_org_param["placeholder"] == "cb-demos"

    def test_form_data_preprocessing(self):
        """Test that form data preprocessing handles checkbox values correctly."""
        from mimic.scenarios import initialize_scenarios

        manager = initialize_scenarios("scenarios")
        scenario = manager.get_scenario("param-demo")
        assert scenario is not None

        # Test checkbox form data - "on" should become True
        form_data_checked = {
            "project_name": "test-project",
            "target_org": "test-org",
            "environment": "dev",
            "enable_feature_x": "on",  # Form checkbox sends "on" when checked
        }
        processed = scenario.validate_input(form_data_checked)
        assert processed["enable_feature_x"] is True

        # Test checkbox form data - missing should become False
        form_data_unchecked = {
            "project_name": "test-project",
            "target_org": "test-org",
            "environment": "dev",
            # enable_feature_x is missing (unchecked checkbox)
        }
        processed = scenario.validate_input(form_data_unchecked)
        assert processed["enable_feature_x"] is False

        # Test that actual boolean values pass through unchanged
        api_data = {
            "project_name": "test-project",
            "target_org": "test-org",
            "environment": "dev",
            "enable_feature_x": True,
        }
        processed = scenario.validate_input(api_data)
        assert processed["enable_feature_x"] is True


class TestConditionalFileOperations:
    """Test conditional file operations functionality."""

    def test_conditional_file_operation_creation(self):
        """Test creating a ConditionalFileOperation."""
        from mimic.scenarios import ConditionalFileOperation

        operation = ConditionalFileOperation(
            condition_parameter="auto_setup_workflow",
            when_true={"workflow.yaml": ".cloudbees/workflows/workflow.yaml"},
            when_false={},
        )
        assert operation.condition_parameter == "auto_setup_workflow"
        assert operation.when_true == {
            "workflow.yaml": ".cloudbees/workflows/workflow.yaml"
        }
        assert operation.when_false == {}

    def test_param_demo_conditional_operations(self):
        """Test that param-demo scenario includes conditional file operations."""
        from mimic.scenarios import initialize_scenarios

        manager = initialize_scenarios("scenarios")
        scenario = manager.get_scenario("param-demo")
        assert scenario is not None

        # Should have one repository
        assert len(scenario.repositories) == 1
        repo = scenario.repositories[0]

        # Should have conditional file operations
        assert len(repo.conditional_file_operations) == 1
        operation = repo.conditional_file_operations[0]

        assert operation.condition_parameter == "enable_feature_x"
        assert operation.when_true == {
            "feature-x.yaml": ".cloudbees/workflows/feature-x.yaml"
        }
        assert operation.when_false == {"feature-x.yaml": "unused/feature-x.yaml"}

    def test_template_resolution_with_conditional_operations(self):
        """Test that template resolution works with conditional file operations."""
        from mimic.scenarios import initialize_scenarios

        manager = initialize_scenarios("scenarios")
        scenario = manager.get_scenario("param-demo")
        assert scenario is not None

        # Test with enable_feature_x = true
        params_auto = {
            "project_name": "test-project",
            "target_org": "test-org",
            "environment": "dev",
            "enable_feature_x": True,
        }

        resolved_auto = scenario.resolve_template_variables(params_auto)
        repo_auto = resolved_auto.repositories[0]
        operation_auto = repo_auto.conditional_file_operations[0]

        # Conditional operations should be preserved after resolution
        assert operation_auto.condition_parameter == "enable_feature_x"
        assert operation_auto.when_true == {
            "feature-x.yaml": ".cloudbees/workflows/feature-x.yaml"
        }

        # Test with enable_feature_x = false (default)
        params_manual = {
            "project_name": "test-project",
            "target_org": "test-org",
            "environment": "dev",
            "enable_feature_x": False,
        }

        resolved_manual = scenario.resolve_template_variables(params_manual)
        repo_manual = resolved_manual.repositories[0]
        operation_manual = repo_manual.conditional_file_operations[0]

        # Should still have the same structure
        assert operation_manual.condition_parameter == "enable_feature_x"
        assert operation_manual.when_false == {
            "feature-x.yaml": "unused/feature-x.yaml"
        }
