"""Discord API client (bot token) and Interactions (slash commands) handling."""
import json
import httpx
from config import get_settings
from app.db import get_tenant_by_discord_sub
from app.services.acapy import list_credentials

BASE_URL = "https://discord.com/api/v10"


class DiscordServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ---- Bot API (uses bot token) ----

def _bot_headers(bot_token: str) -> dict:
    if not (bot_token or "").strip():
        raise DiscordServiceError("Set DISCORD_BOT_TOKEN in the backend environment.", 400)
    return {"Authorization": f"Bot {(bot_token or '').strip()}"}


async def _request(method: str, path: str, bot_token: str, **kwargs) -> dict | list:
    url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.request(
                method, url, headers=_bot_headers(bot_token), **kwargs
            )
            r.raise_for_status()
            return r.json() if r.content else {}
    except httpx.HTTPStatusError as e:
        detail = "Discord API error."
        if e.response is not None:
            try:
                body = e.response.json()
                if isinstance(body.get("message"), str):
                    detail = body["message"]
            except Exception:
                pass
        raise DiscordServiceError(detail, 400)
    except httpx.RequestError as e:
        raise DiscordServiceError(f"Could not reach Discord: {e!s}", 502)


SLASH_COMMANDS_PAYLOAD = [
    {"name": "wallet", "description": "Open your Tritone Cards deck (The Devil's Interval Collectible Cards)", "type": 1},
    {"name": "collection", "description": "View your Tritone Cards collection", "type": 1},
]


async def register_slash_commands(application_id: str, bot_token: str) -> list[str]:
    """Register slash commands with Discord. Returns list of registered command names."""
    if not (application_id or "").strip():
        raise DiscordServiceError("Set DISCORD_CLIENT_ID and DISCORD_BOT_TOKEN in the backend environment.", 400)
    app_id = application_id.strip()
    bot_token = (bot_token or "").strip()
    if not bot_token:
        raise DiscordServiceError("Set DISCORD_CLIENT_ID and DISCORD_BOT_TOKEN in the backend environment.", 400)
    url = f"{BASE_URL}/applications/{app_id}/commands"
    registered = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for cmd in SLASH_COMMANDS_PAYLOAD:
                r = await client.post(
                    url,
                    headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"},
                    json=cmd,
                )
                r.raise_for_status()
                registered.append(r.json().get("name", cmd["name"]))
    except httpx.HTTPStatusError as e:
        detail = "Failed to register with Discord."
        if e.response is not None:
            try:
                body = e.response.json()
                if isinstance(body.get("message"), str):
                    detail = body["message"]
            except Exception:
                pass
        raise DiscordServiceError(detail, 400)
    except httpx.RequestError as e:
        raise DiscordServiceError(f"Could not reach Discord: {e!s}", 502)
    return registered


async def get_bot_guilds(bot_token: str) -> list:
    """Return list of guilds where the bot is invited."""
    data = await _request("GET", "/users/@me/guilds", bot_token, params={"limit": 200, "with_counts": "true"})
    return data if isinstance(data, list) else []


async def get_guild(bot_token: str, guild_id: str) -> dict:
    """Return a single guild's details."""
    return await _request("GET", f"/guilds/{guild_id}", bot_token, params={"with_counts": "true"})


async def get_guild_members(bot_token: str, guild_id: str, limit: int = 100, after: str | None = None) -> list:
    """Return paginated guild members."""
    params = {"limit": min(max(1, limit), 1000)}
    if after:
        params["after"] = after
    data = await _request("GET", f"/guilds/{guild_id}/members", bot_token, params=params)
    return data if isinstance(data, list) else []


async def get_user_by_id(bot_token: str, user_id: str) -> dict | None:
    """Fetch Discord user by ID using bot token. Returns user object (username, avatar, discriminator, etc.) or None on error."""
    if not (bot_token or "").strip() or not (user_id or "").strip():
        return None
    try:
        data = await _request("GET", f"/users/{user_id.strip()}", bot_token)
        return data if isinstance(data, dict) and data.get("id") else None
    except DiscordServiceError:
        return None


# ---- Interactions (webhook: verify + handle) ----

INTERACTION_TYPE_PING = 1
INTERACTION_TYPE_APPLICATION_COMMAND = 2
INTERACTION_RESPONSE_TYPE_PONG = 1
INTERACTION_RESPONSE_TYPE_CHANNEL_MESSAGE = 4
INTERACTION_RESPONSE_FLAG_EPHEMERAL = 64


def verify_interaction_signature(body: bytes, signature: str, timestamp: str, public_key: str) -> bool:
    try:
        from discord_interactions import verify_key
        return verify_key(
            body.decode("utf-8") if isinstance(body, bytes) else body,
            signature,
            timestamp,
            public_key,
        )
    except Exception:
        return False


async def handle_interaction(body: bytes, frontend_url: str) -> dict:
    """
    Parse interaction payload and return response payload (JSON-serializable dict).
    Handles PING and application commands (wallet, collection).
    """
    data = json.loads(body)
    interaction_type = data.get("type")

    if interaction_type == INTERACTION_TYPE_PING:
        return {"type": INTERACTION_RESPONSE_TYPE_PONG}

    if interaction_type != INTERACTION_TYPE_APPLICATION_COMMAND:
        return {"type": INTERACTION_RESPONSE_TYPE_PONG}

    command_name = (data.get("data") or {}).get("name")
    user_id = None
    if "member" in data and data["member"]:
        user_id = (data["member"].get("user") or {}).get("id")
    if not user_id:
        user_id = (data.get("user") or {}).get("id")
    user_id = str(user_id) if user_id else None

    if command_name == "wallet":
        return await _build_response_wallet(user_id, frontend_url)
    if command_name == "collection":
        return await _build_response_wallet(user_id, frontend_url)

    return _build_message_response("Unknown command.", ephemeral=True)


def _build_message_response(content: str, ephemeral: bool = False) -> dict:
    return {
        "type": INTERACTION_RESPONSE_TYPE_CHANNEL_MESSAGE,
        "data": {
            "content": content[:2000],
            "flags": INTERACTION_RESPONSE_FLAG_EPHEMERAL if ephemeral else 0,
        },
    }


async def _build_response_wallet(user_id: str | None, frontend_url: str) -> dict:
    url = frontend_url.rstrip("/") + "/wallet"
    if not user_id:
        return _build_message_response(
            f"**Tritone Cards** — The Devil's Interval Collectible Cards\n\nOpen your deck: {url}\nLog in with Discord to see your cards.",
            ephemeral=True,
        )
    tenant = await get_tenant_by_discord_sub(user_id)
    if not tenant:
        return _build_message_response(
            f"**Tritone Cards** — The Devil's Interval Collectible Cards\n\nYou don't have a deck yet. Log in once to create it:\n{url}",
            ephemeral=True,
        )
    count = 0
    if tenant.get("tenant_token"):
        creds = await list_credentials(tenant["tenant_token"])
        count = len(creds) if isinstance(creds, list) else 0
    if count:
        return _build_message_response(
            f"**Tritone Cards** · My deck\n\nYou have **{count}** card(s). Open your deck: {url}",
            ephemeral=True,
        )
    return _build_message_response(
        f"**Tritone Cards** · My deck\n\nOpen your deck: {url}",
        ephemeral=True,
    )
