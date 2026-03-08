"""Discord OAuth2 / OIDC: authorize URL, exchange code for tokens, fetch user."""
import httpx
from urllib.parse import urlencode
from config import get_settings

_settings = get_settings()


def get_authorize_url(state: str, redirect_uri: str | None = None) -> str:
    redirect_uri = redirect_uri or _settings.discord_redirect_uri or _settings.oauth_redirect_uri
    params = {
        "client_id": _settings.discord_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    return f"{_settings.discord_authorize_url}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str | None = None) -> dict | None:
    redirect_uri = redirect_uri or _settings.discord_redirect_uri or _settings.oauth_redirect_uri
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _settings.discord_token_url,
            data={
                "client_id": _settings.discord_client_id,
                "client_secret": _settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            return None
        return r.json()


async def get_discord_user(access_token: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            _settings.discord_user_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code != 200:
            return None
        return r.json()
