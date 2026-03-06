"""Admin dashboard API: stats, user list, card sets and cards. Requires user to be in ADMIN_DISCORD_IDS."""
import os
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Body
from app.dependencies import get_current_admin
from app.services.acapy import agent_status
from app.db import (
    list_users,
    count_users,
    count_card_sets,
    count_cards_total,
    list_card_sets,
    create_card_set,
    get_card_set,
    update_card_set,
    delete_card_set,
    list_cards,
    create_card,
    get_card,
    update_card,
    delete_card,
    get_tenant_by_discord_sub,
    admin_issue_card_to_user,
)
from config import get_settings

settings = get_settings()
router = APIRouter(tags=["Admin"], prefix="/api/admin")


@router.get("/agent/settings")
async def admin_agent_settings(_admin: dict = Depends(get_current_admin)):
    """Return agent (ACA-Py) settings for admin UI. No secrets. Includes status check."""
    status = await agent_status()
    return {
        "admin_url": settings.acapy_admin_url or "(not set)",
        "admin_url_configured": bool(settings.acapy_admin_url and settings.acapy_admin_url.strip()),
        "api_key_configured": bool(settings.acapy_admin_api_key and settings.acapy_admin_api_key.strip()),
        "innkeeper_configured": bool(settings.innkeeper_id and settings.innkeeper_key),
        "status": status,
    }


@router.get("/stats")
async def admin_stats(_admin: dict = Depends(get_current_admin)):
    """Return counts for the admin dashboard."""
    total_users = await count_users()
    total_sets = await count_card_sets()
    total_cards = await count_cards_total()
    return {"total_users": total_users, "total_sets": total_sets, "total_cards": total_cards}


@router.get("/users")
async def admin_users(_admin: dict = Depends(get_current_admin), limit: int = 500):
    """List registered users (discord_sub, username, wallet_id, created_at)."""
    if limit < 1 or limit > 1000:
        limit = 500
    users = await list_users(limit=limit)
    return {"users": users}


# ---- Card sets ----

@router.get("/sets")
async def admin_list_sets(_admin: dict = Depends(get_current_admin)):
    """List all card sets."""
    sets = await list_card_sets()
    return {"sets": sets}


def _save_set_back_image(set_id: str, file: UploadFile) -> str:
    """Save uploaded card back image (PNG or SVG); return path relative to upload_dir (e.g. sets/{set_id}/back.png)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = (os.path.splitext(file.filename)[1] or ".png").lower()
    if ext not in (".png", ".svg", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="Card back must be PNG, SVG, JPG, or WebP")
    base = os.path.abspath(settings.upload_dir)
    subdir = os.path.join("sets", set_id)
    dest_dir = os.path.join(base, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    name = f"back{ext}"
    path = os.path.join(dest_dir, name)
    rel = os.path.join(subdir, name).replace("\\", "/")
    return rel


@router.post("/sets")
async def admin_create_set(
    _admin: dict = Depends(get_current_admin),
    name: str = Form(...),
    slug: str = Form(""),
    description: str = Form(""),
    set_type: str = Form(""),
    card_back: UploadFile | None = File(None),
):
    """Create a new card set. Optionally upload a card back image and set a set type."""
    try:
        out = await create_card_set(
            name=name, slug=(slug or "").strip(), description=description, set_type=set_type.strip()
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=400, detail="A set with this slug already exists")
        raise
    if not out:
        raise HTTPException(status_code=500, detail="Failed to create set")
    if card_back and card_back.filename:
        try:
            rel = _save_set_back_image(out["id"], card_back)
            contents = await card_back.read()
            base = os.path.abspath(settings.upload_dir)
            full = os.path.join(base, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(contents)
            out = await update_card_set(out["id"], card_back_path=rel)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save card back image: {e}")
    return out


@router.get("/sets/{set_id}")
async def admin_get_set(set_id: str, _admin: dict = Depends(get_current_admin)):
    """Get a single card set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    return s


@router.put("/sets/{set_id}")
async def admin_update_set(
    set_id: str,
    _admin: dict = Depends(get_current_admin),
    name: str | None = Form(None),
    slug: str | None = Form(None),
    description: str | None = Form(None),
):
    """Update a card set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    try:
        out = await update_card_set(set_id, name=name, slug=slug, description=description)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=400, detail="A set with this slug already exists")
        raise
    return out or s


@router.delete("/sets/{set_id}")
async def admin_delete_set(set_id: str, _admin: dict = Depends(get_current_admin)):
    """Delete a card set (and its cards)."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    ok = await delete_card_set(set_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete set")
    return {"deleted": True}


# ---- Cards ----

