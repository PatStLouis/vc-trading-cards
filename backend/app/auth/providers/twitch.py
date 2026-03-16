"""Twitch OAuth2: authorize URL, exchange code for tokens, fetch user."""
import httpx
from urllib.parse import urlencode
from config import get_settings

_settings = get_settings()


def get_authorize_url(state: str, redirect_uri: str) -> str:
    """Minimal scope: no email, no openid. Helix /users still returns id, login, display_name with the token."""
    params = {
        "client_id": _settings.twitch_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    return f"https://id.twitch.tv/oauth2/authorize?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": _settings.twitch_client_id,
                "client_secret": _settings.twitch_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            return None
        return r.json()


async def get_twitch_user(access_token: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Client-Id": _settings.twitch_client_id,
            },
        )
        if r.status_code != 200:
            return None
        data = r.json()
        users = data.get("data", [])
        return users[0] if users else None
