"""Tests for flag configuration on re-runs (don't reset existing settings)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mimic.pipeline.resource_manager import ResourceManager


def _manager(flag_exists: bool, env_existed: bool) -> tuple[ResourceManager, MagicMock]:
    rm = ResourceManager("org-1", "ep-1", "https://api.example.invalid", "pat")
    rm.created_applications = {"app": {"id": "app-1"}}
    rm.created_environments = {"prod": {"id": "env-1"}}
    if env_existed:
        rm.preexisting_environments.add("prod")
    rm.flag_definitions = {"default.score": object()}

    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    existing = [{"id": "flag-1", "name": "default.score"}] if flag_exists else []
    client.list_flags.return_value = {"flags": existing}
    client.create_boolean_flag.return_value = {"flag": {"id": "flag-new"}}
    return rm, client


SCENARIO = SimpleNamespace(
    environments=[SimpleNamespace(name="prod", flags=["default.score"])]
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flag_exists", "env_existed", "should_set"),
    [
        (True, True, False),  # re-run: leave the SE's current setting alone
        (True, False, True),  # existing flag, brand-new environment
        (False, True, True),  # new flag
        (False, False, True),  # fresh run
    ],
)
async def test_existing_flag_setting_is_not_reset_on_rerun(
    flag_exists, env_existed, should_set
):
    rm, client = _manager(flag_exists, env_existed)
    with patch("mimic.pipeline.resource_manager.UnifyAPIClient", return_value=client):
        await rm.configure_flags_in_environments(SCENARIO)

    assert client.enable_flag_in_environment.called is should_set
    assert rm.flag_environment_updates == (1 if should_set else 0)
    assert rm.flag_environment_preserved == (0 if should_set else 1)
