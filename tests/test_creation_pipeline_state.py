"""Tests for CreationPipeline state tracking (pre-existing resources, checkpoints)."""

from unittest.mock import AsyncMock

import pytest

from mimic.exceptions import PipelineError, UnifyAPIError
from mimic.models import Instance
from mimic.pipeline import CreationPipeline
from mimic.scenarios import RepositoryConfig, Scenario


def _scenario() -> Scenario:
    return Scenario(
        id="test-scenario",
        name="Test Scenario",
        summary="Test",
        repositories=[
            RepositoryConfig(
                source="template/repo",
                target_org="acme",
                repo_name_template="new-repo",
                create_component=True,
            ),
            RepositoryConfig(
                source="template/repo",
                target_org="acme",
                repo_name_template="old-repo",
                create_component=True,
            ),
        ],
    )


def _pipeline(checkpoints: list[Instance]) -> CreationPipeline:
    return CreationPipeline(
        organization_id="org-1",
        endpoint_id="ep-1",
        unify_pat="unify-test",
        unify_base_url="https://api.example.invalid",
        session_id="sess-1",
        github_pat="gh-test",
        scenario_id="test-scenario",
        tenant="preprod",
        on_checkpoint=checkpoints.append,
    )


def _fake_repos(pipeline: CreationPipeline):
    async def create_repositories(_repos, _params):
        pipeline.repo_manager.created_repositories.update(
            {
                "new-repo": {
                    "name": "new-repo",
                    "full_name": "acme/new-repo",
                    "html_url": "https://github.com/acme/new-repo",
                    "existed": False,
                },
                "old-repo": {
                    "name": "old-repo",
                    "full_name": "acme/old-repo",
                    "html_url": "https://github.com/acme/old-repo",
                    "existed": True,
                },
            }
        )
        return pipeline.repo_manager.created_repositories

    return create_repositories


@pytest.mark.asyncio
async def test_failed_run_checkpoints_resources_created_before_failure():
    checkpoints: list[Instance] = []
    pipeline = _pipeline(checkpoints)
    pipeline.repo_manager.create_repositories = _fake_repos(pipeline)  # type: ignore[method-assign]
    pipeline.resource_manager.create_components = AsyncMock(  # type: ignore[method-assign]
        side_effect=UnifyAPIError("boom", status_code=500)
    )

    with pytest.raises(PipelineError):
        await pipeline.execute_scenario(_scenario(), {})

    # Initial checkpoint, after repos, then failure
    assert [c.status for c in checkpoints] == ["in_progress", "in_progress", "failed"]
    final = checkpoints[-1]
    assert final.id == "sess-1"
    repos = {r.id: r for r in final.repositories}
    assert set(repos) == {"acme/new-repo", "acme/old-repo"}
    assert repos["acme/old-repo"].existed is True
    assert repos["acme/new-repo"].existed is False
    assert repos["acme/new-repo"].owner == "acme"


@pytest.mark.asyncio
async def test_preexisting_component_is_marked_existed():
    checkpoints: list[Instance] = []
    pipeline = _pipeline(checkpoints)
    pipeline.repo_manager.create_repositories = _fake_repos(pipeline)  # type: ignore[method-assign]

    async def create_components(_repos, _created):
        rm = pipeline.resource_manager
        rm.created_components["new-repo"] = {"id": "comp-new"}
        rm.created_components["old-repo"] = {"id": "comp-old"}
        rm.preexisting_components.add("old-repo")
        return rm.created_components

    pipeline.resource_manager.create_components = create_components  # type: ignore[method-assign]
    pipeline.resource_manager.create_applications = AsyncMock(return_value={})  # type: ignore[method-assign]

    summary = await pipeline.execute_scenario(_scenario(), {})

    instance: Instance = summary["instance"]
    assert instance.status == "complete"
    comps = {c.id: c.existed for c in instance.components}
    assert comps == {"comp-new": False, "comp-old": True}


@pytest.mark.asyncio
async def test_checkpoint_errors_do_not_break_the_run():
    def broken_save(_instance: Instance) -> None:
        raise OSError("disk full")

    pipeline = _pipeline([])
    pipeline.on_checkpoint = broken_save
    pipeline.repo_manager.create_repositories = _fake_repos(pipeline)  # type: ignore[method-assign]
    pipeline.resource_manager.create_components = AsyncMock(return_value={})  # type: ignore[method-assign]
    pipeline.resource_manager.create_applications = AsyncMock(return_value={})  # type: ignore[method-assign]

    summary = await pipeline.execute_scenario(_scenario(), {})
    assert summary["success"] is True


@pytest.mark.parametrize(
    ("total", "reused", "expected"),
    [
        (2, 0, "Created 2 components"),
        (1, 0, "Created 1 component"),
        (1, 1, "Reused 1 existing component"),
        (3, 3, "Reused 3 existing components"),
        (3, 1, "Created 2 components, reused 1 existing"),
        (0, 0, "Created 0 components"),
    ],
)
def test_outcome_message_separates_created_from_reused(total, reused, expected):
    assert (
        CreationPipeline._outcome_message(total, reused, "component", "components")
        == expected
    )


@pytest.mark.parametrize(
    ("total", "reused", "expected"),
    [(1, 1, True), (3, 3, True), (3, 1, False), (2, 0, False), (0, 0, False)],
)
def test_outcome_event_flags_steps_that_only_reused(total, reused, expected):
    event = CreationPipeline._outcome_event(total, reused, "repository", "repositories")
    assert event["all_preexisting"] is expected
    assert event["message"] == CreationPipeline._outcome_message(
        total, reused, "repository", "repositories"
    )


def test_flag_config_event_reports_reused_flags_as_preexisting():
    pipeline = _pipeline([])
    rm = pipeline.resource_manager
    rm.created_flags["default.score"] = {"id": "f1"}
    rm.preexisting_flags.add("default.score")
    rm.flag_environment_updates = 1

    event = pipeline._flag_config_event()

    assert event["all_preexisting"] is True
    assert event["message"] == (
        "Reused 1 existing flag; applied 1 environment setting (flag set off)"
    )


def test_planned_flags_message_does_not_claim_creation():
    pipeline = _pipeline([])
    pipeline.resource_manager.flag_definitions["a"] = object()
    assert pipeline._planned_flags_message().startswith("Planned 1 flag")


def test_defined_flags_event_marks_preexisting_after_configuration():
    pipeline = _pipeline([])
    rm = pipeline.resource_manager
    rm.flag_definitions["default.score"] = object()
    rm.created_flags["default.score"] = {"id": "f1"}
    rm.preexisting_flags.add("default.score")

    event = pipeline._defined_flags_event()

    assert event["all_preexisting"] is True
    assert event["message"] == "Planned 1 flag: reused 1 existing flag"


def test_flag_config_event_reports_settings_left_unchanged():
    pipeline = _pipeline([])
    rm = pipeline.resource_manager
    rm.created_flags["default.score"] = {"id": "f1"}
    rm.preexisting_flags.add("default.score")
    rm.flag_environment_preserved = 1

    assert pipeline._flag_config_event()["message"] == (
        "Reused 1 existing flag; left 1 existing environment setting unchanged"
    )
