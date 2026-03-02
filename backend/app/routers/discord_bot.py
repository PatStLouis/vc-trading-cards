"""Discord Bot: slash commands via Interactions API (POST /discord/interactions)."""
import json
from fastapi import APIRouter, Request, HTTPException, Response

from config import get_settings
from app.db import get_tenant_by_discord_sub
from app.services.acapy import list_credentials

router = APIRouter(tags=["Discord Bot"], prefix="/discord")
# Interaction type and response type constants (Discord API)
INTERACTION_TYPE_PING = 1
INTERACTION_TYPE_APPLICATION_COMMAND = 2
INTERACTION_RESPONSE_TYPE_PONG = 1
INTERACTION_RESPONSE_TYPE_CHANNEL_MESSAGE = 4
INTERACTION_RESPONSE_FLAG_EPHEMERAL = 64  # Only visible to the user


def _verify_signature(body: bytes, signature: str, timestamp: str, public_key: str) -> bool:
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


@router.post("/interactions")
async def discord_interactions(request: Request):
    """
    Discord Interactions endpoint. Set this URL as "Interactions Endpoint URL" in the Discord Developer Portal.
    Requires DISCORD_PUBLIC_KEY and optional DISCORD_BOT_TOKEN. Handles PING and slash commands.
    """
    settings = get_settings()
    if not settings.discord_public_key:
        raise HTTPException(status_code=501, detail="Discord bot not configured (DISCORD_PUBLIC_KEY)")

    signature = request.headers.get("x-signature-ed25519") or ""
    timestamp = request.headers.get("x-signature-timestamp") or ""
    body = await request.body()

    if not _verify_signature(body, signature, timestamp, settings.discord_public_key):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    data = json.loads(body)
    interaction_type = data.get("type")

    if interaction_type == INTERACTION_TYPE_PING:
        return Response(
            content=json.dumps({"type": INTERACTION_RESPONSE_TYPE_PONG}),
            media_type="application/json",
        )

    if interaction_type != INTERACTION_TYPE_APPLICATION_COMMAND:
        return Response(
            content=json.dumps({"type": INTERACTION_RESPONSE_TYPE_PONG}),
            media_type="application/json",
        )

    # Slash command
    command_name = (data.get("data") or {}).get("name")
    # Resolve user id (member in guild, or user in DM)
    user_id = None
    if "member" in data and data["member"]:
        user_id = (data["member"].get("user") or {}).get("id")
    if not user_id:
        user_id = (data.get("user") or {}).get("id")
    user_id = str(user_id) if user_id else None

    if command_name == "wallet":
        return await _response_wallet(settings, user_id)
    if command_name == "collection":
        return await _response_collection(settings, user_id)

    return _response_message("Unknown command.", ephemeral=True)


def _response_message(content: str, ephemeral: bool = False) -> Response:
    payload = {
        "type": INTERACTION_RESPONSE_TYPE_CHANNEL_MESSAGE,
        "data": {
            "content": content[:2000],
            "flags": INTERACTION_RESPONSE_FLAG_EPHEMERAL if ephemeral else 0,
        },
    }
    return Response(content=json.dumps(payload), media_type="application/json")


async def _response_wallet(settings, user_id: str | None) -> Response:
    """Handle /wallet: link to app and optional card count."""
    url = settings.frontend_url.rstrip("/") + "/wallet"
    if not user_id:
        return _response_message(
            f"**Tritone Cards** — The Devil's Interval Collectible Cards\n\nOpen your deck: {url}\nLog in with Discord to see your cards.",
            ephemeral=True,
        )
    tenant = await get_tenant_by_discord_sub(user_id)
    if not tenant:
        return _response_message(
            f"**Tritone Cards** — The Devil's Interval Collectible Cards\n\nYou don’t have a deck yet. Log in once to create it:\n{url}",
            ephemeral=True,
        )
    # Optional: fetch card count (requires tenant token)
    count = 0
    if tenant.get("tenant_token"):
        creds = await list_credentials(tenant["tenant_token"])
        count = len(creds) if isinstance(creds, list) else 0
    if count:
        return _response_message(
            f"**Tritone Cards** · My deck\n\nYou have **{count}** card(s). Open your deck: {url}",
            ephemeral=True,
        )
    return _response_message(
        f"**Tritone Cards** · My deck\n\nOpen your deck: {url}",
        ephemeral=True,
    )


async def _response_collection(settings, user_id: str | None) -> Response:
    """Handle /collection: same as wallet."""
    return await _response_wallet(settings, user_id)
