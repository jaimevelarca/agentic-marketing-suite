"""Low-level Vertex AI (google-genai) image generation call with fallback resilience.

Imports of google.genai stay inside functions so this module imports cleanly offline.
"""
from __future__ import annotations

import base64
from typing import Any


def extract_image_bytes(resp: Any) -> bytes | None:
    """Extract raw image bytes from a Gemini generate_content response."""
    for cand in (getattr(resp, "candidates", None) or []):
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline else None
            if data:
                if isinstance(data, (bytes, bytearray)):
                    return bytes(data)
                try:
                    return base64.b64decode(data)
                except Exception:  # noqa: BLE001
                    return data.encode("utf-8") if isinstance(data, str) else None
    return None


def generate(client: Any, model: str, prompt: str, aspect: str = "1:1") -> tuple[bytes, int]:
    """Execute image generation with resilient config fallbacks.

    Returns (image_bytes, variant_index).
    """
    from google.genai import types

    attempts = []
    # Variant 0: ImageConfig with aspect ratio + IMAGE modality
    try:
        attempts.append(types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect),
        ))
    except Exception:  # noqa: BLE001, S110
        pass

    # Variant 1: IMAGE modality only (aspect in prompt hint)
    try:
        attempts.append(types.GenerateContentConfig(response_modalities=["IMAGE"]))
    except Exception:  # noqa: BLE001, S110
        pass

    # Variant 2: Unconfigured call
    attempts.append(None)

    last_error: str | None = None
    for i, cfg in enumerate(attempts):
        try:
            effective_prompt = (
                prompt
                if cfg is not None and getattr(cfg, "image_config", None)
                else f"{prompt}\n\n(Aspect ratio: {aspect}.)"
            )
            resp = client.models.generate_content(
                model=model,
                contents=effective_prompt,
                config=cfg,
            )
            img = extract_image_bytes(resp)
            if img:
                return img, i
            last_error = f"variant {i}: no image bytes found in response"
        except Exception as e:  # noqa: BLE001
            last_error = f"variant {i}: {type(e).__name__}: {str(e)[:200]}"

    raise RuntimeError(last_error or "no image produced by model")
