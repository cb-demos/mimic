"""Tests for first-class domain models."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from mimic.models import (
    CloudBeesApplication,
    CloudBeesComponent,
    CloudBeesEnvironment,
    CloudBeesFlag,
    EnvironmentVariable,
    GitHubRepository,
    Instance,
)


class TestEnvironmentVariable:
    """Test EnvironmentVariable model."""

    def test_create_basic_variable(self):
        """Test creating a basic environment variable."""
        var = EnvironmentVariable(name="API_URL", value="https://api.example.com")
        assert var.name == "API_URL"
        assert var.value == "https://api.example.com"
        assert var.is_secret is False

    def test_create_secret_variable(self):
        """Test creating a secret environment variable."""
        var = EnvironmentVariable(name="API_KEY", value="secret123", is_secret=True)
        assert var.name == "API_KEY"
        assert var.value == "secret123"
        assert var.is_secret is True

    def test_required_fields(self):
        """Test that name and value are required."""
        with pytest.raises(ValidationError) as exc_info:
            EnvironmentVariable()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "name" in error_fields
        assert "value" in error_fields

    def test_serialization(self):
        """Test model can be serialized to dict."""
        var = EnvironmentVariable(name="DB_HOST", value="localhost", is_secret=False)
        data = var.model_dump()

        assert data["name"] == "DB_HOST"
        assert data["value"] == "localhost"
        assert data["is_secret"] is False


class TestGitHubRepository:
    """Test GitHubRepository model."""

    def test_create_repository(self):
        """Test creating a repository."""
        now = datetime.now()
        repo = GitHubRepository(
            id="myorg/demo-app",
            name="demo-app",
            owner="myorg",
            url="https://github.com/myorg/demo-app",
            created_at=now,
        )

        assert repo.id == "myorg/demo-app"
        assert repo.name == "demo-app"
        assert repo.owner == "myorg"
        assert repo.url == "https://github.com/myorg/demo-app"
        assert repo.created_at == now

    def test_required_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            GitHubRepository()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "id" in error_fields
        assert "name" in error_fields
        assert "owner" in error_fields
        assert "url" in error_fields
        assert "created_at" in error_fields

    def test_serialization_deserialization(self):
        """Test round-trip serialization."""
        now = datetime.now()
        repo = GitHubRepository(
            id="owner/repo",
            name="repo",
            owner="owner",
            url="https://github.com/owner/repo",
            created_at=now,
        )

        data = repo.model_dump(mode="json")
        repo2 = GitHubRepository(**data)

        assert repo2.id == repo.id
        assert repo2.name == repo.name
        assert repo2.owner == repo.owner
        assert repo2.url == repo.url


class TestCloudBeesComponent:
    """Test CloudBeesComponent model."""

    def test_create_component_with_repository(self):
        """Test creating a component linked to a repository."""
        now = datetime.now()
        component = CloudBeesComponent(
            id="comp-uuid-123",
            name="api-service",
            org_id="org-uuid",
            repository_url="https://github.com/myorg/api-service",
            created_at=now,
        )

        assert component.id == "comp-uuid-123"
        assert component.name == "api-service"
        assert component.org_id == "org-uuid"
        assert component.repository_url == "https://github.com/myorg/api-service"
        assert component.created_at == now

    def test_create_component_without_repository(self):
        """Test creating a component without a repository link."""
        now = datetime.now()
        component = CloudBeesComponent(
            id="comp-uuid-456",
            name="standalone-service",
            org_id="org-uuid",
            created_at=now,
        )

        assert component.id == "comp-uuid-456"
        assert component.name == "standalone-service"
        assert component.repository_url is None

    def test_required_fields(self):
        """Test that id, name, org_id, and created_at are required."""
        with pytest.raises(ValidationError) as exc_info:
            CloudBeesComponent()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "id" in error_fields
        assert "name" in error_fields
        assert "org_id" in error_fields
        assert "created_at" in error_fields


class TestCloudBeesEnvironment:
    """Test CloudBeesEnvironment model."""

    def test_create_environment_with_variables_and_flags(self):
        """Test creating an environment with variables and flags."""
        now = datetime.now()
        env = CloudBeesEnvironment(
            id="env-uuid",
            name="production",
            org_id="org-uuid",
            variables=[
                EnvironmentVariable(name="API_URL", value="https://api.prod.com"),
                EnvironmentVariable(name="API_KEY", value="secret", is_secret=True),
            ],
            flag_ids=["flag-1", "flag-2", "flag-3"],
            created_at=now,
        )

        assert env.id == "env-uuid"
        assert env.name == "production"
        assert env.org_id == "org-uuid"
        assert len(env.variables) == 2
        assert env.variables[0].name == "API_URL"
        assert len(env.flag_ids) == 3
        assert "flag-2" in env.flag_ids

    def test_create_environment_with_defaults(self):
        """Test creating an environment with default empty lists."""
        now = datetime.now()
        env = CloudBeesEnvironment(
            id="env-uuid",
            name="development",
            org_id="org-uuid",
            created_at=now,
        )

        assert env.variables == []
        assert env.flag_ids == []

    def test_required_fields(self):
        """Test that id, name, org_id, and created_at are required."""
        with pytest.raises(ValidationError) as exc_info:
            CloudBeesEnvironment()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "id" in error_fields
        assert "name" in error_fields
        assert "org_id" in error_fields
        assert "created_at" in error_fields


class TestCloudBeesFlag:
    """Test CloudBeesFlag model."""

    def test_create_boolean_flag(self):
        """Test creating a boolean feature flag."""
        now = datetime.now()
        flag = CloudBeesFlag(
            id="flag-uuid",
            name="Dark Mode",
            org_id="org-uuid",
            type="boolean",
            key="dark_mode",
            created_at=now,
        )

        assert flag.id == "flag-uuid"
        assert flag.name == "Dark Mode"
        assert flag.org_id == "org-uuid"
        assert flag.type == "boolean"
        assert flag.key == "dark_mode"
        assert flag.created_at == now

    def test_create_string_flag(self):
        """Test creating a string feature flag."""
        now = datetime.now()
        flag = CloudBeesFlag(
            id="flag-uuid-2",
            name="Welcome Message",
            org_id="org-uuid",
            type="string",
            key="welcome_message",
            created_at=now,
        )

        assert flag.type == "string"
        assert flag.key == "welcome_message"

    def test_required_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            CloudBeesFlag()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "id" in error_fields
        assert "name" in error_fields
        assert "org_id" in error_fields
        assert "type" in error_fields
        assert "key" in error_fields
        assert "created_at" in error_fields


class TestCloudBeesApplication:
    """Test CloudBeesApplication model."""

    def test_create_application_with_components_and_environments(self):
        """Test creating an application with components and environments."""
        now = datetime.now()
        app = CloudBeesApplication(
            id="app-uuid",
            name="E-commerce Platform",
            org_id="org-uuid",
            repository_url="https://github.com/myorg/ecommerce",
            component_ids=["comp-1", "comp-2", "comp-3"],
            environment_ids=["env-1", "env-2"],
            created_at=now,
        )

        assert app.id == "app-uuid"
        assert app.name == "E-commerce Platform"
        assert app.org_id == "org-uuid"
        assert app.repository_url == "https://github.com/myorg/ecommerce"
        assert len(app.component_ids) == 3
        assert len(app.environment_ids) == 2
        assert "comp-2" in app.component_ids

    def test_create_application_with_defaults(self):
        """Test creating an application with default empty lists."""
        now = datetime.now()
        app = CloudBeesApplication(
            id="app-uuid",
            name="Simple App",
            org_id="org-uuid",
            created_at=now,
        )

        assert app.repository_url is None
        assert app.component_ids == []
        assert app.environment_ids == []

    def test_required_fields(self):
        """Test that id, name, org_id, and created_at are required."""
        with pytest.raises(ValidationError) as exc_info:
            CloudBeesApplication()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "id" in error_fields
        assert "name" in error_fields
        assert "org_id" in error_fields
        assert "created_at" in error_fields


class TestInstance:
    """Test Instance model."""

    def test_create_instance_minimal(self):
        """Test creating an instance with minimal required fields."""
        now = datetime.now()
        expires = now + timedelta(days=7)

        instance = Instance(
            id="abc-123",
            scenario_id="feature-flags-demo",
            name="acme-corp-demo",
            environment="prod",
            created_at=now,
            expires_at=expires,
        )

        assert instance.id == "abc-123"
        assert instance.scenario_id == "feature-flags-demo"
        assert instance.name == "acme-corp-demo"
        assert instance.environment == "prod"
        assert instance.created_at == now
        assert instance.expires_at == expires
        assert instance.repositories == []
        assert instance.components == []
        assert instance.environments == []
        assert instance.flags == []
        assert instance.applications == []
        assert instance.metadata == {}

    def test_create_instance_never_expires(self):
        """Test creating an instance that never expires."""
        now = datetime.now()
        instance = Instance(
            id="xyz-789",
            scenario_id="test-scenario",
            name="persistent-demo",
            environment="demo",
            created_at=now,
            expires_at=None,
        )

        assert instance.expires_at is None

    def test_create_instance_with_resources(self):
        """Test creating an instance with all resource types."""
        now = datetime.now()

        repo = GitHubRepository(
            id="myorg/demo",
            name="demo",
            owner="myorg",
            url="https://github.com/myorg/demo",
            created_at=now,
        )

        component = CloudBeesComponent(
            id="comp-1",
            name="api",
            org_id="org-1",
            repository_url=repo.url,
            created_at=now,
        )

        flag = CloudBeesFlag(
            id="flag-1",
            name="Feature A",
            org_id="org-1",
            type="boolean",
            key="feature_a",
            created_at=now,
        )

        env = CloudBeesEnvironment(
            id="env-1",
            name="prod",
            org_id="org-1",
            flag_ids=[flag.id],
            created_at=now,
        )

        app = CloudBeesApplication(
            id="app-1",
            name="My App",
            org_id="org-1",
            component_ids=[component.id],
            environment_ids=[env.id],
            created_at=now,
        )

        instance = Instance(
            id="inst-1",
            scenario_id="full-demo",
            name="complete-instance",
            environment="prod",
            created_at=now,
            expires_at=now + timedelta(days=30),
            repositories=[repo],
            components=[component],
            environments=[env],
            flags=[flag],
            applications=[app],
            metadata={"custom_key": "custom_value"},
        )

        assert len(instance.repositories) == 1
        assert len(instance.components) == 1
        assert len(instance.environments) == 1
        assert len(instance.flags) == 1
        assert len(instance.applications) == 1
        assert instance.metadata["custom_key"] == "custom_value"

    def test_get_component_by_name(self):
        """Test finding a component by name."""
        now = datetime.now()
        instance = Instance(
            id="inst-1",
            scenario_id="test",
            name="test",
            environment="prod",
            created_at=now,
            expires_at=None,
            components=[
                CloudBeesComponent(
                    id="comp-1",
                    name="api-service",
                    org_id="org-1",
                    created_at=now,
                ),
                CloudBeesComponent(
                    id="comp-2",
                    name="web-service",
                    org_id="org-1",
                    created_at=now,
                ),
            ],
        )

        component = instance.get_component_by_name("api-service")
        assert component is not None
        assert component.id == "comp-1"
        assert component.name == "api-service"

        missing = instance.get_component_by_name("nonexistent")
        assert missing is None

    def test_get_repository_by_id(self):
        """Test finding a repository by ID."""
        now = datetime.now()
        instance = Instance(
            id="inst-1",
            scenario_id="test",
            name="test",
            environment="prod",
            created_at=now,
            expires_at=None,
            repositories=[
                GitHubRepository(
                    id="org1/repo1",
                    name="repo1",
                    owner="org1",
                    url="https://github.com/org1/repo1",
                    created_at=now,
                ),
                GitHubRepository(
                    id="org2/repo2",
                    name="repo2",
                    owner="org2",
                    url="https://github.com/org2/repo2",
                    created_at=now,
                ),
            ],
        )

        repo = instance.get_repository_by_id("org2/repo2")
        assert repo is not None
        assert repo.name == "repo2"
        assert repo.owner == "org2"

        missing = instance.get_repository_by_id("org3/repo3")
        assert missing is None

    def test_get_application_components(self):
        """Test getting all components for an application."""
        now = datetime.now()

        components = [
            CloudBeesComponent(
                id="comp-1",
                name="frontend",
                org_id="org-1",
                created_at=now,
            ),
            CloudBeesComponent(
                id="comp-2",
                name="backend",
                org_id="org-1",
                created_at=now,
            ),
            CloudBeesComponent(
                id="comp-3",
                name="database",
                org_id="org-1",
                created_at=now,
            ),
        ]

        app = CloudBeesApplication(
            id="app-1",
            name="My App",
            org_id="org-1",
            component_ids=["comp-1", "comp-3"],  # Only frontend and database
            created_at=now,
        )

        instance = Instance(
            id="inst-1",
            scenario_id="test",
            name="test",
            environment="prod",
            created_at=now,
            expires_at=None,
            components=components,
            applications=[app],
        )

        app_components = instance.get_application_components("app-1")
        assert len(app_components) == 2
        assert {c.name for c in app_components} == {"frontend", "database"}

        # Test with non-existent app
        missing_app_components = instance.get_application_components("app-999")
        assert missing_app_components == []

    def test_get_environments_with_flag(self):
        """Test getting all environments that have a specific flag."""
        now = datetime.now()

        environments = [
            CloudBeesEnvironment(
                id="env-1",
                name="dev",
                org_id="org-1",
                flag_ids=["flag-1", "flag-2"],
                created_at=now,
            ),
            CloudBeesEnvironment(
                id="env-2",
                name="staging",
                org_id="org-1",
                flag_ids=["flag-2", "flag-3"],
                created_at=now,
            ),
            CloudBeesEnvironment(
                id="env-3",
                name="prod",
                org_id="org-1",
                flag_ids=["flag-3"],
                created_at=now,
            ),
        ]

        instance = Instance(
            id="inst-1",
            scenario_id="test",
            name="test",
            environment="prod",
            created_at=now,
            expires_at=None,
            environments=environments,
        )

        envs_with_flag2 = instance.get_environments_with_flag("flag-2")
        assert len(envs_with_flag2) == 2
        assert {e.name for e in envs_with_flag2} == {"dev", "staging"}

        envs_with_flag1 = instance.get_environments_with_flag("flag-1")
        assert len(envs_with_flag1) == 1
        assert envs_with_flag1[0].name == "dev"

        # Test with non-existent flag
        envs_with_missing = instance.get_environments_with_flag("flag-999")
        assert envs_with_missing == []

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            Instance()

        errors = exc_info.value.errors()
        error_fields = {e["loc"][0] for e in errors}
        assert "id" in error_fields
        assert "scenario_id" in error_fields
        assert "name" in error_fields
        assert "environment" in error_fields
        assert "created_at" in error_fields

    def test_serialization_deserialization(self):
        """Test complete round-trip serialization with nested resources."""
        now = datetime.now()
        expires = now + timedelta(days=7)

        original = Instance(
            id="inst-1",
            scenario_id="test-scenario",
            name="test-instance",
            environment="prod",
            created_at=now,
            expires_at=expires,
            repositories=[
                GitHubRepository(
                    id="org/repo",
                    name="repo",
                    owner="org",
                    url="https://github.com/org/repo",
                    created_at=now,
                )
            ],
            components=[
                CloudBeesComponent(
                    id="comp-1",
                    name="service",
                    org_id="org-1",
                    created_at=now,
                )
            ],
            metadata={"key": "value"},
        )

        # Serialize to dict
        data = original.model_dump(mode="json")

        # Deserialize back
        restored = Instance(**data)

        assert restored.id == original.id
        assert restored.scenario_id == original.scenario_id
        assert restored.name == original.name
        assert len(restored.repositories) == 1
        assert restored.repositories[0].id == "org/repo"
        assert len(restored.components) == 1
        assert restored.components[0].name == "service"
        assert restored.metadata["key"] == "value"
