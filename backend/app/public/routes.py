"""Public API: catalog (sets, cards), user search, and who-has-which-card. No auth required."""
from fastapi import APIRouter, HTTPException
from app.schemas import (
    RESPONSE_SETS,
    RESPONSE_SET,
    RESPONSE_CARDS,
    RESPONSE_CARD,
    RESPONSE_PUBLIC_OWNERS,
    RESPONSE_PUBLIC_USERS,
    RESPONSE_PUBLIC_USER,
    RESPONSE_PUBLIC_USER_COLLECTION,
    response_example,
)
from app.db import (
    list_card_sets,
    get_card_set,
    list_cards,
    get_card,
    list_owners_for_card,
    list_collection_for_user,
    list_ledger,
    search_users,
    get_user_public,
)

router = APIRouter(prefix="/api/public")  # per-route tags for Swagger sections


@router.get("/sets", responses={200: response_example(RESPONSE_SETS)}, summary="List sets", tags=["Public · Sets"])
async def public_list_sets():
    """List sets."""
    sets = await list_card_sets()
    return {"sets": sets}


@router.get("/sets/{set_id}", responses={200: response_example(RESPONSE_SET)}, summary="Get set", tags=["Public · Sets"])
async def public_get_set(set_id: str):
    """Get set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    return s


@router.get("/sets/{set_id}/cards", responses={200: response_example({"set": RESPONSE_SET, "cards": RESPONSE_CARDS["cards"]})}, summary="List cards in set", tags=["Public · Sets"])
async def public_list_cards(set_id: str):
    """List cards in set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    cards = await list_cards(set_id)
    return {"set": s, "cards": cards}


@router.get("/cards/{card_id}", responses={200: response_example(RESPONSE_CARD)}, summary="Get card", tags=["Public · Cards"])
async def public_get_card(card_id: str):
    """Get card."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    return c


@router.get("/cards/{card_id}/owners", responses={200: response_example(RESPONSE_PUBLIC_OWNERS)}, summary="List card owners", tags=["Public · Cards"])
async def public_card_owners(card_id: str):
    """List users who have this card (synced collection)."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    owners = await list_owners_for_card(card_id)
    return {"card_id": card_id, "owners": owners}


@router.get("/users", responses={200: response_example(RESPONSE_PUBLIC_USERS)}, summary="Search users", tags=["Public · Users"])
async def public_search_users(q: str = "", limit: int = 50):
    """Search users by username."""
    users = await search_users(q, limit=min(limit, 100))
    return {"users": users}


@router.get("/users/{identifier}", responses={200: response_example(RESPONSE_PUBLIC_USER)}, summary="Get user", tags=["Public · Users"])
async def public_get_user(identifier: str):
    """Get user profile. identifier can be user_id or discord_sub."""
    user = await get_user_public(identifier)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{identifier}/collection", responses={200: response_example(RESPONSE_PUBLIC_USER_COLLECTION)}, summary="List user collection", tags=["Public · Users"])
async def public_user_collection(identifier: str):
    """List cards in user's synced collection. identifier can be user_id or discord_sub."""
    user = await get_user_public(identifier)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cards = await list_collection_for_user(user["user_id"])
    return {"user": user, "cards": cards}


@router.get("/ledger", summary="List ledger (public)", tags=["Public · Ledger"])
async def public_ledger(limit: int = 100, event_type: str | None = None):
    """List card issuance and trade ledger entries. Public. Optional filter: event_type (e.g. card.issued, card.traded)."""
    if limit < 1 or limit > 200:
        limit = 100
    entries = await list_ledger(limit=limit, event_type=event_type)
    return {"entries": entries}
