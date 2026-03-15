"""Wallet/collection API: list credentials (trading cards) for the current user's tenant."""
import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from app.dependencies import get_current_user, get_tenant_token_for_request
from app.schemas import (
    RESPONSE_ME,
    RESPONSE_WALLET_CARDS,
    RESPONSE_SYNC,
    response_example,
)
from app.services.acapy import list_credentials
from app.db import (
    sync_user_collection,
    list_admin_issued_for_user,
    webauthn_list_credentials_for_user,
    webauthn_remove_credential,
    get_admin_issued_card_ids,
    get_user_accounts,
    get_user_poser_username,
    set_poser_username,
    get_user_created_at,
    get_user_created_at_raw,
    update_discord_profile_for_user,
)

router = APIRouter(tags=["Wallet"], prefix="/api")


def _discord_avatar_url(provider_user_id: str, avatar_hash: str | None, size: int = 128) -> str | None:
    """Build Discord CDN avatar URL from provider_user_id and avatar hash. Returns None if no hash."""
    if not avatar_hash or not provider_user_id:
        return None
    ext = "gif" if avatar_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{provider_user_id}/{avatar_hash}.{ext}?size={size}"


class UpdateProfileBody(BaseModel):
    poser_username: str | None = None


@router.get("/me", responses={200: response_example(RESPONSE_ME)})
async def me(user: dict = Depends(get_current_user)):
    """Return current user info from session. Includes is_admin, has_passkey, linked_accounts, poser_username, created_at as first_login_at, is_first_login."""
    from app.dependencies import is_admin
    creds = await webauthn_list_credentials_for_user(user["user_id"])
    accounts = await get_user_accounts(user["user_id"])
    poser = await get_user_poser_username(user["user_id"])
    created_at = await get_user_created_at(user["user_id"])
    created_at_raw = await get_user_created_at_raw(user["user_id"])
    now = datetime.now(timezone.utc)
    is_first_login = (
        created_at_raw is not None
        and (now - created_at_raw).total_seconds() < 120
    )
    passkeys = [
        {
            "id": base64.urlsafe_b64encode(c["credential_id"]).decode("ascii").rstrip("="),
            "created_at": c["created_at"],
            "credential_device_type": c.get("credential_device_type"),
            "credential_backed_up": c.get("credential_backed_up"),
            "attestation_format": c.get("attestation_format"),
            "aaguid": c.get("aaguid"),
            "registered_name": c.get("registered_name"),
        }
        for c in creds
    ]
    discord_account = next((a for a in accounts if a.get("provider") == "discord"), None)
    avatar_url = _discord_avatar_url(
        discord_account["provider_user_id"], discord_account.get("provider_avatar")
    ) if discord_account else None
    return {
        "user_id": user.get("user_id"),
        "sub": user.get("sub"),
        "provider": user.get("provider"),
        "username": user.get("username"),
        "wallet_id": user.get("wallet_id"),
        "poser_username": poser,
        "avatar_url": avatar_url,
        "is_admin": await is_admin(user),
        "has_passkey": len(creds) > 0,
        "passkey_count": len(creds),
        "passkeys": passkeys,
        "accounts": accounts,
        "first_login_at": created_at,
        "is_first_login": is_first_login,
    }


@router.patch("/me", responses={200: response_example(RESPONSE_ME)})
async def update_me(
    user: dict = Depends(get_current_user),
    body: UpdateProfileBody | None = Body(default=None),
):
    """Update current user profile. Only poser_username is updatable."""
    if body is not None and body.poser_username is not None:
        new_poser = await set_poser_username(user["user_id"], body.poser_username)
        if new_poser is None and (body.poser_username or "").strip():
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="poser_username is taken or invalid. Use 2–64 alphanumeric characters or underscores.",
            )
    creds = await webauthn_list_credentials_for_user(user["user_id"])
    accounts = await get_user_accounts(user["user_id"])
    poser = await get_user_poser_username(user["user_id"])
    created_at = await get_user_created_at(user["user_id"])
    created_at_raw = await get_user_created_at_raw(user["user_id"])
    now = datetime.now(timezone.utc)
    is_first_login = (
        created_at_raw is not None
        and (now - created_at_raw).total_seconds() < 120
    )
    passkeys = [
        {
            "id": base64.urlsafe_b64encode(c["credential_id"]).decode("ascii").rstrip("="),
            "created_at": c["created_at"],
            "credential_device_type": c.get("credential_device_type"),
            "credential_backed_up": c.get("credential_backed_up"),
            "attestation_format": c.get("attestation_format"),
            "aaguid": c.get("aaguid"),
            "registered_name": c.get("registered_name"),
        }
        for c in creds
    ]
    from app.dependencies import is_admin
    discord_account = next((a for a in accounts if a.get("provider") == "discord"), None)
    avatar_url = _discord_avatar_url(
        discord_account["provider_user_id"], discord_account.get("provider_avatar")
    ) if discord_account else None
    return {
        "user_id": user.get("user_id"),
        "sub": user.get("sub"),
        "provider": user.get("provider"),
        "username": user.get("username"),
        "wallet_id": user.get("wallet_id"),
        "poser_username": poser,
        "avatar_url": avatar_url,
        "is_admin": await is_admin(user),
        "has_passkey": len(creds) > 0,
        "passkey_count": len(creds),
        "passkeys": passkeys,
        "accounts": accounts,
        "first_login_at": created_at,
        "is_first_login": is_first_login,
    }


