"""Admin dashboard API: stats, user list, card sets and cards. Requires user to be in ADMIN_DISCORD_IDS."""
import asyncio
import os
from urllib.parse import urlparse
import httpx
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
    list_card_set_back_paths,
    create_card_set,
    get_card_set,
    update_card_set,
    delete_card_set,
    list_cards,
    list_cards_with_image_paths,
    list_cards_with_image_data_and_path,
    set_card_image_data,
    get_card_image_data,
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
from app.image_sync import pull_images_from_db as do_pull_images_from_db
from app.provision_set import provision_set_pack, provision_set_from_uploads
from app.draw import draw_cards
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


SYNC_IMAGES_RESPONSE = {
    "synced": 12,
    "skipped": 3,
    "errors": [{"card_id": "uuid", "image_path": "cards/set/card.png", "error": "404"}],
}


@router.post(
    "/sync-images",
    responses={200: response_example(SYNC_IMAGES_RESPONSE)},
    tags=["Admin · Sets"],
)
async def sync_images(
    _admin: dict = Depends(get_current_admin),
    source_url: str = Body("", embed=True, description="Base URL of the instance to pull images from (e.g. http://localhost:8000). Overrides SYNC_SOURCE_URL if set."),
    force: bool = Body(False, embed=True, description="Re-download even if file already exists locally."),
):
    """
    Pull card images from another instance (e.g. your local backend) into this instance's upload dir.
    Use when DB is shared but uploads live only on the source. Lists cards with image_path from DB,
    fetches each from source/uploads/{image_path}, and saves locally. Skips existing files unless force=true.
    """
    base_url = (source_url or getattr(settings, "sync_source_url", "") or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=400,
            detail="Provide source_url in the request body or set SYNC_SOURCE_URL (e.g. http://localhost:8000)."
        )
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="source_url must be http or https.")
    upload_base = os.path.abspath(settings.upload_dir)
    cards = await list_cards_with_image_paths()
    synced = 0
    skipped = 0
    errors: list[dict] = []
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for card in cards:
            image_path = card["image_path"]
            if not image_path or ".." in image_path or image_path.startswith("/"):
                errors.append({"card_id": card["id"], "image_path": image_path, "error": "Invalid image_path"})
                continue
            local_path = os.path.join(upload_base, image_path)
            if not os.path.normpath(local_path).startswith(upload_base):
                errors.append({"card_id": card["id"], "image_path": image_path, "error": "Path escapes upload dir"})
                continue
            if not force and os.path.isfile(local_path):
                skipped += 1
                continue
            url = f"{base_url}/uploads/{image_path}"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                errors.append({"card_id": card["id"], "image_path": image_path, "error": f"HTTP {e.response.status_code}"})
                continue
            except Exception as e:
                errors.append({"card_id": card["id"], "image_path": image_path, "error": str(e)})
                continue
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                synced += 1
            except OSError as e:
                errors.append({"card_id": card["id"], "image_path": image_path, "error": str(e)})
        # Set card backs: pull from source for each set that has card_back_path in DB
        set_backs = await list_card_set_back_paths()
        for s in set_backs:
            image_path = s["card_back_path"]
            if not image_path or ".." in image_path or image_path.startswith("/"):
                errors.append({"set_id": s["id"], "image_path": image_path, "error": "Invalid card_back_path"})
                continue
            local_path = os.path.join(upload_base, image_path)
            if not os.path.normpath(local_path).startswith(upload_base):
                errors.append({"set_id": s["id"], "image_path": image_path, "error": "Path escapes upload dir"})
                continue
            if not force and os.path.isfile(local_path):
                skipped += 1
                continue
            url = f"{base_url}/uploads/{image_path}"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                errors.append({"set_id": s["id"], "image_path": image_path, "error": f"HTTP {e.response.status_code}"})
                continue
            except Exception as e:
                errors.append({"set_id": s["id"], "image_path": image_path, "error": str(e)})
                continue
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                synced += 1
            except OSError as e:
                errors.append({"set_id": s["id"], "image_path": image_path, "error": str(e)})
    return {"synced": synced, "skipped": skipped, "errors": errors}


PUSH_PULL_RESPONSE = {
    "pushed": 10,
    "skipped": 2,
    "errors": [{"card_id": "uuid", "image_path": "cards/set/card.png", "error": "File not found"}],
}


