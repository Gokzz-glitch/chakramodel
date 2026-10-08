"""Optional image decode validation.

The default workbench path remains standard-library-only.  This module
discovers an already-installed Pillow package and never installs dependencies.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def capability() -> dict[str, Any]:
    try:
        import PIL  # type: ignore
        return {"validator": "pillow", "available": True, "version": getattr(PIL, "__version__", "unknown")}
    except ImportError:
        return {"validator": "pillow", "available": False, "reason": "Pillow is not installed"}


def validate(path: Path) -> dict[str, Any]:
    info = capability()
    if not info["available"]:
        return {"status": "unavailable", **info}
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            return {
                "status": "decoded",
                "format": image.format,
                "width": image.width,
                "height": image.height,
                **info,
            }
    except Exception as exc:
        return {"status": "decode_error", "error_type": type(exc).__name__, **info}
