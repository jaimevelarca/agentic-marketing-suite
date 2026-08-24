"""Rendering and proposal compilation engine for the Agentic Marketing Suite.

Provides:
- 9-Act Interactive HTML Presentation Deck compiler (presentation_compiler)
- Executive Detail / PDF Report compiler (detail_compiler)
- High-level proposal export facade (compiler)
- Strict brand theming and CSS token generator (theme)
- Visual asset rendering with Gemini Flash/Pro image model routing (engines, service, renderer)
"""
from __future__ import annotations

from suite.rendering.compiler import compile_proposal
from suite.rendering.detail_compiler import compile_detail_report
from suite.rendering.engines import (
    FLASH_MODEL,
    PRICE,
    PRO_MODEL,
    engine_label,
    estimate,
    label_for_model,
    tier_for,
)
from suite.rendering.presentation_compiler import compile_presentation_deck
from suite.rendering.prompts import build_prompt, build_slide_prompt
from suite.rendering.renderer import (
    Renderer,
    StubRenderer,
    VertexRenderer,
    get_renderer,
)
from suite.rendering.service import RenderResult, render_asset, render_slide
from suite.rendering.theme import (
    HUMAN_GATE_ACCENT,
    Theme,
    ThemeError,
    derive_theme_from_profile,
    load_theme,
    theme_css,
)

__all__ = [
    "FLASH_MODEL",
    "HUMAN_GATE_ACCENT",
    "PRICE",
    "PRO_MODEL",
    "RenderResult",
    "Renderer",
    "StubRenderer",
    "Theme",
    "ThemeError",
    "VertexRenderer",
    "build_prompt",
    "build_slide_prompt",
    "compile_detail_report",
    "compile_presentation_deck",
    "compile_proposal",
    "derive_theme_from_profile",
    "engine_label",
    "estimate",
    "get_renderer",
    "label_for_model",
    "load_theme",
    "render_asset",
    "render_slide",
    "theme_css",
    "tier_for",
]
