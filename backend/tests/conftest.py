"""Pytest fixtures and config. Patches DB so tests don't require Postgres."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def patch_db():
    """Avoid real Postgres: no-op init/close, and fake tenant lookup."""
    async def fake_init_db():
        pass

    async def fake_close_db():
        pass

    async def fake_get_tenant(discord_sub: str):
        return {
            "wallet_id": "test-wallet-id",
            "tenant_token": None,
            "discord_username": "testuser",
        }

    with (
        patch("app.db.init_db", fake_init_db),
        patch("app.db.close_db", fake_close_db),
        patch("app.db.get_tenant_by_discord_sub", fake_get_tenant),
    ):
        yield


@pytest.fixture
def app(patch_db):
    from main import app
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_session_cookie():
    """Create a valid session cookie for tests (uses real encode_session)."""
    from app.auth.session import encode_session
    return encode_session({
        "sub": "discord-123",
        "username": "testuser",
        "wallet_id": "test-wallet-id",
    })
