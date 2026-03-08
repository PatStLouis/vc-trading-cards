"""Pytest fixtures and config. Patches DB so tests don't require Postgres."""
import os
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

# Ensure tests see the API root (GET / returns JSON), not the SPA frontend
os.environ.pop("FRONTEND_BUILD_DIR", None)


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
            "wallet_key": None,
            "tenant_token": None,
            "discord_username": "testuser",
        }

    async def fake_get_tenant_by_user_id(user_id: str):
        return {
            "wallet_id": "test-wallet-id",
            "wallet_key": None,
            "tenant_token": None,
            "discord_username": "testuser",
        }

    async def fake_ensure_user_exists(user_id: str):
        pass

    async def fake_list_admin_issued_for_user(user_id: str):
        return []

    async def fake_webauthn_list_credentials_for_user(user_id: str):
        return []

    async def fake_get_user_accounts(user_id: str):
        """Return minimal accounts so /api/me has username etc."""
        return [{"provider": "discord", "provider_user_id": "discord-123", "provider_username": "testuser", "provider_avatar": None}]

    async def fake_get_user_poser_username(user_id: str):
        return "testuser"

    async def fake_get_user_created_at(user_id: str):
        return "2025-01-01T00:00:00Z"

    async def fake_get_user_created_at_raw(user_id: str):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)

    with (
        patch("app.db.init_db", fake_init_db),
        patch("app.db.close_db", fake_close_db),
        patch("app.db.get_tenant_by_discord_sub", fake_get_tenant),
        patch("app.db.get_tenant_by_user_id", fake_get_tenant_by_user_id),
        patch("app.db.ensure_user_exists", fake_ensure_user_exists),
        patch("app.db.list_admin_issued_for_user", fake_list_admin_issued_for_user),
        patch("app.db.webauthn_list_credentials_for_user", fake_webauthn_list_credentials_for_user),
        patch("app.db.get_user_accounts", fake_get_user_accounts),
        patch("app.db.get_user_poser_username", fake_get_user_poser_username),
        patch("app.db.get_user_created_at", fake_get_user_created_at),
        patch("app.db.get_user_created_at_raw", fake_get_user_created_at_raw),
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
        "user_id": "test-wallet-id",  # same as wallet_id in fake_get_tenant for tenant lookup
        "username": "testuser",
        "wallet_id": "test-wallet-id",
    })