@router.post(
    "/push-images-to-db",
    responses={200: response_example(PUSH_PULL_RESPONSE)},
    tags=["Admin · Sets"],
)
async def push_images_to_db(
    _admin: dict = Depends(get_current_admin),
    force: bool = Body(False, embed=True, description="Overwrite existing blob in DB even if already set."),
):
    """
    Push local card images into the database. Reads each card's image file from disk (image_path)
    and stores it in card_image_data. Use on the instance that has the files (e.g. local);
    then Pull from DB on the other instance (e.g. remote) to write files from DB to disk.
    """
    upload_base = os.path.abspath(settings.upload_dir)
    cards = await list_cards_with_image_paths()
    pushed = 0
    skipped = 0
    errors: list[dict] = []
    for card in cards:
        image_path = card["image_path"]
        if not image_path or ".." in image_path or image_path.startswith("/"):
            errors.append({"card_id": card["id"], "image_path": image_path, "error": "Invalid image_path"})
            continue
        local_path = os.path.join(upload_base, image_path)
        if not os.path.normpath(local_path).startswith(upload_base):
            errors.append({"card_id": card["id"], "image_path": image_path, "error": "Path escapes upload dir"})
            continue
        if not os.path.isfile(local_path):
            errors.append({"card_id": card["id"], "image_path": image_path, "error": "File not found"})
            continue
        if not force:
            existing, _ = await get_card_image_data(card["id"])
            if existing:
                skipped += 1
                continue
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            content_type = "image/png"
            if image_path.lower().endswith(".jpg") or image_path.lower().endswith(".jpeg"):
                content_type = "image/jpeg"
            await set_card_image_data(card["id"], data, content_type)
            pushed += 1
        except OSError as e:
            errors.append({"card_id": card["id"], "image_path": image_path, "error": str(e)})
        except Exception as e:
            errors.append({"card_id": card["id"], "image_path": image_path, "error": str(e)})
    return {"pushed": pushed, "skipped": skipped, "errors": errors}


@router.post(
    "/pull-images-from-db",
    responses={200: response_example({"pulled": 10, "skipped": 2, "errors": []})},
    tags=["Admin · Sets"],
)
async def pull_images_from_db(
    _admin: dict = Depends(get_current_admin),
    force: bool = Body(False, embed=True, description="Overwrite existing local files."),
):
    """
    Pull card images from the database to local disk. Reads each card's image from card_image_data
    and writes to upload_dir/image_path. Use on the instance that shares the DB but has no files
    (e.g. remote after local has run Push to DB).
    """
    result = await do_pull_images_from_db(settings.upload_dir, force=force)
    return {"pulled": result["pulled"], "skipped": result["skipped"], "errors": result["errors"]}


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


PROVISION_SET_RESPONSE = {
    "set": RESPONSE_SET,
    "cards_created": 0,
    "cards_skipped": 0,
    "errors": [],
    "created": True,
    "message": "optional message when set already existed",
}


