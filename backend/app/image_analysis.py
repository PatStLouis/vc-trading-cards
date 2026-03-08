"""Analyze card images: file metadata (format, dimensions, EXIF/ICC) and optional OCR for suggested fields."""
from __future__ import annotations

import re
import warnings
from typing import Any

# Max dimension (longest side) for OCR input. Card images are downscaled to this for fast OCR.
# 1024 is a good balance for consistent card uploads: keeps text sharp, much faster than full-res.
MAX_OCR_DIMENSION = 1024

# Optional: OCR (EasyOCR = Python-only; no system Tesseract needed)
_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is not None:
        return _ocr_reader
    try:
        # Suppress PyTorch DataLoader pin_memory warning when no GPU is available (EasyOCR uses torch)
        warnings.filterwarnings(
            "ignore",
            message=".*pin_memory.*",
            category=UserWarning,
        )
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return _ocr_reader
    except Exception:
        return None


def preload_ocr_reader() -> None:
    """Load the EasyOCR model in the current thread. Call at startup so first analyze request is fast."""
    _get_ocr_reader()


def _ocr_image_to_string(img) -> str | None:
    """Run OCR on a PIL Image; return combined text or None. Uses EasyOCR (Python-only)."""
    reader = _get_ocr_reader()
    if reader is None:
        return None
    try:
        import numpy as np
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
        results = reader.readtext(arr)
        if not results:
            return None
        # Sort by top (y) then left (x) to keep reading order
        results.sort(key=lambda x: (float(x[0][0][1]), float(x[0][0][0])))
        return "\n".join(item[1] for item in results if item[1].strip()).strip()
    except Exception:
        return None


try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def analyze_image(data: bytes, content_type: str | None = None, run_ocr: bool = True) -> dict[str, Any]:
    """
    Analyze image bytes. Returns format, dimensions, EXIF/ICC flags,
    and optional suggested card fields from OCR (name, quote, photograph, number).
    Set run_ocr=False for metadata-only (faster).
    """
    result: dict[str, Any] = {
        "format": None,
        "width": None,
        "height": None,
        "has_exif": False,
        "has_icc": False,
        "suggested": {},
    }

    if not HAS_PIL:
        result["error"] = "Pillow not installed; cannot read image metadata."
        return result

    try:
        from io import BytesIO
        img = Image.open(BytesIO(data))
    except Exception as e:
        result["error"] = str(e)
        return result

    result["format"] = img.format or "Unknown"
    result["width"], result["height"] = img.size

    if hasattr(img, "info") and img.info:
        result["has_exif"] = bool(img.info.get("exif"))
        result["has_icc"] = bool(img.info.get("icc_profile"))

    exif = getattr(img, "getexif", lambda: None)()
    if exif and len(exif):
        result["has_exif"] = True

    if run_ocr:
        raw_text = _ocr_image_to_string(img)
        if raw_text:
            result["raw_text"] = raw_text
            result["suggested"] = _suggest_fields_from_text(raw_text)

    return result


def _suggest_fields_from_text(text: str) -> dict[str, str]:
    """Heuristically extract suggested name, quote, photograph, number from OCR text."""
    suggested: dict[str, str] = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # PHOTO: ... or PHOTOGRAPH: ...
    for i, line in enumerate(lines):
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

    # Card number: "1/57" or "42/100"
    number_match = re.search(r"\b(\d+)\s*/\s*(\d+)\b", text)
    if number_match:
        suggested["number"] = number_match.group(1)
        suggested["total_in_set"] = number_match.group(2)

    # Edition: line containing "EDITION" or "SET"
    for line in lines:
        if "EDITION" in line.upper() or ("SET" in line.upper() and "1ST" in line.upper()):
            suggested["edition"] = line
            break

    # Quoted line → quote
    for line in lines:
        if line.startswith('"') and line.endswith('"') and len(line) > 2:
            suggested["quote"] = line[1:-1].strip()
            break
    if "quote" not in suggested:
        for line in lines:
            if "NEVER" in line.upper() or "AGAIN" in line.upper() or ("FUCK" in line.upper() and "YOU" in line.upper()):
                suggested["quote"] = line
                break

    # Name: often the largest / most prominent line; use first non-meta line or line before quote/photo
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
        # Prefer a line that looks like a name (capitalized words, not too long)
        for c in name_candidates:
            if 3 <= len(c) <= 60 and not c.startswith("'"):
                suggested["name"] = c
                break
        if "name" not in suggested:
            suggested["name"] = name_candidates[0]

    return {k: v for k, v in suggested.items() if v}
