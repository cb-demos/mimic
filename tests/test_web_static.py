"""Tests for serving the built web UI (caching and path safety)."""

import pytest
from fastapi.testclient import TestClient

from mimic.web import server

pytestmark = pytest.mark.skipif(
    not (server.STATIC_DIR / "index.html").exists(),
    reason="Web UI not built (run `make build-ui`)",
)

# No `with` block: the lifespan (which touches ~/.mimic) is not run.
client = TestClient(server.app)


def test_index_html_is_revalidated_by_browsers():
    """Without no-cache, browsers keep running the old UI after an upgrade."""
    for path in ["/", "/cleanup", "/scenarios/some-id/run"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-cache"
        assert "<html" in response.text.lower()


def test_spa_route_does_not_serve_files_outside_static_dir():
    # STATIC_DIR is src/mimic/web/static, so four levels up is the repo root
    for path in [
        "/..%2f..%2f..%2f..%2fpyproject.toml",
        "/%2e%2e/%2e%2e/%2e%2e/%2e%2e/pyproject.toml",
    ]:
        response = client.get(path)
        assert "[project]" not in response.text
