"""Admin dashboard API: stats, user list, card sets and cards. Requires user to be in ADMIN_DISCORD_IDS."""
import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Body
from app.dependencies import get_current_admin
from app.schemas import (
    ISSUE_CARD_EXAMPLES,
    RESPONSE_AGENT_SETTINGS,
    RESPONSE_STATS,
    RESPONSE_USERS,
    RESPONSE_SETS,
    RESPONSE_SET,
    RESPONSE_CARDS,
    RESPONSE_CARD,
    RESPONSE_DELETED,
    RESPONSE_ISSUE,
    RESPONSE_LEDGER,
    RESPONSE_DISCORD_REGISTER,
    RESPONSE_GUILDS,
    RESPONSE_GUILD,
    RESPONSE_GUILD_MEMBERS,
    response_example,
)
from app.services.acapy import agent_status
from app.services.discord import (
    DiscordServiceError,
    register_slash_commands,
    get_bot_guilds,
    get_guild,
    get_guild_members,
)
from app.db import (
    list_users,
    count_users,
    get_registered_discord_ids,
    get_user_by_provider,
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
    get_tenant_by_user_id,
    apply_card_issued_event,
    list_ledger,
)
from app.image_analysis import analyze_image
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/admin")  # per-route tags for Swagger sections

# Discord routes: separate tag so they appear in "Admin · Discord" section in Swagger
discord_router = APIRouter(tags=["Admin · Discord"], prefix="/discord")


@router.get("/agent/settings", responses={200: response_example(RESPONSE_AGENT_SETTINGS)}, tags=["Admin · Agent"])
async def agent_settings(_admin: dict = Depends(get_current_admin)):
    """Agent (ACA-Py) settings and status. No secrets."""
    status = await agent_status()
    client_id = (settings.discord_client_id or "").strip()
    invite_url = None
    if client_id:
        from urllib.parse import urlencode
        params = {
            "client_id": client_id,
            "permissions": "0",
            "scope": "bot applications.commands",
        }
        invite_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return {
        "admin_url": settings.acapy_admin_url or "(not set)",
        "admin_url_configured": bool(settings.acapy_admin_url and settings.acapy_admin_url.strip()),
        "api_key_configured": bool(settings.acapy_admin_api_key and settings.acapy_admin_api_key.strip()),
        "innkeeper_configured": bool(settings.innkeeper_id and settings.innkeeper_key),
        "discord_bot_configured": bool(
            settings.discord_bot_token and settings.discord_client_id
        ),
        "discord_bot_invite_url": invite_url,
        "status": status,
    }


@router.get("/stats", responses={200: response_example(RESPONSE_STATS)}, tags=["Admin · Stats"])
async def stats(_admin: dict = Depends(get_current_admin)):
    """Dashboard counts (users, sets, cards)."""
    total_users = await count_users()
    total_sets = await count_card_sets()
    total_cards = await count_cards_total()
    return {"total_users": total_users, "total_sets": total_sets, "total_cards": total_cards}


@router.get("/users", responses={200: response_example(RESPONSE_USERS)}, tags=["Admin · Users"])
async def list_users_route(_admin: dict = Depends(get_current_admin), limit: int = 500):
    """List users."""
    if limit < 1 or limit > 1000:
        limit = 500
    users = await list_users(limit=limit)
    return {"users": users}


# ---- Sets ----

@router.get("/sets", responses={200: response_example(RESPONSE_SETS)}, tags=["Admin · Sets"])
async def list_sets(_admin: dict = Depends(get_current_admin)):
    """List sets."""
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


@router.post("/sets", responses={200: response_example(RESPONSE_SET)}, tags=["Admin · Sets"])
async def create_set(
    _admin: dict = Depends(get_current_admin),
    name: str = Form(...),
    slug: str = Form(""),
    description: str = Form(""),
    set_type: str = Form(""),
    card_back: UploadFile | None = File(None),
):
    """Create set. Optional: card back image, set type."""
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


