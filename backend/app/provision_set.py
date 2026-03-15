"""
Provision a set pack (details.csv + cards.zip) into the app: create set, cards, and extract images.
Can load from disk (provision_set_pack) or from uploaded files (provision_set_from_uploads).
CSV columns: CARD NUMBER, CARD NAME, RARITY, QUOTE, FILE NAME
ZIP: card images named {FILE NAME}.png (optionally under a single top-level folder e.g. "OG SET/")
"""
import csv
import io
import os
import zipfile
from pathlib import Path

from app.db import (
    create_card_set,
    create_card,
    get_card_by_card_id,
    list_card_sets,
)


def _slug_from_dir_name(name: str) -> str:
    """e.g. OG_SET -> og-set, My Set Pack -> my-set-pack."""
    return name.strip().replace(" ", "-").replace("_", "-").lower()


def _normalize_rarity(r: str) -> str:
    """COMMON -> common, ULTRA RARE -> ultra-rare (optional). Keep as lowercase single token or hyphenated."""
    if not (r or "").strip():
        return "common"
    s = r.strip().lower()
    if s == "ultra rare":
        return "ultra-rare"
    return s.replace(" ", "-")


def _parse_csv_rows(reader: csv.DictReader) -> list[dict]:
    """Parse DictReader into list of card row dicts."""
    rows = []
    for raw in reader:
        row = {
            "card_number": (raw.get("CARD NUMBER") or "").strip(),
            "card_name": (raw.get("CARD NAME") or "").strip(),
            "rarity": _normalize_rarity((raw.get("RARITY") or "").strip()),
            "quote": (raw.get("QUOTE") or "").strip(),
            "file_name": (raw.get("FILE NAME") or "").strip().removesuffix(".png"),
        }
        if not row["file_name"]:
            continue
        rows.append(row)
    return rows


def load_set_pack_csv(pack_dir: str) -> list[dict]:
    """
    Load details.csv from pack_dir. Returns list of dicts with keys:
    card_number, card_name, rarity, quote, file_name (stripmed, no .png).
    """
    path = Path(pack_dir) / "details.csv"
    if not path.is_file():
        raise FileNotFoundError(f"details.csv not found in {pack_dir}")
    with open(path, newline="", encoding="utf-8") as f:
        return _parse_csv_rows(csv.DictReader(f))


def load_set_pack_csv_from_bytes(csv_bytes: bytes) -> list[dict]:
    """Load CSV from bytes (UTF-8). Same row shape as load_set_pack_csv."""
    text = csv_bytes.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return _parse_csv_rows(csv.DictReader(io.StringIO(text)))


def _extract_zip_entries(zf: zipfile.ZipFile, dest_dir: str) -> list[str]:
    """Extract image entries from an open ZipFile into dest_dir; flatten one top-level folder. Returns basenames."""
    os.makedirs(dest_dir, exist_ok=True)
    written = []
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        base = os.path.basename(name.rstrip("/"))
        if not base or not base.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        target = os.path.join(dest_dir, base)
        with zf.open(name) as src:
            with open(target, "wb") as dst:
                dst.write(src.read())
        written.append(base)
    return written


def extract_cards_zip(zip_path: str, dest_dir: str) -> list[str]:
    """
    Extract card images from zip into dest_dir. Zip may have a single top-level folder
    (e.g. "OG SET/001_OGSET_NICKARTHUR.png"); we flatten so files land as dest_dir/001_OGSET_NICKARTHUR.png.
    Returns list of basenames written (e.g. 001_OGSET_NICKARTHUR.png).
    """
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError(f"cards.zip not found: {zip_path}")
    with zipfile.ZipFile(path, "r") as zf:
        return _extract_zip_entries(zf, dest_dir)


