"""OCR microservice: POST image bytes, returns raw_text + suggested card fields (EasyOCR)."""
from __future__ import annotations

import os
import re
import warnings
from io import BytesIO

from fastapi import FastAPI, File, Header, UploadFile, HTTPException, Depends
from pydantic import BaseModel

OCR_API_KEY = (os.getenv("OCR_API_KEY") or os.getenv("ADMIN_API_KEY") or "").strip()

# Suppress PyTorch pin_memory warning when no GPU
warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)

try:
    from PIL import Image
    import numpy as np
    import easyocr
except ImportError as e:
    raise RuntimeError(f"Install dependencies: {e}") from e

MAX_OCR_DIMENSION = 1024
_reader = None


def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


def ocr_image_to_text(image_bytes: bytes) -> str | None:
    img = Image.open(BytesIO(image_bytes))
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_OCR_DIMENSION:
        ratio = MAX_OCR_DIMENSION / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, getattr(Image, "Resampling", Image).LANCZOS)
    arr = np.array(img)
    if len(arr.shape) == 2:
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.shape[-1] == 4:
        arr = arr[:, :, :3]
    results = get_reader().readtext(arr)
    if not results:
        return None
    results.sort(key=lambda x: (float(x[0][0][1]), float(x[0][0][0])))
    return "\n".join(item[1] for item in results if item[1].strip()).strip()


def suggest_fields_from_text(text: str) -> dict[str, str]:
    suggested: dict[str, str] = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for line in lines:
        upper = line.upper()
        if upper.startswith("PHOTO:") or upper.startswith("PHOTOGRAPH:"):
            suggested["photograph"] = line.split(":", 1)[-1].strip()
            break
        if "PHOTO" in upper and ":" in line:
            idx = line.upper().index("PHOTO")
            rest = line[idx:]
            if ":" in rest:
                suggested["photograph"] = rest.split(":", 1)[-1].strip()
                break

    number_match = re.search(r"\b(\d+)\s*/\s*(\d+)\b", text)
    if number_match:
        suggested["number"] = number_match.group(1)
        suggested["total_in_set"] = number_match.group(2)

    for line in lines:
        if "EDITION" in line.upper() or ("SET" in line.upper() and "1ST" in line.upper()):
            suggested["edition"] = line
            break

    for line in lines:
        if line.startswith('"') and line.endswith('"') and len(line) > 2:
            suggested["quote"] = line[1:-1].strip()
            break
    if "quote" not in suggested:
        for line in lines:
            if "NEVER" in line.upper() or "AGAIN" in line.upper() or ("FUCK" in line.upper() and "YOU" in line.upper()):
                suggested["quote"] = line
                break

    meta_keywords = ("PHOTO", "PHOTOGRAPH", "EDITION", "SET", "ARTIST", "OG SET", "1ST")
    name_candidates = []
    for line in lines:
        upper = line.upper()
        if any(kw in upper for kw in meta_keywords):
            continue
        if re.match(r"^\d+\s*/\s*\d+$", line):
            continue
        if line == suggested.get("quote"):
            continue
        if len(line) >= 2 and line.isprintable():
            name_candidates.append(line)
    if name_candidates:
        for c in name_candidates:
            if 3 <= len(c) <= 60 and not c.startswith("'"):
                suggested["name"] = c
                break
        if "name" not in suggested:
            suggested["name"] = name_candidates[0]

    return {k: v for k, v in suggested.items() if v}


class OCRResponse(BaseModel):
    raw_text: str | None = None
    suggested: dict[str, str]


app = FastAPI(title="OCR Service", version="0.1.0")


def _check_ocr_api_key(x_ocr_api_key: str | None = Header(None, alias="X-OCR-API-Key")):
    """If OCR_API_KEY (or ADMIN_API_KEY) is set, require X-OCR-API-Key header to match."""
    if not OCR_API_KEY:
        return
    key = (x_ocr_api_key or "").strip()
    if key != OCR_API_KEY:
        raise HTTPException(401, "Invalid or missing X-OCR-API-Key")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr", response_model=OCRResponse)
async def ocr(
    file: UploadFile = File(...),
    _: None = Depends(_check_ocr_api_key),
):
    """Run OCR on uploaded image; return raw text and suggested card fields.
    If OCR_API_KEY or ADMIN_API_KEY is set, request must include header: X-OCR-API-Key: <key>."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Expected an image file")
    try:
        body = await file.read()
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    if len(body) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 20MB)")
    try:
        raw_text = ocr_image_to_text(body)
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}") from e
    if not raw_text:
        return OCRResponse(raw_text=None, suggested={})
    suggested = suggest_fields_from_text(raw_text)
    return OCRResponse(raw_text=raw_text, suggested=suggested)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
