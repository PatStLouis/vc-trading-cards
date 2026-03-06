"""Wallet/collection API: list credentials (trading cards) for the current user's tenant."""
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, get_tenant_token_for_request
from app.services.acapy import list_credentials
from app.db import (
    get_card_id_by_set_and_name,
    sync_user_collection,
    list_admin_issued_for_user,
    webauthn_list_credentials_for_user,
    get_admin_issued_card_ids,
)

router = APIRouter(tags=["Wallet"], prefix="/api")


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return current user info from session. Includes is_admin and has_passkey."""
    from app.dependencies import is_admin
    creds = await webauthn_list_credentials_for_user(user["sub"])
    return {
        "sub": user.get("sub"),
        "username": user.get("username"),
        "wallet_id": user.get("wallet_id"),
        "is_admin": is_admin(user),
        "has_passkey": len(creds) > 0,
        "passkey_count": len(creds),
    }


@router.get("/wallet/credentials")
async def wallet_credentials(
    user: dict = Depends(get_current_user),
    tenant_token: str | None = Depends(get_tenant_token_for_request),
):
    """List W3C credentials in the user's ACA-Py wallet (POST agent /credentials/w3c). Normalize to card-like shape for frontend. Also includes admin-issued cards."""
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
    issued = await list_admin_issued_for_user(user["sub"])
    for card in issued:
        cards.append(card)
    return {"cards": cards}


@router.post("/me/collection/sync")
async def sync_my_collection(
    _user: dict = Depends(get_current_user),
    tenant_token: str | None = Depends(get_tenant_token_for_request),
):
    """Sync the current user's wallet credentials and admin-issued cards to the public collection (so they appear in search / who-has-which-card)."""
    raw = await list_credentials(tenant_token)
    pairs = []
    seen_card_ids = set()
    for rec in raw:
        cred = rec.get("credential") if isinstance(rec.get("credential"), dict) else rec
        subject = (cred or rec).get("credentialSubject", {}) if isinstance(cred or rec, dict) else {}
        if not isinstance(subject, dict):
            continue
        set_name = (subject.get("set") or "").strip()
        card_name = (subject.get("name") or "Unknown").strip()
        cred_id = rec.get("credential_id") or (cred or {}).get("id") or ""
        card_id = await get_card_id_by_set_and_name(set_name, card_name)
        if card_id and card_id not in seen_card_ids:
            pairs.append((card_id, cred_id))
            seen_card_ids.add(card_id)
    # Include admin-issued cards so they appear in Explore even when user has no ACA-Py credentials
    for card_id in await get_admin_issued_card_ids(_user["sub"]):
        if card_id not in seen_card_ids:
            pairs.append((card_id, ""))
            seen_card_ids.add(card_id)
    await sync_user_collection(_user["sub"], pairs)
    return {"synced": len(pairs), "message": "Collection synced. You will appear in search and card owners."}
