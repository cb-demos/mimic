"""Service layer for scenario management and execution."""

import logging
from typing import Any

from src.config import settings
from src.creation_pipeline import CreationPipeline
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
        invitee_username: str | None = None,
        parameters: dict[str, Any] | None = None,
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

        # Create and execute pipeline
        pipeline = CreationPipeline(
            organization_id=organization_id,
            endpoint_id=settings.CLOUDBEES_ENDPOINT_ID,
            invitee_username=invitee_username,
            unify_pat=unify_pat,
        )

        # Execute the complete scenario
        summary = await pipeline.execute_scenario(scenario, processed_parameters)

        return {
            "status": "success",
            "message": "Scenario executed successfully",
            "scenario_id": scenario_id,
            "parameters": processed_parameters,
            "organization_id": organization_id,
            "invitee_username": invitee_username,
            "summary": summary,
        }
