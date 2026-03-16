"""Sync card images: pull from DB to disk. Used at startup and by admin Pull from DB."""
import os

from app.db import list_cards_with_image_data_and_path, get_card_image_data


async def pull_images_from_db(upload_dir: str, *, force: bool = False) -> dict:
    """
    Write card images from card_image_data to disk under upload_dir.
    Only writes when local file is missing (or force=True).
    Returns {"pulled": N, "skipped": M, "errors": [...]}.
    """
    upload_base = os.path.abspath(upload_dir)
    cards = await list_cards_with_image_data_and_path()
    pulled = 0
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
        if not force and os.path.isfile(local_path):
            skipped += 1
            continue
        data, _ = await get_card_image_data(card["id"])
        if not data:
            errors.append({"card_id": card["id"], "image_path": image_path, "error": "No image data in DB"})
            continue
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(data)
            pulled += 1
        except OSError as e:
            errors.append({"card_id": card["id"], "image_path": image_path, "error": str(e)})
    return {"pulled": pulled, "skipped": skipped, "errors": errors}
