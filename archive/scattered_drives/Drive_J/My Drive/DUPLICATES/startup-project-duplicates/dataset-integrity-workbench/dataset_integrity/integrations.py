"""Optional integrations with explicit capability errors."""
from __future__ import annotations

import importlib
from typing import Any


class OptionalDependencyError(RuntimeError):
    """Raised when an explicitly requested optional integration is unavailable."""


def capability(name: str) -> dict[str, Any]:
    modules = {"cleanvision": "cleanvision", "fiftyone": "fiftyone", "datumaro": "datumaro",
               "gemini": "google.genai"}
    if name not in modules:
        raise ValueError("unknown integration: " + name)
    try:
        module = importlib.import_module(modules[name])
    except ImportError:
        return {"name": name, "available": False, "reason": f"optional dependency for {name} is not installed"}
    return {"name": name, "available": True, "version": getattr(module, "__version__", "unknown")}


def require(name: str) -> dict[str, Any]:
    info = capability(name)
    if not info["available"]:
        raise OptionalDependencyError(info["reason"])
    return info