@router.post(
    "/provision-set",
    responses={200: response_example(PROVISION_SET_RESPONSE)},
    tags=["Admin · Sets"],
)
async def provision_set_route(
    _admin: dict = Depends(get_current_admin),
    path: str = Body(..., embed=True),
    set_name: str | None = Body(None, embed=True),
    slug: str | None = Body(None, embed=True),
    skip_existing: bool = Body(True, embed=True),
):
    """
    Provision a set pack from disk into the app. The set pack directory must contain
    details.csv (CARD NUMBER, CARD NAME, RARITY, QUOTE, FILE NAME) and cards.zip (card images).
    path: directory path relative to server cwd or absolute (e.g. sets/OG_SET or ../sets/OG_SET).
    """
    if not (path or "").strip():
        raise HTTPException(status_code=400, detail="path is required")
    try:
        result = await provision_set_pack(
            pack_path=path.strip(),
            upload_dir=os.path.abspath(settings.upload_dir),
            set_name_override=set_name,
            slug_override=slug,
            skip_existing=skip_existing,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post(
    "/provision-set-upload",
    responses={200: response_example(PROVISION_SET_RESPONSE)},
    tags=["Admin · Sets"],
)
async def provision_set_upload_route(
    _admin: dict = Depends(get_current_admin),
    csv_file: UploadFile = File(..., description="details.csv with columns: CARD NUMBER, CARD NAME, RARITY, QUOTE, FILE NAME"),
    zip_file: UploadFile = File(..., description="cards.zip with card images named {FILE NAME}.png"),
    set_name: str = Form("Imported Set"),
    slug: str = Form(""),
    set_type: str = Form(""),
    card_back: UploadFile | None = File(None),
    skip_existing: bool = Form(True),
):
    """
    Provision a set by uploading details.csv and cards.zip. Optional: set type (collection/promo), card back image.
    CSV must have columns: CARD NUMBER, CARD NAME, RARITY, QUOTE, FILE NAME.
    """
    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file (details.csv)")
    if not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a ZIP file (cards.zip)")
    try:
        csv_bytes = await csv_file.read()
        zip_bytes = await zip_file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploads: {e}")
    if len(csv_bytes) == 0:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    if len(zip_bytes) == 0:
        raise HTTPException(status_code=400, detail="ZIP file is empty")

    result = await provision_set_from_uploads(
        csv_bytes=csv_bytes,
        zip_bytes=zip_bytes,
        upload_dir=os.path.abspath(settings.upload_dir),
        set_name_override=set_name.strip() or "Imported Set",
        slug_override=slug.strip() or None,
        set_type=set_type.strip(),
        skip_existing=skip_existing,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    if result.get("set") and card_back and card_back.filename:
        try:
            rel = _save_set_back_image(result["set"]["id"], card_back)
            contents = await card_back.read()
            base = os.path.abspath(settings.upload_dir)
            full = os.path.join(base, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(contents)
            updated = await update_card_set(result["set"]["id"], card_back_path=rel)
            if updated:
                result["set"] = updated
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save card back image: {e}")

    return result


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
    ocr: bool = False,
):
    """
    Analyze an image file: format, dimensions, EXIF/ICC. Optional OCR (name, quote, etc.) when
    ocr=true and OCR_SERVICE_URL is set. OCR is disabled by default.
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


DRAW_RESPONSE = {
    "drawn": [RESPONSE_CARD],
    "issuances": [{"id": "uuid", "card_id": "uuid", "user_id": "uuid", "issued_at": "iso8601"}],
}


@router.post(
    "/sets/{set_id}/draw",
    responses={200: response_example(DRAW_RESPONSE)},
    tags=["Admin · Cards"],
)
async def draw_and_issue(
    set_id: str,
    _admin: dict = Depends(get_current_admin),
    body: dict = Body(...),
):
    """
    Draw cards from the set using rarity-weighted RNG and issue them to a user.
    Body: discord_sub or user_id (required), count (default 1, max 20).
    Weights: common > uncommon > rare > ultra-rare > legendary by default.
    """
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
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
            detail="User not found or has no wallet. They must log in at least once before you can receive drawn cards.",
        )
    count = body.get("count", 1)
    try:
        count = max(1, min(20, int(count)))
    except (TypeError, ValueError):
        count = 1

    cards = await list_cards(set_id)
    if not cards:
        raise HTTPException(status_code=400, detail="Set has no cards to draw from")

    drawn = await asyncio.to_thread(draw_cards, cards, count)

    actor_id = None if _admin.get("user_id") == "__admin_api_key__" else _admin.get("user_id")
    issuances = []
    for card in drawn:
        issued = await apply_card_issued_event(card["id"], user_id, actor_id)
        if issued:
            issuances.append(issued)

    return {"drawn": drawn, "issuances": issuances}


@router.post("/sets/{set_id}/cards", responses={200: response_example(RESPONSE_CARD)}, tags=["Admin · Cards"])
async def create_card_route(
    set_id: str,
    _admin: dict = Depends(get_current_admin),
    card_id: str = Form(...),
    name: str = Form(""),
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
    """Create card in set. card_id is a unique id (e.g. UUID or hash). name is display name; optional PNG/JPEG image."""
    s = await get_card_set(set_id)
    if not s:
        raise HTTPException(status_code=404, detail="Set not found")
    image_path = ""
    if image and image.filename:
        card = await create_card(
            set_id=set_id,
            card_id=card_id.strip(),
            name=name.strip(),
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
        name=name.strip(),
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