@router.get("/sets/{set_id}", responses={200: response_example(RESPONSE_SET)}, tags=["Admin · Sets"])
async def get_set(set_id: str, _admin: dict = Depends(get_current_admin)):
    """Get set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    return s


@router.put("/sets/{set_id}", responses={200: response_example(RESPONSE_SET)}, tags=["Admin · Sets"])
async def update_set(
    set_id: str,
    _admin: dict = Depends(get_current_admin),
    name: str | None = Form(None),
    slug: str | None = Form(None),
    description: str | None = Form(None),
):
    """Update set."""
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


@router.delete("/sets/{set_id}", responses={200: response_example(RESPONSE_DELETED)}, tags=["Admin · Sets"])
async def delete_set(set_id: str, _admin: dict = Depends(get_current_admin)):
    """Delete set and its cards."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    ok = await delete_card_set(set_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete set")
    return {"deleted": True}


# ---- Cards ----

ANALYZE_IMAGE_RESPONSE = {
    "format": "JPEG",
    "width": 732,
    "height": 1024,
    "has_exif": False,
    "has_icc": True,
    "suggested": {
        "name": "PHIL BOZEMAN",
        "quote": "YOU WILL NEVER FUCK AGAIN",
        "photograph": "UNKNOWN ARTIST",
        "number": "1",
        "total_in_set": "57",
        "edition": "OG SET, 1ST EDITION",
    },
}