@router.post("/me/refresh-discord", responses={200: response_example(RESPONSE_ME)})
async def refresh_discord_profile(user: dict = Depends(get_current_user)):
    """Refresh Discord username, avatar, and discriminator from Discord API (bot). No re-login required."""
    from fastapi import HTTPException
    from config import get_settings
    from app.services.discord import get_user_by_id
    accounts = await get_user_accounts(user["user_id"])
    discord_account = next((a for a in accounts if a.get("provider") == "discord"), None)
    if not discord_account:
        raise HTTPException(status_code=400, detail="No Discord account linked")
    bot_token = (get_settings().discord_bot_token or "").strip()
    if not bot_token:
        raise HTTPException(status_code=503, detail="Discord refresh not configured")
    discord_user = await get_user_by_id(bot_token, discord_account["provider_user_id"])
    if not discord_user:
        raise HTTPException(status_code=502, detail="Could not fetch profile from Discord")
    username = (discord_user.get("username") or "").strip() or discord_account.get("provider_username") or ""
    avatar = discord_user.get("avatar")
    discriminator = discord_user.get("discriminator")
    if discriminator is not None:
        discriminator = str(discriminator).strip()
    updated = await update_discord_profile_for_user(user["user_id"], username, avatar, discriminator)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return await me(user=user)


def _decode_passkey_id(credential_id_b64: str) -> bytes | None:
    """Decode base64url passkey id to bytes. Returns None if invalid."""
    try:
        pad = 4 - len(credential_id_b64) % 4
        if pad != 4:
            credential_id_b64 += "=" * pad
        return base64.urlsafe_b64decode(credential_id_b64)
    except Exception:
        return None


@router.delete("/me/passkeys/{credential_id_b64}")
async def remove_passkey(
    credential_id_b64: str,
    user: dict = Depends(get_current_user),
):
    """Remove a passkey for the current user. credential_id_b64 is the passkey id from GET /api/me."""
    from fastapi import HTTPException
    credential_id = _decode_passkey_id(credential_id_b64)
    if not credential_id:
        raise HTTPException(status_code=400, detail="Invalid passkey id")
    removed = await webauthn_remove_credential(user["user_id"], credential_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Passkey not found")
    return {"removed": True}


@router.get("/wallet/cards", responses={200: response_example(RESPONSE_WALLET_CARDS)})
async def wallet_cards(
    user: dict = Depends(get_current_user),
    tenant_token: str | None = Depends(get_tenant_token_for_request),
):
    """List the current user's cards (wallet credentials + admin-issued). Returns card-like shape for frontend."""
    raw = await list_credentials(tenant_token)
    # Agent returns W3C credentials: each item may be { credential_id, credential: { ... } } or raw W3C { credentialSubject, ... }
    cards = []
    for rec in raw:
        cred = rec.get("credential") if isinstance(rec.get("credential"), dict) else rec
        subject = (cred or rec).get("credentialSubject", {})
        if isinstance(subject, dict) and subject:
            cards.append({
                "id": rec.get("credential_id") or (cred or {}).get("id") or "",
                "name": subject.get("name", "Unknown"),
                "rarity": (subject.get("rarity") or "common").lower().replace(" ", " "),
                "set": subject.get("set", ""),
                "number": subject.get("number", ""),
                "quote": subject.get("quote", ""),
                "artwork": subject.get("artwork", ""),
                "types": subject.get("type", ["TradingCard"]),
                "subtypes": subject.get("subtypes", "trading-cards"),
                "supertype": subject.get("supertype", "trading-card"),
                "image_url": subject.get("artwork") or subject.get("image") or "",
            })
        elif rec.get("credential_id"):
            cards.append({
                "id": rec["credential_id"],
                "name": "Credential",
                "rarity": "common",
                "set": "",
                "number": "",
                "quote": "",
                "artwork": "",
                "types": ["TradingCard"],
                "subtypes": "trading-cards",
                "supertype": "trading-card",
                "image_url": "",
            })
        else:
            # W3C cred with no credential_id wrapper; use cred id if present
            c = rec.get("credential") if isinstance(rec.get("credential"), dict) else rec
            if isinstance(c, dict) and c.get("credentialSubject") is not None:
                cards.append({
                    "id": rec.get("credential_id") or c.get("id") or "",
                    "name": (c.get("credentialSubject") or {}).get("name", "Credential") if isinstance(c.get("credentialSubject"), dict) else "Credential",
                    "rarity": "common",
                    "set": "",
                    "number": "",
                    "quote": "",
                    "artwork": "",
                    "types": ["TradingCard"],
                    "subtypes": "trading-cards",
                    "supertype": "trading-card",
                "image_url": "",
            })
    # Merge admin-issued cards (issued by admin to this user) so they appear in the wallet
    issued = await list_admin_issued_for_user(user["user_id"])
    for card in issued:
        cards.append(card)
    return {"cards": cards}


@router.post("/wallet/cards/sync", responses={200: response_example(RESPONSE_SYNC)})
async def sync_wallet_cards(_user: dict = Depends(get_current_user)):
    """Rebuild the current user's public collection from the ledger (issued cards). Collection is also updated automatically when cards are issued."""
    card_ids = await get_admin_issued_card_ids(_user["user_id"])
    pairs = [(card_id, "") for card_id in card_ids]
    await sync_user_collection(_user["user_id"], pairs)
    return {"synced": len(pairs), "message": "Collection refreshed from ledger. You appear in Explore."}
