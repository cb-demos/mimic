"""API endpoints for scenario pack management."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from mimic.exceptions import ScenarioError
from mimic.gh import GitHubClient, parse_github_url
from mimic.scenario_pack_manager import ScenarioPackManager

from ..dependencies import ConfigDep
from ..models import (
    AddScenarioPackRequest,
    DiscoverRefsRequest,
    DiscoverRefsResponse,
    EnablePackRequest,
    GitHubBranch,
    GitHubPullRequest,
    PackRefInfo,
    ScenarioPackInfo,
    ScenarioPackListResponse,
    StatusResponse,
    SwitchPackRefRequest,
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

        # Get current ref info
        ref_info = config.get_pack_current_ref(name) or {}
        current_ref = PackRefInfo(
            type=ref_info.get("type", "branch"),
            branch=ref_info.get("branch", pack_config.get("branch", "main")),
            pr_number=ref_info.get("pr_number"),
            pr_title=ref_info.get("pr_title"),
            pr_author=ref_info.get("pr_author"),
            pr_head_repo_url=ref_info.get("pr_head_repo_url"),
            last_updated=ref_info.get("last_updated"),
        )

        packs.append(
            ScenarioPackInfo(
                name=name,
                git_url=pack_config.get("url", ""),
                enabled=pack_config.get("enabled", True),
                scenario_count=scenario_count,
                current_ref=current_ref,
            )
        )

    return ScenarioPackListResponse(packs=packs)


@router.post("/discover-refs", response_model=DiscoverRefsResponse)
async def discover_refs(request: DiscoverRefsRequest, config: ConfigDep):
    """Discover available branches and PRs for a GitHub URL.

    Args:
        request: GitHub URL to discover refs for
        config: Config manager dependency

    Returns:
        Available branches and pull requests
    """
    # Parse GitHub URL
    parsed = parse_github_url(request.git_url)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub URL. Must be a github.com repository URL.",
        )

    owner, repo = parsed

    # Get GitHub token
    github_pat = config.get_github_pat()
    if not github_pat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not configured. Configure it in Settings.",
        )

    try:
        client = GitHubClient(github_pat)

        # Fetch branches, PRs, and default branch concurrently
        branches_data = await client.list_branches(owner, repo)
        prs_data = await client.list_pull_requests(owner, repo, state="open")
        default_branch = await client.get_default_branch(owner, repo)

        # Convert to response models
        branches = [
            GitHubBranch(
                name=b["name"],
                sha=b["commit"]["sha"],
                protected=b.get("protected", False),
            )
            for b in branches_data
        ]

        pull_requests = [
            GitHubPullRequest(
                number=pr["number"],
                title=pr["title"],
                head_branch=pr["head"]["ref"],
                head_sha=pr["head"]["sha"],
                head_repo_url=(
                    pr["head"]["repo"]["clone_url"] if pr["head"]["repo"] else None
                ),
                author=pr["user"]["login"],
                state=pr["state"],
                created_at=pr["created_at"],
                updated_at=pr["updated_at"],
            )
            for pr in prs_data
        ]

        return DiscoverRefsResponse(
            owner=owner,
            repo=repo,
            default_branch=default_branch or "main",
            branches=branches,
            pull_requests=pull_requests,
        )

    except Exception as e:
        logger.error(f"Failed to discover refs for {owner}/{repo}: {e}")
        return DiscoverRefsResponse(
            owner=owner,
            repo=repo,
            default_branch="main",
            branches=[],
            pull_requests=[],
            error=str(e),
        )


@router.post("/add", response_model=StatusResponse)
async def add_pack(request: AddScenarioPackRequest, config: ConfigDep):
    """Add a new scenario pack.

    Args:
        request: Pack name, git URL, and optional branch/PR info
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
        # If it's a PR from a fork, we need special handling
        if request.pr_number and request.pr_head_repo_url:
            # Clone from upstream without branch specification (gets default branch)
            pack_manager.clone_pack(request.name, request.git_url)
            # Then checkout the PR from the fork
            pack_manager.checkout_pr(
                request.name,
                request.pr_number,
                request.branch,
                head_repo_url=request.pr_head_repo_url,
            )
        else:
            # Normal clone with specified branch (PR from same repo or regular branch)
            pack_manager.clone_pack(
                request.name, request.git_url, branch=request.branch
            )

        # Add to config with PR info if provided
        config.add_scenario_pack(
            request.name,
            request.git_url,
            branch=request.branch,
            enabled=True,
            pr_number=request.pr_number,
            pr_title=request.pr_title,
            pr_author=request.pr_author,
            pr_head_repo_url=request.pr_head_repo_url,
        )

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


