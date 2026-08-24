"""Prompt assembly for Nano Banana (Vertex AI Image) generation.

The English prompt drives the render backend; `negative_prompt` is folded into
natural-language exclusions, the exact Spanish `in_image_text` is pinned with
strict legibility instructions, and an anti-letterbox full-bleed directive is appended.
"""
from __future__ import annotations

from typing import Any


def build_prompt(asset: dict[str, Any]) -> str:
    """Compile full prompt for a standalone single visual asset."""
    raw_prompt = asset.get("prompt", "").strip()
    parts = [raw_prompt] if raw_prompt else []

    txt = asset.get("in_image_text")
    if txt:
        parts.append(
            f'Render this exact Spanish text inside the image, spelled correctly '
            f'and clearly legible: "{txt}".'
        )

    neg = (asset.get("negative_prompt") or "").strip()
    if neg:
        parts.append(f"Do NOT include any of the following: {neg}")

    aspect = asset.get("aspect_ratio", "1:1")
    parts.append(
        f"Compose the image to fill the entire {aspect} frame edge to edge, "
        f"full bleed, with no borders, letterboxing, or empty margins."
    )

    return "\n\n".join(parts)


def build_slide_prompt(asset: dict[str, Any], slide: dict[str, Any]) -> str:
    """Compile self-contained prompt for an individual carousel slide."""
    raw_prompt = slide.get("prompt") or asset.get("prompt", "")
    parts = [raw_prompt.strip()]

    txt = slide.get("in_image_text") or slide.get("copy")
    if txt:
        parts.append(
            f'Render this exact Spanish text inside the slide, spelled correctly '
            f'and clearly legible: "{txt}".'
        )

    neg = (asset.get("negative_prompt") or "").strip()
    if neg:
        parts.append(f"Do NOT include any of the following: {neg}")

    aspect = asset.get("aspect_ratio", "4:5")
    slide_num = slide.get("slide", 1)
    parts.append(
        f"This is ONE single slide (slide {slide_num}). Fill the entire {aspect} "
        f"frame edge to edge (full bleed); do not letterbox, do not leave empty margins, "
        f"and do NOT render a grid or contact-sheet of multiple slides."
    )

    return "\n\n".join(parts)
