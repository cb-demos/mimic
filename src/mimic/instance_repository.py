"""Repository for Instance persistence and retrieval.

This module implements the Repository pattern for managing Instance objects,
providing a clean abstraction over persistence details.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Instance
from .paths import get_config_dir


class InstanceRepository:
    """Repository for Instance persistence and retrieval.

    Handles serialization, deserialization, and querying of Instance objects
    to/from JSON storage.

    Examples:
        >>> repo = InstanceRepository()
        >>> instance = Instance(...)
        >>> repo.save(instance)
        >>> loaded = repo.get_by_id(instance.id)
        >>> all_instances = repo.find_all()
    """

    def __init__(self, state_file: Path | str | None = None):
        """
        Initialize the instance repository.

        Args:
            state_file: Path to state JSON file. Defaults to $MIMIC_CONFIG_DIR/state.json or ~/.mimic/state.json
        """
        if state_file is None:
            state_file = get_config_dir() / "state.json"
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize state if file doesn't exist
        if not self.state_file.exists():
            self._save_state({"instances": {}})

    def _load_state(self) -> dict[str, Any]:
        """Load state from JSON file with auto-migration.

        Returns:
            Dictionary containing instances data
        """
        if not self.state_file.exists():
            return {"instances": {}}

        with open(self.state_file) as f:
            state = json.load(f)

        # MIGRATE: environment → tenant in all instances
        needs_save = False
        for _instance_id, instance_data in state.get("instances", {}).items():
            if "environment" in instance_data and "tenant" not in instance_data:
                instance_data["tenant"] = instance_data.pop("environment")
                needs_save = True

        if needs_save:
            self._save_state(state)

        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save state to JSON file.

        Args:
            state: Dictionary containing instances data
        """
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def save(self, instance: Instance) -> None:
        """Persist an instance with all its resources.

        Args:
            instance: The Instance object to save

        Examples:
            >>> repo = InstanceRepository()
            >>> instance = Instance(id="abc-123", ...)
            >>> repo.save(instance)
        """
        state = self._load_state()
        state["instances"][instance.id] = instance.model_dump(mode="json")
        self._save_state(state)

    def get_by_id(self, instance_id: str) -> Instance | None:
        """Load and hydrate an instance by ID.

        Args:
            instance_id: The unique identifier of the instance

        Returns:
            Fully hydrated Instance object if found, None otherwise

        Examples:
            >>> repo = InstanceRepository()
            >>> instance = repo.get_by_id("abc-123")
            >>> if instance:
            ...     print(f"Found: {instance.name}")
        """
        state = self._load_state()
        instance_data = state["instances"].get(instance_id)

        if not instance_data:
            return None

        return Instance(**instance_data)

    def get_by_name(self, name: str) -> Instance | None:
        """Load and hydrate an instance by its human-readable name.

        Args:
            name: The human-readable name of the instance

        Returns:
            Fully hydrated Instance object if found, None otherwise

        Examples:
            >>> repo = InstanceRepository()
            >>> instance = repo.get_by_name("acme-corp-demo")
            >>> if instance:
            ...     print(f"Found instance: {instance.id}")
        """
        state = self._load_state()

        for instance_data in state["instances"].values():
            if instance_data.get("name") == name:
                return Instance(**instance_data)

        return None

    def find_all(self, include_expired: bool = True) -> list[Instance]:
        """Load all instances.

        Args:
            include_expired: Whether to include expired instances (default: True)

        Returns:
            List of Instance objects, sorted by creation date (newest first)

        Examples:
            >>> repo = InstanceRepository()
            >>> all_instances = repo.find_all()
            >>> active_only = repo.find_all(include_expired=False)
        """
        state = self._load_state()
        instances = []
        now = datetime.now()

        for instance_data in state["instances"].values():
            instance = Instance(**instance_data)

            # Include instance if:
            # - include_expired is True, OR
            # - instance never expires (expires_at is None), OR
            # - instance hasn't expired yet
            if (
                include_expired
                or instance.expires_at is None
                or instance.expires_at > now
            ):
                instances.append(instance)

        # Sort by creation date, newest first
        instances.sort(key=lambda i: i.created_at, reverse=True)
        return instances

    def find_by_scenario(self, scenario_id: str) -> list[Instance]:
        """Find instances by scenario ID.

        Args:
            scenario_id: The scenario ID to filter by

        Returns:
            List of Instance objects for this scenario, sorted by creation date (newest first)

        Examples:
            >>> repo = InstanceRepository()
            >>> instances = repo.find_by_scenario("feature-flags-demo")
            >>> print(f"Found {len(instances)} instances")
        """
        all_instances = self.find_all(include_expired=True)
        return [i for i in all_instances if i.scenario_id == scenario_id]

    def find_by_tenant(self, tenant: str) -> list[Instance]:
        """Find instances by CloudBees tenant.

        Args:
            tenant: The tenant name to filter by (e.g., "prod", "demo")

        Returns:
            List of Instance objects for this tenant, sorted by creation date (newest first)

        Examples:
            >>> repo = InstanceRepository()
            >>> prod_instances = repo.find_by_tenant("prod")
        """
        all_instances = self.find_all(include_expired=True)
        return [i for i in all_instances if i.tenant == tenant]

    def find_expired(self) -> list[Instance]:
        """Find all expired instances.

        Instances with expires_at=None never expire and are not included.

        Returns:
            List of expired Instance objects, sorted by creation date (newest first)

        Examples:
            >>> repo = InstanceRepository()
            >>> expired = repo.find_expired()
            >>> print(f"Found {len(expired)} expired instances")
        """
        now = datetime.now()
        all_instances = self.find_all(include_expired=True)
        return [
            i for i in all_instances if i.expires_at is not None and i.expires_at <= now
        ]

    def delete(self, instance_id: str) -> None:
        """Delete an instance from storage.

        Args:
            instance_id: The ID of the instance to delete

        Raises:
            ValueError: If the instance doesn't exist

        Examples:
            >>> repo = InstanceRepository()
            >>> repo.delete("abc-123")
        """
        state = self._load_state()

        if instance_id not in state["instances"]:
            raise ValueError(f"Instance {instance_id} not found")

        del state["instances"][instance_id]
        self._save_state(state)

    def exists(self, instance_id: str) -> bool:
        """Check if an instance exists.

        Args:
            instance_id: The ID to check

        Returns:
            True if the instance exists, False otherwise

        Examples:
            >>> repo = InstanceRepository()
            >>> if repo.exists("abc-123"):
            ...     print("Instance exists")
        """
        state = self._load_state()
        return instance_id in state["instances"]
