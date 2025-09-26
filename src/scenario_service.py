"""Service layer for scenario management and execution."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from src.auth import get_auth_service
from src.config import settings
from src.creation_pipeline import CreationPipeline
from src.database import get_database
from src.progress_tracker import cleanup_progress_tracker, create_progress_tracker
from src.scenarios import Scenario, get_scenario_manager

logger = logging.getLogger(__name__)


class ScenarioService:
    """Centralized service for scenario operations."""

    def __init__(self):
        self.manager = get_scenario_manager()

    def list_scenarios(self) -> list[dict[str, Any]]:
        """List all available scenarios with their parameter schemas."""
        return self.manager.list_scenarios()

    def get_scenario(self, scenario_id: str) -> Scenario | None:
        """Get a specific scenario by ID."""
        return self.manager.get_scenario(scenario_id)

    async def execute_scenario(
        self,
        scenario_id: str,
        organization_id: str,
        unify_pat: str,
        email: str,
        invitee_username: str | None = None,
        parameters: dict[str, Any] | None = None,
        expires_in_days: int | None = 7,
    ) -> dict[str, Any]:
        """
        Execute a complete scenario using the Creation Pipeline.

        This will:
        1. Create repositories from templates with content replacements
        2. Create CloudBees components for repos that need them
        3. Create feature flags
        4. Create environments
        5. Create applications linking components and environments
        6. Configure flags across environments

        Args:
            scenario_id: The ID of the scenario to execute
            organization_id: CloudBees Unify organization UUID
            unify_pat: CloudBees Platform API token
            invitee_username: Optional GitHub username to invite to the organization
            parameters: Dictionary of scenario parameters (both required and optional)

        Returns:
            Dictionary with execution status and summary

        Raises:
            ValueError: If scenario not found
            ValidationError: If parameters are invalid
            PipelineError: If pipeline execution fails
        """
        scenario = self.manager.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        # Default empty dict if None
        scenario_parameters = parameters or {}

        # Validate and preprocess input parameters
        processed_parameters = scenario.validate_input(scenario_parameters)

        # Create resource session for tracking
        session_id = str(uuid.uuid4())
        db = get_database()

        # Calculate expiration timestamp if expires_in_days is provided
        expires_at = None
        if expires_in_days is not None:
            expires_at = (
                datetime.utcnow() + timedelta(days=expires_in_days)
            ).isoformat()

        await db.create_session(
            session_id=session_id,
            email=email,
            scenario_id=scenario_id,
            expires_at=expires_at,
            parameters=processed_parameters,
        )

        logger.info(f"Created resource session {session_id} for user {email}")

        # Create progress tracker for real-time updates
        create_progress_tracker(session_id)

        # Determine GitHub PAT (user's custom PAT or default service account)
        github_pat = settings.GITHUB_TOKEN  # Default service account
        auth_service = get_auth_service()

        try:
            # Try to get user's custom GitHub PAT if they provided one
            user_github_pat = await auth_service.get_pat(email, "github")
            if user_github_pat:
                github_pat = user_github_pat
                logger.info(f"Using user's custom GitHub PAT for {email}")
            else:
                logger.info(f"Using default service account GitHub PAT for {email}")
        except Exception as e:
            # If user doesn't have a GitHub PAT or it fails, use service account
            logger.info(
                f"Using default service account GitHub PAT for {email} (fallback: {e})"
            )

        # Create and execute pipeline
        pipeline = CreationPipeline(
            organization_id=organization_id,
            endpoint_id=settings.CLOUDBEES_ENDPOINT_ID,
            invitee_username=invitee_username,
            unify_pat=unify_pat,
            session_id=session_id,
            email=email,
            github_pat=github_pat,
        )

        try:
            # Execute the complete scenario
            summary = await pipeline.execute_scenario(scenario, processed_parameters)

            return {
                "status": "success",
                "message": "Scenario executed successfully",
                "scenario_id": scenario_id,
                "session_id": session_id,
                "parameters": processed_parameters,
                "organization_id": organization_id,
                "invitee_username": invitee_username,
                "summary": summary,
            }
        finally:
            # Clean up progress tracker after a delay to allow final events to be consumed
            import asyncio
            asyncio.create_task(self._cleanup_progress_tracker_delayed(session_id))

    async def _cleanup_progress_tracker_delayed(self, session_id: str) -> None:
        """Clean up progress tracker after a delay to allow final events to be consumed."""
        await asyncio.sleep(5)  # Allow time for final events to be sent
        cleanup_progress_tracker(session_id)

    async def start_scenario_execution(
        self,
        scenario_id: str,
        organization_id: str,
        unify_pat: str,
        email: str,
        invitee_username: str | None = None,
        parameters: dict[str, Any] | None = None,
        expires_in_days: int | None = 7,
    ) -> str:
        """
        Start scenario execution asynchronously and return session ID immediately.

        This method:
        1. Creates the session and progress tracker
        2. Starts execution in a background task
        3. Returns session ID for real-time progress tracking

        Args:
            Same as execute_scenario

        Returns:
            Session ID for progress tracking
        """
        scenario = self.manager.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        # Default empty dict if None
        scenario_parameters = parameters or {}

        # Validate and preprocess input parameters
        processed_parameters = scenario.validate_input(scenario_parameters)

        # Create resource session for tracking
        session_id = str(uuid.uuid4())
        db = get_database()

        # Calculate expiration timestamp if expires_in_days is provided
        expires_at = None
        if expires_in_days is not None:
            expires_at = (
                datetime.utcnow() + timedelta(days=expires_in_days)
            ).isoformat()

        await db.create_session(
            session_id=session_id,
            email=email,
            scenario_id=scenario_id,
            expires_at=expires_at,
            parameters=processed_parameters,
        )

        logger.info(f"Created resource session {session_id} for user {email}")

        # Create progress tracker for real-time updates
        create_progress_tracker(session_id)

        # Start execution in background task
        import asyncio
        asyncio.create_task(self._execute_scenario_background(
            session_id=session_id,
            scenario=scenario,
            processed_parameters=processed_parameters,
            organization_id=organization_id,
            unify_pat=unify_pat,
            email=email,
            invitee_username=invitee_username,
        ))

        return session_id

    async def _execute_scenario_background(
        self,
        session_id: str,
        scenario: Scenario,
        processed_parameters: dict[str, Any],
        organization_id: str,
        unify_pat: str,
        email: str,
        invitee_username: str | None = None,
    ) -> None:
        """
        Execute scenario in background with progress tracking.
        """
        try:
            # Determine GitHub PAT (user's custom PAT or default service account)
            github_pat = settings.GITHUB_TOKEN  # Default service account
            auth_service = get_auth_service()

            try:
                # Try to get user's custom GitHub PAT if they provided one
                user_github_pat = await auth_service.get_pat(email, "github")
                if user_github_pat:
                    github_pat = user_github_pat
                    logger.info(f"Using user's custom GitHub PAT for {email}")
                else:
                    logger.info(f"Using default service account GitHub PAT for {email}")
            except Exception as e:
                # If user doesn't have a GitHub PAT or it fails, use service account
                logger.info(
                    f"Using default service account GitHub PAT for {email} (fallback: {e})"
                )

            # Create and execute pipeline
            pipeline = CreationPipeline(
                organization_id=organization_id,
                endpoint_id=settings.CLOUDBEES_ENDPOINT_ID,
                invitee_username=invitee_username,
                unify_pat=unify_pat,
                session_id=session_id,
                email=email,
                github_pat=github_pat,
            )

            # Execute the complete scenario
            await pipeline.execute_scenario(scenario, processed_parameters)

        except Exception as e:
            logger.error(f"Background scenario execution failed: {e}")
            # Progress tracker will handle the error through the pipeline
        finally:
            # Clean up progress tracker after a delay
            await self._cleanup_progress_tracker_delayed(session_id)
