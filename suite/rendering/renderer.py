"""Renderer strategies: real Vertex AI image renderer and zero-cost offline stub.

- VertexRenderer: Real Nano Banana / Gemini image generation on Vertex AI.
- StubRenderer: Clean offline placeholder generator with zero network/cost for tests & demo.
"""
from __future__ import annotations

import io
import os
import textwrap
from typing import Any, Protocol

_ASPECT_DIMS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "4:5": (1024, 1280),
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1.91:1": (1200, 628),
}


def _dims_for_aspect(aspect: str) -> tuple[int, int]:
    return _ASPECT_DIMS.get(aspect, (1024, 1024))


class Renderer(Protocol):
    def render(self, model: str, prompt: str, aspect: str = "1:1") -> tuple[bytes, Any]:
        ...


class StubRenderer:
    """Offline placeholder generator — zero network, zero cost, completely safe for tests."""

    def render(self, model: str, prompt: str, aspect: str = "1:1") -> tuple[bytes, str]:
        w, h = _dims_for_aspect(aspect)
        try:
            from PIL import Image, ImageDraw

            im = Image.new("RGB", (w, h), (27, 43, 77))  # Navy #1b2b4d
            d = ImageDraw.Draw(im)
            header = f"[render de prueba · QHHE]\n{model}\n{aspect}"
            d.multiline_text((32, 32), header, fill=(245, 245, 240), spacing=8)
            first_line = prompt.strip().splitlines()[0] if prompt.strip() else "Visual render"
            snippet = "\n".join(textwrap.wrap(first_line, width=42)[:8])
            d.multiline_text((32, 160), snippet, fill=(201, 168, 76), spacing=6)  # Gold
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return buf.getvalue(), "stub_pil"
        except ImportError:
            # Fallback SVG/PNG representation when Pillow is not installed
            first_line = prompt.strip().splitlines()[0] if prompt.strip() else "Visual render"
            safe_text = first_line[:100].replace("<", "&lt;").replace(">", "&gt;")
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                f'<rect width="100%" height="100%" fill="#1b2b4d"/>'
                f'<text x="32" y="60" fill="#f5f5f0" font-family="sans-serif" font-size="24" font-weight="bold">[render de prueba · QHHE]</text>'
                f'<text x="32" y="100" fill="#667085" font-family="sans-serif" font-size="18">{model} ({aspect})</text>'
                f'<text x="32" y="160" fill="#c9a84c" font-family="sans-serif" font-size="16">{safe_text}</text>'
                f'</svg>'
            )
            return svg.encode("utf-8"), "stub_svg"


class VertexRenderer:
    """Real Vertex AI Gemini image generation."""

    def __init__(self, project: str | None = None, location: str | None = None):
        from google import genai
        self.project = project or os.environ.get("GCP_PROJECT", "agentic-marketing-suite")
        self.location = location or os.environ.get("VERTEX_LOCATION", "global")
        self._client = genai.Client(vertexai=True, project=self.project, location=self.location)

    def render(self, model: str, prompt: str, aspect: str = "1:1") -> tuple[bytes, Any]:
        from suite.rendering.vertex import generate
        return generate(self._client, model, prompt, aspect)


def get_renderer(provider: str | None = None) -> Renderer:
    """Select the active renderer strategy based on environment or explicit parameter."""
    if provider is None:
        provider = os.environ.get("SUITE_RENDER_PROVIDER")
        if provider is None:
            llm = os.environ.get("SUITE_LLM_PROVIDER", "fixture")
            provider = "stub" if llm == "fixture" else "vertex"

    if provider == "stub":
        return StubRenderer()
    return VertexRenderer()
