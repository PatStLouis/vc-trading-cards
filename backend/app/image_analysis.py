"""Analyze card images: metadata (format, dimensions, EXIF/ICC) and optional OCR via microservice."""
from __future__ import annotations

from typing import Any

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def analyze_image(data: bytes, content_type: str | None = None, run_ocr: bool = True) -> dict[str, Any]:
    """
    Analyze image bytes. Returns format, dimensions, EXIF/ICC flags,
    and optional suggested card fields from OCR (when OCR_SERVICE_URL is set and run_ocr=True).
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
        _run_ocr(data, content_type, result)

    return result


def _run_ocr(data: bytes, content_type: str | None, result: dict[str, Any]) -> None:
    """Call OCR microservice if configured; merge raw_text and suggested into result."""
    from config import get_settings
    settings = get_settings()
    url = (settings.ocr_service_url or "").strip()
    if not url:
        return
    base = url.rstrip("/")
    ocr_url = f"{base}/ocr"
    try:
        import httpx
        content_type = content_type or "image/png"
        headers = {}
        if (settings.admin_api_key or "").strip():
            headers["X-OCR-API-Key"] = (settings.admin_api_key or "").strip()
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                ocr_url,
                files={"file": ("image", data, content_type)},
                headers=headers,
            )
        if r.status_code != 200:
            return
        data_resp = r.json()
        if data_resp.get("raw_text"):
            result["raw_text"] = data_resp["raw_text"]
        if data_resp.get("suggested"):
            result["suggested"] = data_resp["suggested"]
    except Exception:
        pass
