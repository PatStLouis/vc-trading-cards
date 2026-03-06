"""Public API: catalog (sets, cards), user search, and who-has-which-card. No auth required."""
from fastapi import APIRouter, HTTPException

from app.db import (
    list_card_sets,
    get_card_set,
    list_cards,
    get_card,
    list_owners_for_card,
    list_collection_for_user,
    search_users,
    get_user_public,
)

router = APIRouter(tags=["Public"], prefix="/api/public")


@router.get("/sets")
async def public_list_sets():
    """List all card sets. Public."""
    sets = await list_card_sets()
    return {"sets": sets}


@router.get("/sets/{set_id}")
async def public_get_set(set_id: str):
    """Get a single set. Public."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    return s


@router.get("/sets/{set_id}/cards")
async def public_list_cards(set_id: str):
    """List cards in a set. Public."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    cards = await list_cards(set_id)
    return {"set": s, "cards": cards}


@router.get("/cards/{card_id}")
async def public_get_card(card_id: str):
    """Get a single card. Public."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    return c


@router.get("/cards/{card_id}/owners")
async def public_card_owners(card_id: str):
    """List users who have this card (synced collection). Public."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    owners = await list_owners_for_card(card_id)
    return {"card_id": card_id, "owners": owners}


@router.get("/users")
async def public_search_users(q: str = "", limit: int = 50):
    """Search users by username. Public. Returns username, discord_sub, collection_count."""
    users = await search_users(q, limit=min(limit, 100))
    return {"users": users}


@router.get("/users/{discord_sub}")
async def public_get_user(discord_sub: str):
    """Get public user profile. Public."""
    user = await get_user_public(discord_sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{discord_sub}/collection")
async def public_user_collection(discord_sub: str):
    """List cards in a user's (synced) collection. Public."""
    user = await get_user_public(discord_sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cards = await list_collection_for_user(discord_sub)
    return {"user": user, "cards": cards}
