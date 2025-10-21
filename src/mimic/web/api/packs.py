"""API endpoints for scenario pack management."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from mimic.exceptions import ScenarioError
from mimic.scenario_pack_manager import ScenarioPackManager

from ..dependencies import ConfigDep
from ..models import (
    AddScenarioPackRequest,
    EnablePackRequest,
    ScenarioPackInfo,
    ScenarioPackListResponse,
    StatusResponse,
    UpdatePacksRequest,
    UpdatePacksResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/packs", tags=["scenario-packs"])


def _get_pack_manager(config: ConfigDep) -> ScenarioPackManager:
    """Get a ScenarioPackManager instance.

    Args:
        config: Config manager dependency

    Returns:
        ScenarioPackManager instance
    """
    from mimic.config_manager import ConfigManager

    packs_dir = ConfigManager.PACKS_DIR
    return ScenarioPackManager(packs_dir)


def _count_scenarios_in_pack(pack_path: Path) -> int:
    """Count the number of scenario YAML files in a pack.

    Args:
        pack_path: Path to the scenario pack directory

    Returns:
        Number of .yaml and .yml files in the pack directory
    """
    if not pack_path.exists():
        return 0

    # Count both .yaml and .yml files (matching scenarios.py loading behavior)
    yaml_files = list(pack_path.glob("*.yaml")) + list(pack_path.glob("*.yml"))
    return len(yaml_files)


@router.get("", response_model=ScenarioPackListResponse)
async def list_packs(config: ConfigDep):
    """List all scenario packs.

    Returns:
        List of scenario packs with their configuration
    """
    pack_configs = config.list_scenario_packs()
    pack_manager = _get_pack_manager(config)

    packs = []
    for name, pack_config in pack_configs.items():
        pack_path = pack_manager.get_pack_path(name)
        scenario_count = 0

        if pack_path:
            scenario_count = _count_scenarios_in_pack(pack_path)

        packs.append(
            ScenarioPackInfo(
                name=name,
                git_url=pack_config.get("url", ""),
                enabled=pack_config.get("enabled", True),
                scenario_count=scenario_count,
            )
        )

    return ScenarioPackListResponse(packs=packs)


@router.post("/add", response_model=StatusResponse)
async def add_pack(request: AddScenarioPackRequest, config: ConfigDep):
    """Add a new scenario pack.

    Args:
        request: Pack name and git URL
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify pack doesn't already exist
    existing_pack = config.get_scenario_pack(request.name)
    if existing_pack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario pack '{request.name}' already exists",
        )

    pack_manager = _get_pack_manager(config)

    try:
        # Clone the pack
        pack_manager.clone_pack(request.name, request.git_url)

        # Add to config
        config.add_scenario_pack(request.name, request.git_url, enabled=True)

        logger.info(f"Added scenario pack: {request.name} from {request.git_url}")

        return StatusResponse(
            status="success",
            message=f"Scenario pack '{request.name}' added successfully",
        )

    except ScenarioError as e:
        logger.error(f"Failed to add scenario pack {request.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error adding scenario pack {request.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add scenario pack: {str(e)}",
        ) from e


@router.delete("/{pack_name}", response_model=StatusResponse)
async def remove_pack(pack_name: str, config: ConfigDep):
    """Remove a scenario pack.

    Args:
        pack_name: Name of the pack to remove
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify pack exists
    existing_pack = config.get_scenario_pack(pack_name)
    if not existing_pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario pack '{pack_name}' not found",
        )

    pack_manager = _get_pack_manager(config)

    try:
        # Remove the pack directory
        pack_manager.remove_pack(pack_name)

        # Remove from config
        config.remove_scenario_pack(pack_name)

        logger.info(f"Removed scenario pack: {pack_name}")

        return StatusResponse(
            status="success",
            message=f"Scenario pack '{pack_name}' removed successfully",
        )

    except ScenarioError as e:
        logger.error(f"Failed to remove scenario pack {pack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error removing scenario pack {pack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove scenario pack: {str(e)}",
        ) from e


@router.patch("/{pack_name}/enable", response_model=StatusResponse)
async def enable_pack(pack_name: str, request: EnablePackRequest, config: ConfigDep):
    """Enable or disable a scenario pack.

    Args:
        pack_name: Name of the pack
        request: Enable/disable flag
        config: Config manager dependency

    Returns:
        Status message
    """
    # Verify pack exists
    existing_pack = config.get_scenario_pack(pack_name)
    if not existing_pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario pack '{pack_name}' not found",
        )

    try:
        config.set_scenario_pack_enabled(pack_name, request.enabled)

        action = "enabled" if request.enabled else "disabled"
        logger.info(f"Scenario pack '{pack_name}' {action}")

        return StatusResponse(
            status="success",
            message=f"Scenario pack '{pack_name}' {action} successfully",
        )

    except Exception as e:
        logger.error(f"Failed to update scenario pack {pack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update scenario pack: {str(e)}",
        ) from e


@router.post("/update", response_model=UpdatePacksResponse)
async def update_packs(request: UpdatePacksRequest, config: ConfigDep):
    """Update one or all scenario packs.

    Args:
        request: Pack name (optional, None = update all)
        config: Config manager dependency

    Returns:
        Update results with list of updated packs and errors
    """
    pack_manager = _get_pack_manager(config)
    pack_configs = config.list_scenario_packs()

    updated = []
    errors = {}

    # Determine which packs to update
    packs_to_update = (
        [request.pack_name] if request.pack_name else list(pack_configs.keys())
    )

    for pack_name in packs_to_update:
        if pack_name not in pack_configs:
            errors[pack_name] = "Pack not found"
            continue

        try:
            pack_manager.update_pack(pack_name)
            updated.append(pack_name)
            logger.info(f"Updated scenario pack: {pack_name}")

        except ScenarioError as e:
            errors[pack_name] = str(e)
            logger.error(f"Failed to update scenario pack {pack_name}: {e}")
        except Exception as e:
            errors[pack_name] = str(e)
            logger.error(f"Unexpected error updating scenario pack {pack_name}: {e}")

    return UpdatePacksResponse(updated=updated, errors=errors)
