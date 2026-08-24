"""High-level rendering service for visual assets and carousel slides.

Gracefully captures render errors into the RenderResult object without crashing the batch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from suite.rendering import engines


@dataclass
class RenderResult:
    asset_id: str | None
    ok: bool
    engine_model: str
    engine_label: str
    image_bytes: bytes | None = None
    variant: Any = None
    error: str | None = None
    slide: int | None = None


def render_asset(asset: dict[str, Any], *, renderer: Any = None) -> RenderResult:
    """Render a standalone single image asset using appropriate Flash/Pro tier."""
    from suite.rendering.prompts import build_prompt
    from suite.rendering.renderer import get_renderer

    renderer = renderer or get_renderer()
    model = engines.tier_for(asset)
    label = engines.label_for_model(model)
    aid = asset.get("asset_id")
    aspect = asset.get("aspect_ratio", "1:1")

    try:
        img_bytes, variant = renderer.render(model, build_prompt(asset), aspect)
        return RenderResult(
            asset_id=aid,
            ok=True,
            engine_model=model,
            engine_label=label,
            image_bytes=img_bytes,
            variant=variant,
            error=None,
        )
    except Exception as e:  # noqa: BLE001
        return RenderResult(
            asset_id=aid,
            ok=False,
            engine_model=model,
            engine_label=label,
            image_bytes=None,
            variant=None,
            error=f"{type(e).__name__}: {e}",
        )


def render_slide(asset: dict[str, Any], slide: dict[str, Any], *, renderer: Any = None) -> RenderResult:
    """Render a single slide for a carousel asset, routed strictly to Pro tier."""
    from suite.rendering.prompts import build_slide_prompt
    from suite.rendering.renderer import get_renderer

    renderer = renderer or get_renderer()
    model = engines.PRO_MODEL  # Carousel slides always render on Pro for typography/layout
    label = engines.label_for_model(model)
    aid = asset.get("asset_id")
    aspect = asset.get("aspect_ratio", "4:5")
    slide_num = slide.get("slide")

    try:
        img_bytes, variant = renderer.render(model, build_slide_prompt(asset, slide), aspect)
        return RenderResult(
            asset_id=aid,
            ok=True,
            engine_model=model,
            engine_label=label,
            image_bytes=img_bytes,
            variant=variant,
            error=None,
            slide=slide_num,
        )
    except Exception as e:  # noqa: BLE001
        return RenderResult(
            asset_id=aid,
            ok=False,
            engine_model=model,
            engine_label=label,
            image_bytes=None,
            variant=None,
            error=f"{type(e).__name__}: {e}",
            slide=slide_num,
        )