def _save_card_image(set_id: str, card_id: str, file: UploadFile) -> str:
    """Save uploaded PNG; return path relative to upload_dir (e.g. cards/{set_id}/{card_id}.png)."""
    if not file.filename or not file.filename.lower().endswith(".png"):
        raise HTTPException(status_code=400, detail="Only PNG files are allowed")
    base = os.path.abspath(settings.upload_dir)
    subdir = os.path.join("cards", set_id)
    dest_dir = os.path.join(base, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".png"
    name = f"{card_id}{ext}"
    path = os.path.join(dest_dir, name)
    rel = os.path.join(subdir, name).replace("\\", "/")
    return rel


@router.get("/sets/{set_id}/cards")
async def admin_list_cards(set_id: str, _admin: dict = Depends(get_current_admin)):
    """List cards in a set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    cards = await list_cards(set_id)
    return {"cards": cards}


@router.post("/sets/{set_id}/cards")
async def admin_create_card(
    set_id: str,
    _admin: dict = Depends(get_current_admin),
    name: str = Form(...),
    number: str = Form(""),
    rarity: str = Form("common"),
    set_name: str = Form(""),
    quote: str = Form(""),
    artwork: str = Form(""),
    photograph: str = Form(""),
    artist: str = Form(""),
    band: str = Form(""),
    image: UploadFile | None = File(None),
    types: str = Form("TradingCard"),
    subtypes: str = Form("trading-cards"),
    supertype: str = Form("trading-card"),
):
    """Add a card to a set. Optionally upload a PNG image."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    image_path = ""
    if image and image.filename:
        card = await create_card(
            set_id=set_id,
            name=name,
            number=number,
            rarity=rarity,
            set_name=set_name or s["name"],
            quote=quote,
            artwork=artwork,
            photograph=photograph,
            artist=artist,
            band=band,
            image_path="",
            types=[t.strip() for t in types.split(",") if t.strip()] if types else None,
            subtypes=subtypes,
            supertype=supertype,
        )
        if not card:
            raise HTTPException(status_code=500, detail="Failed to create card")
        try:
            rel = _save_card_image(set_id, card["id"], image)
            contents = await image.read()
            base = os.path.abspath(settings.upload_dir)
            full = os.path.join(base, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(contents)
        except HTTPException:
            raise
        except Exception as e:
            await delete_card(card["id"])
            raise HTTPException(status_code=400, detail=f"Failed to save image: {e}")
        card = await update_card(card["id"], image_path=rel)
        return card or await get_card(card["id"])
    card = await create_card(
        set_id=set_id,
        name=name,
        number=number,
        rarity=rarity,
        set_name=set_name or s["name"],
        quote=quote,
        artwork=artwork,
        photograph=photograph,
        artist=artist,
        band=band,
        image_path=image_path,
        types=[t.strip() for t in types.split(",") if t.strip()] if types else None,
        subtypes=subtypes,
        supertype=supertype,
    )
    if not card:
        raise HTTPException(status_code=500, detail="Failed to create card")
    return card


@router.get("/cards/{card_id}")
async def admin_get_card(card_id: str, _admin: dict = Depends(get_current_admin)):
    """Get a single card."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    return c


@router.put("/cards/{card_id}")
async def admin_update_card(
    card_id: str,
    _admin: dict = Depends(get_current_admin),
    name: str | None = Form(None),
    number: str | None = Form(None),
    rarity: str | None = Form(None),
    set_name: str | None = Form(None),
    quote: str | None = Form(None),
    artwork: str | None = Form(None),
    photograph: str | None = Form(None),
    artist: str | None = Form(None),
    band: str | None = Form(None),
    image: UploadFile | None = File(None),
    types: str | None = Form(None),
    subtypes: str | None = Form(None),
    supertype: str | None = Form(None),
):
    """Update a card. Optionally replace image with new PNG."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    image_path = c.get("image_path") or ""
    if image and image.filename and image.filename.lower().endswith(".png"):
        try:
            rel = _save_card_image(c["set_id"], card_id, image)
            contents = await image.read()
            base = os.path.abspath(settings.upload_dir)
            full = os.path.join(base, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(contents)
            image_path = rel
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save image: {e}")
    types_list = None
    if types is not None:
        types_list = [t.strip() for t in types.split(",") if t.strip()]
    out = await update_card(
        card_id,
        name=name,
        number=number,
        rarity=rarity,
        set_name=set_name,
        quote=quote,
        artwork=artwork,
        photograph=photograph,
        artist=artist,
        band=band,
        image_path=image_path if (image and image.filename) else None,
        types=types_list,
        subtypes=subtypes,
        supertype=supertype,
    )
    if image and image.filename and image_path:
        out = await get_card(card_id)
        if out:
            out["image_path"] = image_path
    return out or await get_card(card_id)


@router.delete("/cards/{card_id}")
async def admin_delete_card(card_id: str, _admin: dict = Depends(get_current_admin)):
    """Delete a card."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    ok = await delete_card(card_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete card")
    return {"deleted": True}


@router.post("/cards/{card_id}/issue")
async def admin_issue_card(
    card_id: str,
    _admin: dict = Depends(get_current_admin),
    body: dict = Body(...),
):
    """Issue an instance of a card to a user. Body: { "discord_sub": "<user's discord sub>" }. User must be registered (have a wallet)."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    discord_sub = (body.get("discord_sub") or "").strip()
    if not discord_sub:
        raise HTTPException(status_code=400, detail="discord_sub is required")
    tenant = await get_tenant_by_discord_sub(discord_sub)
    if not tenant:
        raise HTTPException(
            status_code=400,
            detail="User not found or has no wallet. They must log in at least once before you can issue a card.",
        )
    issued = await admin_issue_card_to_user(card_id, discord_sub)
    if not issued:
        raise HTTPException(status_code=500, detail="Failed to record issuance")
    return {"issued": True, "issuance": issued}
