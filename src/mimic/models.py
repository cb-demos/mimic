"""First-class domain models for Mimic.

This module defines structured, typed resource models that replace the generic
Resource model. Each resource type is a first-class domain object with proper
typing, validation, and relationship tracking.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EnvironmentVariable(BaseModel):
    """Environment variable configuration.

    Used in CloudBees environments to store configuration values and secrets.

    Examples:
        >>> var = EnvironmentVariable(name="API_KEY", value="secret123", is_secret=True)
        >>> var.name
        'API_KEY'
    """

    name: str
    value: str
    is_secret: bool = False


class GitHubRepository(BaseModel):
    """A GitHub repository created for this instance.

    Represents a GitHub repository that was created from a template during
    scenario execution. Tracks ownership, URL, and creation time.

    Examples:
        >>> repo = GitHubRepository(
        ...     id="myorg/demo-app",
        ...     name="demo-app",
        ...     owner="myorg",
        ...     url="https://github.com/myorg/demo-app",
        ...     created_at=datetime.now()
        ... )
        >>> repo.id
        'myorg/demo-app'
    """

    id: str  # Format: "owner/repo"
    name: str  # Just the repo name
    owner: str  # GitHub org/user
    url: str  # Full HTTPS URL
    created_at: datetime

    # Future extensions (commented for now):
    # secrets: list[str] = Field(default_factory=list)  # Secret names that were added
    # collaborators: list[str] = Field(default_factory=list)  # Invited users
    # default_branch: str = "main"

    def get_url(self) -> str:
        """Get the URL to view this repository in GitHub.

        Returns:
            Full HTTPS URL to the GitHub repository
        """
        return self.url


class CloudBeesComponent(BaseModel):
    """A CloudBees component.

    Represents a component in CloudBees Unify that may be linked to a GitHub
    repository. Components are the building blocks of applications.

    Examples:
        >>> component = CloudBeesComponent(
        ...     id="uuid-1234",
        ...     name="api-service",
        ...     org_id="org-uuid",
        ...     repository_url="https://github.com/myorg/api-service",
        ...     created_at=datetime.now()
        ... )
        >>> component.name
        'api-service'
    """

    id: str  # UUID
    name: str
    org_id: str
    repository_url: str | None = None  # Link to GitHub repo
    created_at: datetime

    def get_url(self, base_url: str, org_slug: str) -> str:
        """Get the URL to view this component in CloudBees UI.

        Args:
            base_url: Base URL like "https://cloudbees.io" or "https://ui.demo1.cloudbees.io"
            org_slug: Organization slug in URL (e.g., "cloudbees", "demo", "unify-golden-demos")

        Returns:
            Full URL to the component page
        """
        # Remove any trailing slashes
        base = base_url.rstrip("/")
        return f"{base}/{org_slug}/{self.org_id}/components/{self.id}"


class CloudBeesEnvironment(BaseModel):
    """A CloudBees environment.

    Represents a deployment environment in CloudBees Unify with associated
    environment variables, secrets, and feature flags.

    Examples:
        >>> env = CloudBeesEnvironment(
        ...     id="env-uuid",
        ...     name="production",
        ...     org_id="org-uuid",
        ...     variables=[EnvironmentVariable(name="API_URL", value="https://api.example.com")],
        ...     flag_ids=["flag-1", "flag-2"],
        ...     created_at=datetime.now()
        ... )
        >>> len(env.variables)
        1
    """

    id: str  # UUID
    name: str
    org_id: str
    variables: list[EnvironmentVariable] = Field(
        default_factory=list
    )  # Env vars/secrets
    flag_ids: list[str] = Field(default_factory=list)  # Associated feature flags
    created_at: datetime

    def get_url(self, base_url: str, org_slug: str) -> str:
        """Get the URL to view this environment in CloudBees UI.

        Args:
            base_url: Base URL like "https://cloudbees.io" or "https://ui.demo1.cloudbees.io"
            org_slug: Organization slug in URL (e.g., "cloudbees", "demo", "unify-golden-demos")

        Returns:
            Full URL to the environments list page filtered by this environment's name
        """
        base = base_url.rstrip("/")
        # Environments don't have dedicated pages, use list view with search query
        return (
            f"{base}/{org_slug}/{self.org_id}/configurations/environments?q={self.name}"
        )


class CloudBeesFlag(BaseModel):
    """A CloudBees feature flag.

    Represents a feature flag in CloudBees Feature Management that can be
    associated with environments and used to control feature rollout.

    Examples:
        >>> flag = CloudBeesFlag(
        ...     id="flag-uuid",
        ...     name="Dark Mode",
        ...     org_id="org-uuid",
        ...     type="boolean",
        ...     key="dark_mode",
        ...     created_at=datetime.now()
        ... )
        >>> flag.key
        'dark_mode'
    """

    id: str  # UUID
    name: str
    org_id: str
    type: str  # "boolean", "string", "number"
    key: str  # The flag key used in code
    created_at: datetime

    # Future extensions (commented for now):
    # default_value: Any

    def get_url(self, base_url: str, org_slug: str) -> str:
        """Get the URL to view this feature flag in CloudBees UI.

        Args:
            base_url: Base URL like "https://cloudbees.io" or "https://ui.demo1.cloudbees.io"
            org_slug: Organization slug in URL (e.g., "cloudbees", "demo", "unify-golden-demos")

        Returns:
            Full URL to the flag page
        """
        base = base_url.rstrip("/")
        return f"{base}/{org_slug}/{self.org_id}/feature-management/flags/{self.id}"


class CloudBeesApplication(BaseModel):
    """A CloudBees application.

    Represents an application in CloudBees Unify that groups together components
    and environments. Applications provide the top-level organizational structure
    for deployment pipelines.

    Examples:
        >>> app = CloudBeesApplication(
        ...     id="app-uuid",
        ...     name="E-commerce Platform",
        ...     org_id="org-uuid",
        ...     repository_url="https://github.com/myorg/ecommerce",
        ...     component_ids=["comp-1", "comp-2"],
        ...     environment_ids=["env-1", "env-2"],
        ...     created_at=datetime.now()
        ... )
        >>> len(app.component_ids)
        2
    """

    id: str  # UUID
    name: str
    org_id: str
    repository_url: str | None = None
    component_ids: list[str] = Field(default_factory=list)  # References to components
    environment_ids: list[str] = Field(
        default_factory=list
    )  # References to environments
    is_shared: bool = False  # If True, reuse existing app; don't delete on cleanup
    created_at: datetime

    def get_url(self, base_url: str, org_slug: str) -> str:
        """Get the URL to view this application in CloudBees UI.

        Args:
            base_url: Base URL like "https://cloudbees.io" or "https://ui.demo1.cloudbees.io"
            org_slug: Organization slug in URL (e.g., "cloudbees", "demo", "unify-golden-demos")

        Returns:
            Full URL to the application page
        """
        base = base_url.rstrip("/")
        return f"{base}/{org_slug}/{self.org_id}/applications/{self.id}"


class Instance(BaseModel):
    """An instantiation of a scenario.

    Represents a complete demo, workshop, or proof-of-concept environment created
    from a scenario. An instance contains all resources created during execution,
    organized by type with preserved relationships.

    This is the atomic unit that users think in when using Mimic:
    - "I'm running the feature-flags instance for the Acme Corp demo"
    - "I need to spin up an instance for Friday's workshop"

    Examples:
        >>> instance = Instance(
        ...     id="abc-123",
        ...     scenario_id="feature-flags-demo",
        ...     name="acme-corp-demo",
        ...     environment="prod",
        ...     created_at=datetime.now(),
        ...     expires_at=datetime.now() + timedelta(days=7)
        ... )
        >>> instance.name
        'acme-corp-demo'

        >>> # Add resources
        >>> instance.repositories.append(GitHubRepository(...))
        >>> instance.components.append(CloudBeesComponent(...))

        >>> # Query relationships
        >>> component = instance.get_component_by_name("api-service")
        >>> app_components = instance.get_application_components("app-uuid")
    """

    id: str  # Unique identifier (formerly session_id)
    scenario_id: str  # Which scenario was used
    name: str  # Human-readable name (from name_template)
    environment: str  # Which CloudBees environment (prod/preprod/demo/custom)
    created_at: datetime
    expires_at: datetime | None  # None = never expires

    # Structured resources (not flat list!)
    repositories: list[GitHubRepository] = Field(default_factory=list)
    components: list[CloudBeesComponent] = Field(default_factory=list)
    environments: list[CloudBeesEnvironment] = Field(default_factory=list)
    flags: list[CloudBeesFlag] = Field(default_factory=list)
    applications: list[CloudBeesApplication] = Field(default_factory=list)

    # Escape hatch for scenario-specific metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_component_by_name(self, name: str) -> CloudBeesComponent | None:
        """Find a component by its name.

        Args:
            name: The component name to search for

        Returns:
            The CloudBeesComponent if found, None otherwise

        Examples:
            >>> component = instance.get_component_by_name("api-service")
            >>> if component:
            ...     print(f"Found component: {component.id}")
        """
        return next((c for c in self.components if c.name == name), None)

    def get_repository_by_id(self, repo_id: str) -> GitHubRepository | None:
        """Find a repository by its ID (owner/repo format).

        Args:
            repo_id: The repository ID in "owner/repo" format

        Returns:
            The GitHubRepository if found, None otherwise

        Examples:
            >>> repo = instance.get_repository_by_id("myorg/demo-app")
            >>> if repo:
            ...     print(f"Repository URL: {repo.url}")
        """
        return next((r for r in self.repositories if r.id == repo_id), None)

    def get_application_components(self, app_id: str) -> list[CloudBeesComponent]:
        """Get all components associated with an application.

        Args:
            app_id: The application ID

        Returns:
            List of CloudBeesComponent objects linked to this application

        Examples:
            >>> components = instance.get_application_components("app-uuid")
            >>> for comp in components:
            ...     print(f"Component: {comp.name}")
        """
        app = next((a for a in self.applications if a.id == app_id), None)
        if not app:
            return []
        return [c for c in self.components if c.id in app.component_ids]

    def get_environments_with_flag(self, flag_id: str) -> list[CloudBeesEnvironment]:
        """Get all environments that have a specific flag associated.

        Args:
            flag_id: The flag ID to search for

        Returns:
            List of CloudBeesEnvironment objects that include this flag

        Examples:
            >>> envs = instance.get_environments_with_flag("flag-uuid")
            >>> for env in envs:
            ...     print(f"Environment: {env.name}")
        """
        return [e for e in self.environments if flag_id in e.flag_ids]
