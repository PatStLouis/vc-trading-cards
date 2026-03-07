"""HTTP routes exposed by services: Discord bot interactions webhook."""
import json
from fastapi import APIRouter, Request, HTTPException, Response

from config import get_settings
from app.services.discord import verify_interaction_signature, handle_interaction

router = APIRouter(tags=["Discord Bot"], prefix="/discord")


@router.post("/interactions")
async def discord_interactions(request: Request):
    """
    Discord Interactions endpoint. Set this URL as "Interactions Endpoint URL" in the Discord Developer Portal.
    Requires DISCORD_PUBLIC_KEY. Handles PING and slash commands (wallet, collection).
    """
    settings = get_settings()
    if not settings.discord_public_key:
        raise HTTPException(status_code=501, detail="Discord bot not configured (DISCORD_PUBLIC_KEY)")

    signature = request.headers.get("x-signature-ed25519") or ""
    timestamp = request.headers.get("x-signature-timestamp") or ""
    body = await request.body()

    if not verify_interaction_signature(body, signature, timestamp, settings.discord_public_key):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    payload = await handle_interaction(body, settings.frontend_url)
    return Response(content=json.dumps(payload), media_type="application/json")
