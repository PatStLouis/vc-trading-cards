"""Wallet/collection API: list credentials (trading cards) for the current user's tenant."""
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, get_tenant_token_for_request
from app.services.acapy import list_credentials

router = APIRouter(tags=["Wallet"], prefix="/api")


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return current user info from session. Includes is_admin when user is in ADMIN_DISCORD_IDS."""
    from app.dependencies import is_admin
    return {
        "sub": user.get("sub"),
        "username": user.get("username"),
        "wallet_id": user.get("wallet_id"),
        "is_admin": is_admin(user),
    }


@router.get("/wallet/credentials")
async def wallet_credentials(
    _user: dict = Depends(get_current_user),
    tenant_token: str | None = Depends(get_tenant_token_for_request),
):
    """List credentials in the user's ACA-Py wallet. Normalize to card-like shape for frontend."""
    raw = await list_credentials(tenant_token)
    # ACA-Py can return { results: [ { credential_id, credential: { cred } } ] } or similar
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
    return {"cards": cards}