@router.post("/{pack_name}/switch-ref", response_model=StatusResponse)
async def switch_pack_ref(
    pack_name: str, request: SwitchPackRefRequest, config: ConfigDep
):
    """Switch a pack to a different branch or PR.

    Args:
        pack_name: Name of the pack
        request: Branch or PR to switch to
        config: Config manager dependency

    Returns:
        Status message
    """
    # Validate request - exactly one of branch or pr_number must be set
    if (request.branch is None) == (request.pr_number is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify exactly one of 'branch' or 'pr_number'",
        )

    # Verify pack exists
    existing_pack = config.get_scenario_pack(pack_name)
    if not existing_pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario pack '{pack_name}' not found",
        )

    pack_manager = _get_pack_manager(config)

    try:
        if request.branch:
            # Switch to branch
            pack_manager.switch_branch(pack_name, request.branch)
            config.update_pack_ref(pack_name, branch=request.branch)
            message = f"Switched pack '{pack_name}' to branch '{request.branch}'"

        else:
            # Checkout PR - need to fetch PR details first
            github_pat = config.get_github_pat()
            if not github_pat:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GitHub token required to checkout PR",
                )

            # Parse GitHub URL to get owner/repo
            git_url = existing_pack.get("url", "")
            parsed = parse_github_url(git_url)
            if not parsed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pack URL is not a valid GitHub URL",
                )

            owner, repo = parsed
            client = GitHubClient(github_pat)

            # Fetch PR details
            prs = await client.list_pull_requests(owner, repo, state="all")
            pr_data = next(
                (pr for pr in prs if pr["number"] == request.pr_number), None
            )

            if not pr_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Pull request #{request.pr_number} not found",
                )

            head_branch = pr_data["head"]["ref"]
            pr_title = pr_data["title"]
            pr_author = pr_data["user"]["login"]
            head_repo_url = (
                pr_data["head"]["repo"]["clone_url"]
                if pr_data["head"]["repo"]
                else None
            )

            # Checkout PR (pr_number is guaranteed to be set here)
            pr_number = request.pr_number
            assert pr_number is not None
            pack_manager.checkout_pr(
                pack_name, pr_number, head_branch, head_repo_url=head_repo_url
            )
            config.update_pack_ref(
                pack_name,
                branch=head_branch,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_author=pr_author,
                pr_head_repo_url=head_repo_url,
            )
            message = f"Checked out PR #{pr_number} for pack '{pack_name}'"

        logger.info(message)
        return StatusResponse(status="success", message=message)

    except ScenarioError as e:
        logger.error(f"Failed to switch ref for pack {pack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error switching ref for pack {pack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to switch pack reference: {str(e)}",
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
            # Get current ref info to handle PR updates correctly
            ref_info = config.get_pack_current_ref(pack_name) or {}
            pr_number = ref_info.get("pr_number")
            head_branch = ref_info.get("branch")
            head_repo_url = ref_info.get("pr_head_repo_url")

            pack_manager.update_pack(
                pack_name,
                pr_number=pr_number,
                head_branch=head_branch,
                head_repo_url=head_repo_url,
            )
            updated.append(pack_name)
            logger.info(f"Updated scenario pack: {pack_name}")

        except ScenarioError as e:
            errors[pack_name] = str(e)
            logger.error(f"Failed to update scenario pack {pack_name}: {e}")
        except Exception as e:
            errors[pack_name] = str(e)
            logger.error(f"Unexpected error updating scenario pack {pack_name}: {e}")

    return UpdatePacksResponse(updated=updated, errors=errors)
