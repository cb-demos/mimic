"""Tests for cleanup outcome reporting (kept reasons, already-gone, API counts)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mimic.cleanup_manager import (
    CONDITIONAL_FLAG,
    CONDITIONAL_SHARED_APP,
    KEEP_REASON_FLAG,
    KEEP_REASON_PREEXISTING,
    REMOVED_WITH_APPLICATION,
    CleanupManager,
    keep_reason,
    summarize_results,
)
from mimic.instance_repository import InstanceRepository
from mimic.models import (
    CloudBeesApplication,
    CloudBeesComponent,
    CloudBeesEnvironment,
    CloudBeesFlag,
    GitHubRepository,
    Instance,
)
from mimic.web.api.cleanup import _to_cleanup_response, _to_cleanup_results

NOW = datetime.now()


def _repo(name: str, existed: bool = False) -> GitHubRepository:
    return GitHubRepository(
        id=f"acme/{name}",
        name=name,
        owner="acme",
        url=f"https://github.com/acme/{name}",
        created_at=NOW,
        existed=existed,
    )


def test_keep_reason_rules():
    flag = CloudBeesFlag(
        id="f", name="f", org_id="o", type="boolean", key="f", created_at=NOW
    )
    shared = CloudBeesApplication(
        id="a", name="a", org_id="o", is_shared=True, created_at=NOW
    )
    owned_app = CloudBeesApplication(id="b", name="b", org_id="o", created_at=NOW)
    old_comp = CloudBeesComponent(
        id="c", name="c", org_id="o", created_at=NOW, existed=True
    )

    assert keep_reason("cloudbees_flag", flag) == KEEP_REASON_FLAG
    assert keep_reason("cloudbees_application", shared) == CONDITIONAL_SHARED_APP
    assert keep_reason("cloudbees_application", owned_app) is None
    assert keep_reason("cloudbees_component", old_comp) == KEEP_REASON_PREEXISTING
    assert keep_reason("github_repo", _repo("new")) is None


@pytest.fixture
def manager(tmp_path):
    repo = InstanceRepository(state_file=tmp_path / "state.json")
    config = MagicMock()
    config.get_github_pat.return_value = "gh-test"
    config.get_cloudbees_pat.return_value = None  # GitHub only
    config.get_tenant_url.return_value = None
    return CleanupManager(
        config_manager=config, instance_repository=repo, console=MagicMock()
    ), repo


@pytest.mark.asyncio
async def test_repo_already_gone_is_reported_distinctly(manager):
    cleanup, repo = manager
    repo.save(
        Instance(
            id="s1",
            scenario_id="x",
            name="n",
            tenant="t",
            created_at=NOW,
            expires_at=None,
            repositories=[_repo("gone"), _repo("here"), _repo("old", existed=True)],
        )
    )
    with patch("mimic.cleanup_manager.GitHubClient") as gh_cls:
        gh = AsyncMock()
        # "gone" returns 404 (False); "here" is deleted (True)
        gh.delete_repository.side_effect = lambda name: name != "acme/gone"
        gh_cls.return_value = gh
        results = await cleanup.cleanup_session("s1")

    assert summarize_results(results) == {
        "deleted": 1,
        "already_gone": 1,
        "kept": 1,
        "failed": 0,
    }
    gone = next(c for c in results["cleaned"] if c["id"] == "acme/gone")
    assert gone["already_gone"] is True
    assert gone["name"] == "gone"


def test_api_counts_when_everything_is_kept():
    """The bug seen in the UI: 0 deleted must not be reported as 5 deleted."""
    result = {
        "cleaned": [],
        "errors": [],
        "skipped": [
            {"type": t, "id": t, "name": t, "reason": "Existed before this run"}
            for t in ["a", "b", "c", "d", "e"]
        ],
    }
    response = _to_cleanup_response(_to_cleanup_results(result), dry_run=False)
    assert response.deleted_count == 0
    assert response.cleaned_count == 0
    assert response.kept_count == 5
    assert response.failed_count == 0


def test_api_counts_mixed_outcomes():
    result = {
        "cleaned": [
            {"type": "github_repo", "id": "r1", "name": "r1"},
            {"type": "github_repo", "id": "r2", "name": "r2", "already_gone": True},
        ],
        "errors": [
            {"type": "cloudbees_component", "id": "c", "name": "c", "error": "x"}
        ],
        "skipped": [{"type": "cloudbees_flag", "id": "f", "name": "f", "reason": "r"}],
    }
    response = _to_cleanup_response(
        _to_cleanup_results(result, session_id="s"), dry_run=True
    )
    assert (
        response.deleted_count,
        response.already_gone_count,
        response.kept_count,
        response.failed_count,
    ) == (1, 1, 1, 1)
    assert response.dry_run is True
    assert all(r.session_id == "s" for r in response.results)


def _shared_app_instance(flag_existed: bool = False) -> Instance:
    return Instance(
        id="shared-run",
        scenario_id="x",
        name="n",
        tenant="t",
        created_at=NOW,
        expires_at=None,
        environments=[
            CloudBeesEnvironment(id="env-mine", name="e", org_id="o", created_at=NOW)
        ],
        applications=[
            CloudBeesApplication(
                id="app-1", name="app", org_id="o", is_shared=True, created_at=NOW
            )
        ],
        flags=[
            CloudBeesFlag(
                id="flag-1",
                name="default.score",
                org_id="o",
                type="boolean",
                key="default.score",
                created_at=NOW,
                existed=flag_existed,
            )
        ],
    )


def test_flag_reason_follows_its_application():
    instance = _shared_app_instance()
    assert (
        keep_reason("cloudbees_flag", instance.flags[0], instance) == CONDITIONAL_FLAG
    )
    # Without instance context the flag is kept, as before
    assert keep_reason("cloudbees_flag", instance.flags[0]) == KEEP_REASON_FLAG


@pytest.fixture
def cb_manager(tmp_path):
    repo = InstanceRepository(state_file=tmp_path / "state.json")
    config = MagicMock()
    config.get_github_pat.return_value = None
    config.get_cloudbees_pat.return_value = "cb-test"
    config.get_tenant_url.return_value = "https://api.example.invalid"
    return (
        CleanupManager(
            config_manager=config, instance_repository=repo, console=MagicMock()
        ),
        repo,
    )


async def _run_shared(cb_manager, linked_envs, dry_run=False, list_error=None):
    cleanup, repo = cb_manager
    repo.save(_shared_app_instance())
    unify = MagicMock()
    if list_error:
        unify.list_applications.side_effect = list_error
    else:
        unify.list_applications.return_value = {
            "service": [{"id": "app-1", "linkedEnvironmentIds": linked_envs}]
        }
    unify.delete_application.return_value = True
    unify.delete_environment.return_value = True
    with patch("mimic.cleanup_manager.UnifyAPIClient", return_value=unify):
        results = await cleanup.cleanup_session("shared-run", dry_run=dry_run)
    return results, unify


@pytest.mark.asyncio
async def test_unused_shared_app_created_by_run_is_deleted_with_its_flags(cb_manager):
    # Only this run's own environment is attached
    results, unify = await _run_shared(cb_manager, ["env-mine"])

    unify.delete_application.assert_called_once_with("o", "app-1")
    flag = next(c for c in results["cleaned"] if c["type"] == "cloudbees_flag")
    assert flag["message"] == REMOVED_WITH_APPLICATION
    assert summarize_results(results)["kept"] == 0


@pytest.mark.asyncio
async def test_shared_app_still_used_by_another_run_is_kept(cb_manager):
    results, unify = await _run_shared(cb_manager, ["env-mine", "env-someone-else"])

    unify.delete_application.assert_not_called()
    kept = {s["type"]: s["reason"] for s in results["skipped"]}
    assert "still used" in kept["cloudbees_application"]
    assert kept["cloudbees_flag"] == KEEP_REASON_FLAG
    # This run's own environment is still deleted
    unify.delete_environment.assert_called_once_with("o", "env-mine")


@pytest.mark.asyncio
async def test_shared_app_is_kept_if_usage_check_fails(cb_manager):
    results, unify = await _run_shared(cb_manager, [], list_error=RuntimeError("boom"))
    unify.delete_application.assert_not_called()
    reasons = [s["reason"] for s in results["skipped"]]
    assert any("Could not check" in r for r in reasons)


@pytest.mark.asyncio
async def test_dry_run_previews_shared_app_deletion_without_deleting(cb_manager):
    results, unify = await _run_shared(cb_manager, ["env-mine"], dry_run=True)
    unify.delete_application.assert_not_called()
    types = {c["type"] for c in results["cleaned"] if c.get("dry_run")}
    assert {"cloudbees_application", "cloudbees_flag"} <= types
