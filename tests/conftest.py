import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def async_client():
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
