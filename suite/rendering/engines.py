"""Model routing and human-facing engine labels for Vertex AI image generation.

Single source of truth for Flash/Pro image tier routing:
- Assets with baked-in text OR carousels -> Nano Banana Pro (Gemini 3 Pro Image)
- Photoreal assets with no text -> Nano Banana (Gemini 3.1 Flash Image)
"""
from __future__ import annotations

import os
from typing import Any

# Env-overridable model IDs
FLASH_MODEL = os.environ.get("NB_FLASH_MODEL", "gemini-3.1-flash-image")
PRO_MODEL = os.environ.get("NB_PRO_MODEL", "gemini-3.1-pro-preview")

# Standard list pricing estimates per generated image (USD)
PRICE: dict[str, float] = {
    FLASH_MODEL: 0.04,
    PRO_MODEL: 0.20,
    "gemini-2.5-flash-image": 0.04,
    "gemini-3-pro-image-preview": 0.20,
}

# Human-facing labels in es-MX (sin anglicismos, Nano Banana = nombre de producto)
_LABELS: dict[str, str] = {
    FLASH_MODEL: "Nano Banana (Gemini 3.1 Flash Image · Vertex AI)",
    PRO_MODEL: "Nano Banana Pro (Gemini 3.1 Pro Image · Vertex AI)",
    "gemini-2.5-flash-image": "Nano Banana (Gemini 2.5 Flash Image · Vertex AI)",
    "gemini-3-pro-image-preview": "Nano Banana Pro (Gemini 3 Pro Image · Vertex AI)",
}


def tier_for(asset: dict[str, Any]) -> str:
    """Pro for anything text-heavy (baked-in text OR carousel format); Flash otherwise."""
    if asset.get("in_image_text") or asset.get("asset_type") == "carousel" or asset.get("slides"):
        return PRO_MODEL
    return FLASH_MODEL


def label_for_model(model: str) -> str:
    """Return Spanish human label for a concrete model ID."""
    return _LABELS.get(model, f"Nano Banana ({model} · Vertex AI)")


def engine_label(asset: dict[str, Any]) -> str:
    """Return human label for the engine that will actually render this asset."""
    return label_for_model(tier_for(asset))


def estimate(assets: list[dict[str, Any]]) -> float:
    """Calculate rough render cost in USD for a list of visual assets."""
    total = 0.0
    for a in assets:
        if a.get("asset_type") == "carousel" or a.get("slides"):
            slides = a.get("slides") or []
            slide_count = len(slides) if slides else 1
            total += slide_count * PRICE.get(PRO_MODEL, 0.20)
        else:
            total += PRICE.get(tier_for(a), 0.04)
    return round(total, 2)
