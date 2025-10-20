"""Tests for InstanceRepository - persistence and retrieval of Instance objects."""

from datetime import datetime, timedelta

import pytest

from mimic.instance_repository import InstanceRepository
from mimic.models import (
    CloudBeesApplication,
    CloudBeesComponent,
    CloudBeesEnvironment,
    CloudBeesFlag,
    EnvironmentVariable,
    GitHubRepository,
    Instance,
)


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file for testing."""
    state_file = tmp_path / "state.json"
    return state_file


@pytest.fixture
def repo(temp_state_file):
    """Create an InstanceRepository instance with temporary state file."""
    return InstanceRepository(state_file=temp_state_file)


@pytest.fixture
def sample_instance():
    """Create a sample instance for testing."""
    now = datetime.now()
    return Instance(
        id="test-123",
        scenario_id="test-scenario",
        name="test-instance",
        environment="prod",
        created_at=now,
        expires_at=now + timedelta(days=7),
    )


@pytest.fixture
def complex_instance():
    """Create a complex instance with all resource types."""
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
        variables=[
            EnvironmentVariable(name="API_URL", value="https://api.example.com"),
            EnvironmentVariable(name="API_KEY", value="secret", is_secret=True),
        ],
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

    return Instance(
        id="complex-123",
        scenario_id="full-demo",
        name="complex-instance",
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


class TestRepositoryInitialization:
    """Test InstanceRepository initialization."""

    def test_creates_state_file_on_init(self, temp_state_file):
        """Test that state file is created on initialization."""
        assert not temp_state_file.exists()

        _ = InstanceRepository(state_file=temp_state_file)

        assert temp_state_file.exists()

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        state_file = tmp_path / "nested" / "dir" / "state.json"
        assert not state_file.parent.exists()

        _ = InstanceRepository(state_file=state_file)

        assert state_file.parent.exists()
        assert state_file.exists()

    def test_loads_existing_state_file(self, repo, sample_instance, temp_state_file):
        """Test that existing state file is loaded correctly."""
        # Save an instance
        repo.save(sample_instance)

        # Create new repo pointing to same file
        repo2 = InstanceRepository(state_file=temp_state_file)
        loaded = repo2.get_by_id("test-123")

        assert loaded is not None
        assert loaded.id == "test-123"


class TestSaveAndLoad:
    """Test save and load operations."""

    def test_save_instance(self, repo, sample_instance):
        """Test saving an instance."""
        repo.save(sample_instance)

        loaded = repo.get_by_id("test-123")
        assert loaded is not None
        assert loaded.id == sample_instance.id
        assert loaded.name == sample_instance.name
        assert loaded.scenario_id == sample_instance.scenario_id

    def test_save_instance_persists_to_file(self, repo, sample_instance):
        """Test that saved instance persists to file."""
        repo.save(sample_instance)

        # Create new repo instance
        repo2 = InstanceRepository(state_file=repo.state_file)
        loaded = repo2.get_by_id("test-123")

        assert loaded is not None
        assert loaded.id == "test-123"

    def test_save_updates_existing_instance(self, repo, sample_instance):
        """Test that saving an instance with same ID updates it."""
        repo.save(sample_instance)

        # Modify and save again
        sample_instance.name = "updated-name"
        repo.save(sample_instance)

        loaded = repo.get_by_id("test-123")
        assert loaded is not None
        assert loaded.name == "updated-name"

    def test_save_complex_instance_with_all_resources(self, repo, complex_instance):
        """Test saving instance with all resource types."""
        repo.save(complex_instance)

        loaded = repo.get_by_id("complex-123")
        assert loaded is not None
        assert len(loaded.repositories) == 1
        assert len(loaded.components) == 1
        assert len(loaded.environments) == 1
        assert len(loaded.flags) == 1
        assert len(loaded.applications) == 1
        assert loaded.repositories[0].id == "myorg/demo"
        assert loaded.components[0].name == "api"
        assert loaded.environments[0].variables[0].name == "API_URL"
        assert loaded.flags[0].key == "feature_a"
        assert loaded.applications[0].component_ids == ["comp-1"]
        assert loaded.metadata["custom_key"] == "custom_value"


class TestGetById:
    """Test get_by_id method."""

    def test_get_by_id_returns_instance(self, repo, sample_instance):
        """Test getting instance by ID."""
        repo.save(sample_instance)

        loaded = repo.get_by_id("test-123")
        assert loaded is not None
        assert loaded.id == "test-123"

    def test_get_by_id_returns_none_for_nonexistent(self, repo):
        """Test that get_by_id returns None for non-existent instance."""
        loaded = repo.get_by_id("nonexistent")
        assert loaded is None

    def test_get_by_id_hydrates_all_resources(self, repo, complex_instance):
        """Test that get_by_id fully hydrates all nested resources."""
        repo.save(complex_instance)

        loaded = repo.get_by_id("complex-123")
        assert loaded is not None

        # Verify all resources are hydrated as proper model instances
        assert isinstance(loaded.repositories[0], GitHubRepository)
        assert isinstance(loaded.components[0], CloudBeesComponent)
        assert isinstance(loaded.environments[0], CloudBeesEnvironment)
        assert isinstance(loaded.flags[0], CloudBeesFlag)
        assert isinstance(loaded.applications[0], CloudBeesApplication)
        assert isinstance(loaded.environments[0].variables[0], EnvironmentVariable)


class TestGetByName:
    """Test get_by_name method."""

    def test_get_by_name_returns_instance(self, repo, sample_instance):
        """Test getting instance by name."""
        repo.save(sample_instance)

        loaded = repo.get_by_name("test-instance")
        assert loaded is not None
        assert loaded.id == "test-123"
        assert loaded.name == "test-instance"

    def test_get_by_name_returns_none_for_nonexistent(self, repo):
        """Test that get_by_name returns None for non-existent name."""
        loaded = repo.get_by_name("nonexistent")
        assert loaded is None

    def test_get_by_name_finds_correct_instance_with_multiple(self, repo):
        """Test that get_by_name finds correct instance when multiple exist."""
        now = datetime.now()
        instance1 = Instance(
            id="inst-1",
            scenario_id="test",
            name="first-instance",
            environment="prod",
            created_at=now,
            expires_at=None,
        )
        instance2 = Instance(
            id="inst-2",
            scenario_id="test",
            name="second-instance",
            environment="prod",
            created_at=now,
            expires_at=None,
        )

        repo.save(instance1)
        repo.save(instance2)

        loaded = repo.get_by_name("second-instance")
        assert loaded is not None
        assert loaded.id == "inst-2"


class TestFindAll:
    """Test find_all method."""

    def test_find_all_returns_empty_list_when_no_instances(self, repo):
        """Test that find_all returns empty list when no instances exist."""
        instances = repo.find_all()
        assert instances == []

    def test_find_all_returns_all_instances(self, repo):
        """Test that find_all returns all saved instances."""
        now = datetime.now()
        for i in range(3):
            instance = Instance(
                id=f"inst-{i}",
                scenario_id="test",
                name=f"instance-{i}",
                environment="prod",
                created_at=now + timedelta(seconds=i),
                expires_at=None,
            )
            repo.save(instance)

        instances = repo.find_all()
        assert len(instances) == 3

    def test_find_all_sorts_by_creation_date_newest_first(self, repo):
        """Test that find_all sorts instances by creation date (newest first)."""
        now = datetime.now()

        # Create instances with different creation times
        old_instance = Instance(
            id="old",
            scenario_id="test",
            name="old",
            environment="prod",
            created_at=now - timedelta(days=2),
            expires_at=None,
        )
        new_instance = Instance(
            id="new",
            scenario_id="test",
            name="new",
            environment="prod",
            created_at=now,
            expires_at=None,
        )
        middle_instance = Instance(
            id="middle",
            scenario_id="test",
            name="middle",
            environment="prod",
            created_at=now - timedelta(days=1),
            expires_at=None,
        )

        repo.save(old_instance)
        repo.save(new_instance)
        repo.save(middle_instance)

        instances = repo.find_all()
        assert len(instances) == 3
        assert instances[0].id == "new"
        assert instances[1].id == "middle"
        assert instances[2].id == "old"

    def test_find_all_includes_expired_by_default(self, repo):
        """Test that find_all includes expired instances by default."""
        now = datetime.now()

        active = Instance(
            id="active",
            scenario_id="test",
            name="active",
            environment="prod",
            created_at=now,
            expires_at=now + timedelta(days=7),
        )
        expired = Instance(
            id="expired",
            scenario_id="test",
            name="expired",
            environment="prod",
            created_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=3),
        )

        repo.save(active)
        repo.save(expired)

        instances = repo.find_all(include_expired=True)
        assert len(instances) == 2

    def test_find_all_can_exclude_expired(self, repo):
        """Test that find_all can exclude expired instances."""
        now = datetime.now()

        active = Instance(
            id="active",
            scenario_id="test",
            name="active",
            environment="prod",
            created_at=now,
            expires_at=now + timedelta(days=7),
        )
        expired = Instance(
            id="expired",
            scenario_id="test",
            name="expired",
            environment="prod",
            created_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=3),
        )

        repo.save(active)
        repo.save(expired)

        instances = repo.find_all(include_expired=False)
        assert len(instances) == 1
        assert instances[0].id == "active"

    def test_find_all_includes_never_expiring_instances(self, repo):
        """Test that instances with expires_at=None are included regardless."""
        now = datetime.now()

        never_expires = Instance(
            id="never",
            scenario_id="test",
            name="never",
            environment="prod",
            created_at=now,
            expires_at=None,
        )

        repo.save(never_expires)

        instances = repo.find_all(include_expired=False)
        assert len(instances) == 1
        assert instances[0].id == "never"


class TestFindByScenario:
    """Test find_by_scenario method."""

    def test_find_by_scenario_filters_correctly(self, repo):
        """Test that find_by_scenario filters by scenario ID."""
        now = datetime.now()

        for i in range(2):
            instance = Instance(
                id=f"scenario-a-{i}",
                scenario_id="scenario-a",
                name=f"instance-{i}",
                environment="prod",
                created_at=now,
                expires_at=None,
            )
            repo.save(instance)

        for i in range(3):
            instance = Instance(
                id=f"scenario-b-{i}",
                scenario_id="scenario-b",
                name=f"instance-{i}",
                environment="prod",
                created_at=now,
                expires_at=None,
            )
            repo.save(instance)

        scenario_a_instances = repo.find_by_scenario("scenario-a")
        assert len(scenario_a_instances) == 2
        assert all(i.scenario_id == "scenario-a" for i in scenario_a_instances)

        scenario_b_instances = repo.find_by_scenario("scenario-b")
        assert len(scenario_b_instances) == 3
        assert all(i.scenario_id == "scenario-b" for i in scenario_b_instances)

    def test_find_by_scenario_returns_empty_for_nonexistent(self, repo):
        """Test that find_by_scenario returns empty list for non-existent scenario."""
        instances = repo.find_by_scenario("nonexistent")
        assert instances == []


class TestFindByEnvironment:
    """Test find_by_environment method."""

    def test_find_by_environment_filters_correctly(self, repo):
        """Test that find_by_environment filters by environment."""
        now = datetime.now()

        for i in range(2):
            instance = Instance(
                id=f"prod-{i}",
                scenario_id="test",
                name=f"prod-instance-{i}",
                environment="prod",
                created_at=now,
                expires_at=None,
            )
            repo.save(instance)

        for i in range(3):
            instance = Instance(
                id=f"demo-{i}",
                scenario_id="test",
                name=f"demo-instance-{i}",
                environment="demo",
                created_at=now,
                expires_at=None,
            )
            repo.save(instance)

        prod_instances = repo.find_by_environment("prod")
        assert len(prod_instances) == 2
        assert all(i.environment == "prod" for i in prod_instances)

        demo_instances = repo.find_by_environment("demo")
        assert len(demo_instances) == 3
        assert all(i.environment == "demo" for i in demo_instances)

    def test_find_by_environment_returns_empty_for_nonexistent(self, repo):
        """Test that find_by_environment returns empty list for non-existent environment."""
        instances = repo.find_by_environment("nonexistent")
        assert instances == []


class TestFindExpired:
    """Test find_expired method."""

    def test_find_expired_returns_only_expired_instances(self, repo):
        """Test that find_expired returns only expired instances."""
        now = datetime.now()

        active = Instance(
            id="active",
            scenario_id="test",
            name="active",
            environment="prod",
            created_at=now,
            expires_at=now + timedelta(days=7),
        )
        expired1 = Instance(
            id="expired-1",
            scenario_id="test",
            name="expired-1",
            environment="prod",
            created_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=3),
        )
        expired2 = Instance(
            id="expired-2",
            scenario_id="test",
            name="expired-2",
            environment="prod",
            created_at=now - timedelta(days=20),
            expires_at=now - timedelta(days=1),
        )

        repo.save(active)
        repo.save(expired1)
        repo.save(expired2)

        expired_instances = repo.find_expired()
        assert len(expired_instances) == 2
        assert all(i.id.startswith("expired") for i in expired_instances)

    def test_find_expired_excludes_never_expiring(self, repo):
        """Test that find_expired excludes instances with expires_at=None."""
        now = datetime.now()

        never_expires = Instance(
            id="never",
            scenario_id="test",
            name="never",
            environment="prod",
            created_at=now,
            expires_at=None,
        )
        expired = Instance(
            id="expired",
            scenario_id="test",
            name="expired",
            environment="prod",
            created_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=3),
        )

        repo.save(never_expires)
        repo.save(expired)

        expired_instances = repo.find_expired()
        assert len(expired_instances) == 1
        assert expired_instances[0].id == "expired"

    def test_find_expired_returns_empty_when_none_expired(self, repo):
        """Test that find_expired returns empty list when no instances are expired."""
        now = datetime.now()

        active = Instance(
            id="active",
            scenario_id="test",
            name="active",
            environment="prod",
            created_at=now,
            expires_at=now + timedelta(days=7),
        )

        repo.save(active)

        expired_instances = repo.find_expired()
        assert expired_instances == []


class TestDelete:
    """Test delete method."""

    def test_delete_removes_instance(self, repo, sample_instance):
        """Test that delete removes an instance."""
        repo.save(sample_instance)
        assert repo.exists("test-123")

        repo.delete("test-123")

        assert not repo.exists("test-123")
        assert repo.get_by_id("test-123") is None

    def test_delete_persists_to_file(self, repo, sample_instance):
        """Test that delete persists to file."""
        repo.save(sample_instance)
        repo.delete("test-123")

        # Create new repo instance
        repo2 = InstanceRepository(state_file=repo.state_file)
        assert not repo2.exists("test-123")

    def test_delete_raises_error_for_nonexistent(self, repo):
        """Test that delete raises error for non-existent instance."""
        with pytest.raises(ValueError) as exc_info:
            repo.delete("nonexistent")

        assert "Instance nonexistent not found" in str(exc_info.value)


class TestExists:
    """Test exists method."""

    def test_exists_returns_true_for_existing_instance(self, repo, sample_instance):
        """Test that exists returns True for existing instance."""
        repo.save(sample_instance)
        assert repo.exists("test-123")

    def test_exists_returns_false_for_nonexistent_instance(self, repo):
        """Test that exists returns False for non-existent instance."""
        assert not repo.exists("nonexistent")

    def test_exists_returns_false_after_deletion(self, repo, sample_instance):
        """Test that exists returns False after deletion."""
        repo.save(sample_instance)
        assert repo.exists("test-123")

        repo.delete("test-123")
        assert not repo.exists("test-123")
