"""State tracking for Mimic sessions and resources."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .paths import get_config_dir


class Resource(BaseModel):
    """A resource created during scenario execution."""

    type: str  # github_repo, cloudbees_component, cloudbees_environment, etc.
    id: str  # Resource identifier (repo name, component UUID, etc.)
    name: str  # Human-readable name
    org_id: str | None = None  # For CloudBees resources
    metadata: dict[str, Any] = Field(default_factory=dict)  # Additional data


class Session(BaseModel):
    """A scenario execution session."""

    session_id: str
    scenario_id: str
    run_name: str | None = (
        None  # Human-readable name for this run (resolved from scenario name_template), defaults to session_id for backwards compatibility
    )
    environment: str  # Which CloudBees environment was used
    created_at: datetime
    expires_at: datetime | None  # None means never expires
    resources: list[Resource] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)  # Additional session data


class StateTracker:
    """Manages session state and resource tracking."""

    def __init__(self, state_file: Path | str | None = None):
        """
        Initialize the state tracker.

        Args:
            state_file: Path to state JSON file. Defaults to $MIMIC_CONFIG_DIR/state.json or ~/.mimic/state.json
        """
        if state_file is None:
            state_file = get_config_dir() / "state.json"
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize state if file doesn't exist
        if not self.state_file.exists():
            self._save_state({"sessions": {}})

    def _load_state(self) -> dict[str, Any]:
        """Load state from JSON file."""
        if not self.state_file.exists():
            return {"sessions": {}}

        with open(self.state_file) as f:
            return json.load(f)

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save state to JSON file."""
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def create_session(
        self,
        session_id: str,
        scenario_id: str,
        environment: str,
        run_name: str | None = None,
        expiration_days: int | None = 7,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new session.

        Args:
            session_id: Unique session identifier
            scenario_id: The scenario that was executed
            run_name: Human-readable name for this run (defaults to session_id if not provided)
            environment: CloudBees environment name
            expiration_days: Days until session expires (None = never expires)
            metadata: Additional session metadata

        Returns:
            Created Session object
        """
        now = datetime.now()
        expires_at = (
            now + timedelta(days=expiration_days)
            if expiration_days is not None
            else None
        )

        # Use session_id as fallback if run_name not provided
        if not run_name:
            run_name = session_id

        session = Session(
            session_id=session_id,
            scenario_id=scenario_id,
            run_name=run_name,
            environment=environment,
            created_at=now,
            expires_at=expires_at,
            resources=[],
            metadata=metadata or {},
        )

        state = self._load_state()
        state["sessions"][session_id] = session.model_dump(mode="json")
        self._save_state(state)

        return session

    def add_resource(
        self,
        session_id: str,
        resource_type: str,
        resource_id: str,
        resource_name: str,
        org_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a resource to a session.

        Args:
            session_id: Session to add resource to
            resource_type: Type of resource (github_repo, cloudbees_component, etc.)
            resource_id: Unique resource identifier
            resource_name: Human-readable resource name
            org_id: Organization ID for CloudBees resources
            metadata: Additional resource metadata
        """
        state = self._load_state()

        if session_id not in state["sessions"]:
            raise ValueError(f"Session {session_id} not found")

        resource = Resource(
            type=resource_type,
            id=resource_id,
            name=resource_name,
            org_id=org_id,
            metadata=metadata or {},
        )

        state["sessions"][session_id]["resources"].append(
            resource.model_dump(mode="json")
        )
        self._save_state(state)

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        state = self._load_state()
        session_data = state["sessions"].get(session_id)

        if not session_data:
            return None

        return Session(**session_data)

    def get_session_by_identifier(self, identifier: str) -> Session | None:
        """
        Get a session by either session ID or run name.

        Args:
            identifier: Session ID or run name

        Returns:
            Session object if found, None otherwise
        """
        # First try to get by session_id (exact match)
        session = self.get_session(identifier)
        if session:
            return session

        # If not found, search by run_name
        state = self._load_state()
        for _session_id, session_data in state["sessions"].items():
            if session_data.get("run_name") == identifier:
                return Session(**session_data)

        return None

    def list_sessions(self, include_expired: bool = True) -> list[Session]:
        """
        List all sessions.

        Args:
            include_expired: Whether to include expired sessions

        Returns:
            List of Session objects
        """
        state = self._load_state()
        sessions = []
        now = datetime.now()

        for session_data in state["sessions"].values():
            session = Session(**session_data)

            # Include session if:
            # - include_expired is True, OR
            # - session never expires (expires_at is None), OR
            # - session hasn't expired yet
            if (
                include_expired
                or session.expires_at is None
                or session.expires_at > now
            ):
                sessions.append(session)

        # Sort by creation date, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def list_expired_sessions(self) -> list[Session]:
        """List all expired sessions (sessions with expires_at=None never expire)."""
        now = datetime.now()
        all_sessions = self.list_sessions(include_expired=True)
        return [
            s for s in all_sessions if s.expires_at is not None and s.expires_at <= now
        ]

    def delete_session(self, session_id: str) -> None:
        """Delete a session from state."""
        state = self._load_state()

        if session_id not in state["sessions"]:
            raise ValueError(f"Session {session_id} not found")

        del state["sessions"][session_id]
        self._save_state(state)

    def update_session_metadata(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        """Update session metadata."""
        state = self._load_state()

        if session_id not in state["sessions"]:
            raise ValueError(f"Session {session_id} not found")

        state["sessions"][session_id]["metadata"].update(metadata)
        self._save_state(state)