@router.post(
    "/analyze-card-image",
    responses={200: response_example(ANALYZE_IMAGE_RESPONSE)},
    tags=["Admin · Cards"],
)
async def analyze_card_image(
    _admin: dict = Depends(get_current_admin),
    image: UploadFile = File(...),
    ocr: bool = True,
):
    """
    Analyze an image file: format, dimensions, EXIF/ICC, and optional OCR suggestions
    (name, quote, photographer, card number). Use before or when adding a card to pre-fill form.
    Set ocr=false for metadata-only (faster, no suggested fields).
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = (os.path.splitext(image.filename)[1] or "").lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Image must be PNG or JPEG")
    try:
        contents = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")
    result = await asyncio.to_thread(analyze_image, contents, None, ocr)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


def _save_card_image(set_id: str, card_id: str, file: UploadFile) -> str:
    """Save uploaded card image (PNG or JPEG); return path relative to upload_dir (e.g. cards/{set_id}/{card_id}.png)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = (os.path.splitext(file.filename)[1] or ".png").lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Card image must be PNG or JPEG")
    base = os.path.abspath(settings.upload_dir)
    subdir = os.path.join("cards", set_id)
    dest_dir = os.path.join(base, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    name = f"{card_id}{ext}"
    rel = os.path.join(subdir, name).replace("\\", "/")
    return rel


@router.get("/sets/{set_id}/cards", responses={200: response_example(RESPONSE_CARDS)}, tags=["Admin · Cards"])
async def list_cards_in_set(set_id: str, _admin: dict = Depends(get_current_admin)):
    """List cards in set."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    cards = await list_cards(set_id)
    return {"cards": cards}


@router.post("/sets/{set_id}/cards", responses={200: response_example(RESPONSE_CARD)}, tags=["Admin · Cards"])
async def create_card_route(
    set_id: str,
    _admin: dict = Depends(get_current_admin),
    card_id: str = Form(...),
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
    """Create card in set. card_id is a unique id (e.g. UUID or hash). Optional: PNG or JPEG image."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    image_path = ""
    if image and image.filename:
        card = await create_card(
            set_id=set_id,
            card_id=card_id.strip(),
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
        card_id=card_id.strip(),
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


@router.get("/cards/{card_id}", responses={200: response_example(RESPONSE_CARD)}, tags=["Admin · Cards"])
async def get_card_route(card_id: str, _admin: dict = Depends(get_current_admin)):
    """Get card."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    return c


@router.put("/cards/{card_id}", responses={200: response_example(RESPONSE_CARD)}, tags=["Admin · Cards"])
async def update_card_route(
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
    """Update card. Optional: replace image."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    image_path = c.get("image_path") or ""
    if image and image.filename:
        ext = (os.path.splitext(image.filename)[1] or "").lower()
        if ext in (".png", ".jpg", ".jpeg"):
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


@router.delete("/cards/{card_id}", responses={200: response_example(RESPONSE_DELETED)}, tags=["Admin · Cards"])
async def delete_card_route(card_id: str, _admin: dict = Depends(get_current_admin)):
    """Delete card."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    ok = await delete_card(card_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete card")
    return {"deleted": True}


@router.post(
    "/cards/{card_id}/issue",
    responses={200: response_example(RESPONSE_ISSUE)},
    tags=["Admin · Cards"],
)
async def issue_card(
    card_id: str,
    _admin: dict = Depends(get_current_admin),
    body: dict = Body(..., examples=ISSUE_CARD_EXAMPLES),
):
    """Issue card to user. Body: user_id or discord_sub. User must have logged in once."""
    c = await get_card(card_id)
    if not c:
        raise HTTPException(status_code=404, detail="Card not found")
    user_id = (body.get("user_id") or "").strip()
    discord_sub = (body.get("discord_sub") or "").strip()
    if not user_id and discord_sub:
        user_id = await get_user_by_provider("discord", discord_sub)
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id or discord_sub is required")
    tenant = await get_tenant_by_user_id(user_id)
    if not tenant:
        raise HTTPException(
            status_code=400,
            detail="User not found or has no wallet. They must log in at least once before you can issue a card.",
        )
    actor_id = None if _admin.get("user_id") == "__admin_api_key__" else _admin.get("user_id")
    issued = await apply_card_issued_event(card_id, user_id, actor_id)
    if not issued:
        raise HTTPException(status_code=500, detail="Failed to record issuance")
    return {"issued": True, "issuance": issued}


@router.get("/ledger", responses={200: response_example(RESPONSE_LEDGER)}, tags=["Admin · Ledger"])
async def get_ledger(
    _admin: dict = Depends(get_current_admin),
    limit: int = 100,
    card_id: str | None = None,
    user_id: str | None = None,
    event_type: str | None = None,
):
    """List card issuance and trade ledger entries. Optional filters: card_id, user_id, event_type."""
    entries = await list_ledger(limit=limit, card_id=card_id, user_id=user_id, event_type=event_type)
    return {"entries": entries}


# ---- Discord ----

@discord_router.post("/register-commands", responses={200: response_example(RESPONSE_DISCORD_REGISTER)})
async def register_commands(_admin: dict = Depends(get_current_admin)):
    """Register slash commands (/wallet, /collection) with Discord."""
    try:
        registered = await register_slash_commands(
            settings.discord_client_id or "", settings.discord_bot_token or ""
        )
    except DiscordServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"registered": registered}


@discord_router.get("/guilds", responses={200: response_example(RESPONSE_GUILDS)})
async def list_guilds(_admin: dict = Depends(get_current_admin)):
    """List guilds where the bot is invited."""
    try:
        guilds = await get_bot_guilds(settings.discord_bot_token or "")
    except DiscordServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"guilds": guilds}


@discord_router.get("/guilds/{guild_id}", responses={200: response_example(RESPONSE_GUILD)})
async def get_guild_route(guild_id: str, _admin: dict = Depends(get_current_admin)):
    """Get guild details."""
    try:
        data = await get_guild(settings.discord_bot_token or "", guild_id)
    except DiscordServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return data


@discord_router.get("/guilds/{guild_id}/members", responses={200: response_example(RESPONSE_GUILD_MEMBERS)})
async def list_guild_members(
    guild_id: str,
    _admin: dict = Depends(get_current_admin),
    limit: int = 100,
    after: str | None = None,
):
    """List guild members. Includes is_registered for app users."""
    if limit < 1 or limit > 1000:
        limit = 100
    try:
        data = await get_guild_members(
            settings.discord_bot_token or "", guild_id, limit=limit, after=after
        )
    except DiscordServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    user_ids = [m["user"]["id"] for m in data if m.get("user", {}).get("id")]
    registered = await get_registered_discord_ids(user_ids)
    for m in data:
        m["is_registered"] = (m.get("user", {}).get("id") or "") in registered
    return {"members": data}


# discord_router is mounted in main.py under prefix /api/admin so it only gets tag "Admin · Discord"