def extract_cards_zip_from_bytes(zip_bytes: bytes, dest_dir: str) -> list[str]:
    """Extract card images from zip bytes into dest_dir. Same behavior as extract_cards_zip."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        return _extract_zip_entries(zf, dest_dir)


async def provision_set_pack(
    pack_path: str,
    upload_dir: str,
    set_name_override: str | None = None,
    slug_override: str | None = None,
    skip_existing: bool = True,
) -> dict:
    """
    Provision a set pack from disk into the app.

    - pack_path: path to the set pack directory (e.g. sets/OG_SET), relative to cwd or absolute.
    - upload_dir: app upload directory (e.g. settings.upload_dir); images go under upload_dir/cards/{set_id}/.
    - set_name_override: if set, use as set name; else derived from directory name.
    - slug_override: if set, use as set slug; else derived from directory name.
    - skip_existing: if True and a set with the same slug exists, return it with created=False and no cards added.

    Returns dict: set, cards_created, cards_skipped, errors (list of str), created (bool).
    """
    pack_dir = Path(pack_path).resolve()
    if not pack_dir.is_dir():
        return {"error": f"Not a directory: {pack_path}", "created": False}

    csv_path = pack_dir / "details.csv"
    zip_path = pack_dir / "cards.zip"
    if not csv_path.is_file():
        return {"error": "details.csv not found", "created": False}
    if not zip_path.is_file():
        return {"error": "cards.zip not found", "created": False}

    dir_name = pack_dir.name
    set_name = (set_name_override or dir_name).strip()
    slug = (slug_override or _slug_from_dir_name(dir_name)).strip() or _slug_from_dir_name(set_name)

    # Check existing set by slug
    sets_list = await list_card_sets()
    existing = next((s for s in sets_list if (s.get("slug") or "").lower() == slug.lower()), None)
    if existing and skip_existing:
        return {
            "set": existing,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": [],
            "created": False,
            "message": f"Set with slug '{slug}' already exists; no changes made.",
        }

    if existing and not skip_existing:
        set_id = existing["id"]
        set_record = existing
        created_set = False
    else:
        created = await create_card_set(
            name=set_name,
            slug=slug,
            description="",
            set_type="",
            card_back_path="",
        )
        if not created:
            return {"error": "Failed to create set", "created": False}
        set_id = created["id"]
        set_record = created
        created_set = True

    rows = load_set_pack_csv(str(pack_dir))
    if not rows:
        return {
            "set": set_record,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": ["No rows in details.csv"],
            "created": created_set,
        }

    # Extract images to upload_dir/cards/{set_id}/
    base_upload = Path(upload_dir).resolve()
    cards_subdir = base_upload / "cards" / set_id
    try:
        extracted = extract_cards_zip(str(zip_path), str(cards_subdir))
    except Exception as e:
        return {
            "set": set_record,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": [f"Failed to extract cards.zip: {e}"],
            "created": created_set,
        }

    # Relative path prefix for image_path (e.g. cards/{set_id}/)
    image_path_prefix = f"cards/{set_id}"

    created_count = 0
    skipped_count = 0
    errors = []

    for r in rows:
        file_name = r["file_name"]
        ext = ".png"
        for e in [".png", ".jpg", ".jpeg", ".webp"]:
            if (cards_subdir / f"{file_name}{e}").exists():
                ext = e
                break
        image_path = f"{image_path_prefix}/{file_name}{ext}"

        existing_card = await get_card_by_card_id(set_id, file_name)
        if existing_card:
            skipped_count += 1
            continue

        card = await create_card(
            set_id=set_id,
            card_id=file_name,
            name=r["card_name"],
            number=r["card_number"],
            rarity=r["rarity"],
            set_name=set_name,
            quote=r["quote"],
            artwork="",
            image_path=image_path,
            photograph="",
            artist="",
            band="",
        )
        if card:
            created_count += 1
        else:
            errors.append(f"Failed to create card: {file_name}")

    return {
        "set": set_record,
        "cards_created": created_count,
        "cards_skipped": skipped_count,
        "errors": errors,
        "created": created_set,
    }


async def provision_set_from_uploads(
    csv_bytes: bytes,
    zip_bytes: bytes,
    upload_dir: str,
    set_name_override: str = "Imported Set",
    slug_override: str | None = None,
    set_type: str = "",
    skip_existing: bool = True,
) -> dict:
    """
    Provision a set from uploaded CSV and ZIP bytes (e.g. from form uploads).

    - csv_bytes: contents of details.csv (UTF-8).
    - zip_bytes: contents of cards.zip.
    - upload_dir: app upload directory; images go under upload_dir/cards/{set_id}/.
    - set_name_override: set name (default "Imported Set").
    - slug_override: if set, use as slug; else derived from set name.
    - set_type: optional type (e.g. "collection", "promo").
    - skip_existing: if True and a set with the same slug exists, return it with no cards added.

    Returns dict: set, cards_created, cards_skipped, errors (list of str), created (bool).
    """
    set_name = (set_name_override or "Imported Set").strip()
    slug = (slug_override or _slug_from_dir_name(set_name)).strip() or "imported-set"

    sets_list = await list_card_sets()
    existing = next((s for s in sets_list if (s.get("slug") or "").lower() == slug.lower()), None)
    if existing and skip_existing:
        return {
            "set": existing,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": [],
            "created": False,
            "message": f"Set with slug '{slug}' already exists; no changes made.",
        }

    if existing and not skip_existing:
        set_id = existing["id"]
        set_record = existing
        created_set = False
    else:
        created = await create_card_set(
            name=set_name,
            slug=slug,
            description="",
            set_type=(set_type or "").strip(),
            card_back_path="",
        )
        if not created:
            return {"error": "Failed to create set", "created": False}
        set_id = created["id"]
        set_record = created
        created_set = True

    try:
        rows = load_set_pack_csv_from_bytes(csv_bytes)
    except Exception as e:
        return {
            "set": set_record,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": [f"Invalid CSV: {e}"],
            "created": created_set,
        }

    if not rows:
        return {
            "set": set_record,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": ["CSV has no valid rows (need CARD NUMBER, CARD NAME, RARITY, QUOTE, FILE NAME)"],
            "created": created_set,
        }

    base_upload = Path(upload_dir).resolve()
    cards_subdir = base_upload / "cards" / set_id
    try:
        extract_cards_zip_from_bytes(zip_bytes, str(cards_subdir))
    except Exception as e:
        return {
            "set": set_record,
            "cards_created": 0,
            "cards_skipped": 0,
            "errors": [f"Failed to extract ZIP: {e}"],
            "created": created_set,
        }

    image_path_prefix = f"cards/{set_id}"
    created_count = 0
    skipped_count = 0
    errors = []

    for r in rows:
        file_name = r["file_name"]
        ext = ".png"
        for e in [".png", ".jpg", ".jpeg", ".webp"]:
            if (cards_subdir / f"{file_name}{e}").exists():
                ext = e
                break
        image_path = f"{image_path_prefix}/{file_name}{ext}"

        existing_card = await get_card_by_card_id(set_id, file_name)
        if existing_card:
            skipped_count += 1
            continue

        card = await create_card(
            set_id=set_id,
            card_id=file_name,
            name=r["card_name"],
            number=r["card_number"],
            rarity=r["rarity"],
            set_name=set_name,
            quote=r["quote"],
            artwork="",
            image_path=image_path,
            photograph="",
            artist="",
            band="",
        )
        if card:
            created_count += 1
        else:
            errors.append(f"Failed to create card: {file_name}")

    return {
        "set": set_record,
        "cards_created": created_count,
        "cards_skipped": skipped_count,
        "errors": errors,
        "created": created_set,
    }
