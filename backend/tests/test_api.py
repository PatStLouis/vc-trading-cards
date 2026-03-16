"""API route tests. Run with: uv run pytest tests/ -v"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from config import get_settings


def _session_cookie_name():
    return get_settings().session_cookie_name


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "Brutality Cards API"
    assert "docs" in data


@pytest.mark.asyncio
async def test_api_me_requires_auth(client: AsyncClient):
    r = await client.get("/api/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_api_me_with_valid_session(client: AsyncClient, valid_session_cookie: str):
    r = await client.get(
        "/api/me",
        cookies={_session_cookie_name(): valid_session_cookie},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["sub"] == "discord-123"
    assert data["username"] == "testuser"
    assert data["wallet_id"] == "test-wallet-id"


@pytest.mark.asyncio
async def test_wallet_cards_requires_auth(client: AsyncClient):
    r = await client.get("/api/wallet/cards")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wallet_cards_with_session_returns_cards(
    client: AsyncClient, valid_session_cookie: str
):
    r = await client.get(
        "/api/wallet/cards",
        cookies={_session_cookie_name(): valid_session_cookie},
    )
    assert r.status_code == 200
    data = r.json()
    assert "cards" in data
    assert isinstance(data["cards"], list)


@pytest.mark.asyncio
async def test_wallet_cards_normalizes_credential_subject(
    client: AsyncClient, valid_session_cookie: str
):
    """When ACA-Py returns a credential with credentialSubject, response has card shape."""
    from app.wallet import routes as wallet_routes

    async def fake_list(_token):
        return [{
            "credential_id": "cred-1",
            "credential": {
                "credentialSubject": {
                    "name": "Test Card",
                    "rarity": "Rare Holo",
                    "set": "base",
                    "number": "42",
                    "artwork": "https://example.com/img.png",
                }
            },
        }]

    with (
        patch.object(wallet_routes, "list_credentials", fake_list),
        patch(
            "app.db.get_tenant_by_discord_sub",
            AsyncMock(
                return_value={
                    "wallet_id": "test-wallet-id",
                    "wallet_key": None,
                    "tenant_token": "fake-token",
                    "discord_username": "testuser",
                }
            ),
        ),
    ):
        r = await client.get(
            "/api/wallet/cards",
            cookies={_session_cookie_name(): valid_session_cookie},
        )
    assert r.status_code == 200
    data = r.json()
    assert len(data["cards"]) == 1
    card = data["cards"][0]
    assert card["name"] == "Test Card"
    assert card["rarity"] == "rare holo"
    assert card["set"] == "base"
    assert card["number"] == "42"
    assert card["image_url"] == "https://example.com/img.png"
