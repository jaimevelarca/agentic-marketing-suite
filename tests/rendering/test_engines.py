"""Unit tests for engine tier routing, labels, pricing, and prompt assembly."""
from __future__ import annotations

from suite.rendering.engines import (
    FLASH_MODEL,
    PRO_MODEL,
    engine_label,
    estimate,
    label_for_model,
    tier_for,
)
from suite.rendering.prompts import build_prompt, build_slide_prompt
from suite.rendering.renderer import StubRenderer, get_renderer
from suite.rendering.service import render_asset, render_slide


def test_engine_tier_routing():
    # Photoreal asset without text -> Flash
    asset_flash = {"asset_id": "vis-001", "prompt": "An executive portrait in office", "aspect_ratio": "1:1"}
    assert tier_for(asset_flash) == FLASH_MODEL

    # Asset with in_image_text -> Pro
    asset_pro = {
        "asset_id": "vis-002",
        "prompt": "Graphic typography poster",
        "in_image_text": "¿Su empresa cumple con la ley?",
        "aspect_ratio": "1:1",
    }
    assert tier_for(asset_pro) == PRO_MODEL

    # Carousel asset -> Pro
    asset_carousel = {
        "asset_id": "vis-003",
        "asset_type": "carousel",
        "slides": [{"slide": 1, "prompt": "Slide 1"}],
    }
    assert tier_for(asset_carousel) == PRO_MODEL


def test_engine_labels():
    lbl_flash = label_for_model(FLASH_MODEL)
    lbl_pro = label_for_model(PRO_MODEL)
    assert "Nano Banana" in lbl_flash
    assert "Nano Banana Pro" in lbl_pro

    asset = {"in_image_text": "Texto"}
    assert engine_label(asset) == lbl_pro


def test_price_estimate():
    assets = [
        {"asset_id": "v1", "aspect_ratio": "1:1"},  # Flash ($0.04)
        {"asset_id": "v2", "in_image_text": "Text"},  # Pro ($0.20)
        {"asset_id": "v3", "asset_type": "carousel", "slides": [{"slide": 1}, {"slide": 2}]},  # 2 slides on Pro ($0.40)
    ]
    total = estimate(assets)
    assert total == 0.64


def test_prompt_assembly():
    asset = {
        "prompt": "Modern office in CDMX",
        "in_image_text": "Certeza Fiscal",
        "negative_prompt": "blurry, distorted letters, cartoon",
        "aspect_ratio": "4:5",
    }
    compiled = build_prompt(asset)
    assert "Modern office in CDMX" in compiled
    assert 'Render this exact Spanish text inside the image, spelled correctly and clearly legible: "Certeza Fiscal".' in compiled
    assert "Do NOT include any of the following: blurry, distorted letters, cartoon" in compiled
    assert "full bleed, with no borders, letterboxing, or empty margins" in compiled


def test_slide_prompt_assembly():
    asset = {"prompt": "Carousel series", "aspect_ratio": "4:5", "negative_prompt": "watermarks"}
    slide = {"slide": 3, "prompt": "Slide 3 specific scene", "in_image_text": "Paso 3"}
    compiled = build_slide_prompt(asset, slide)
    assert "Slide 3 specific scene" in compiled
    assert 'Render this exact Spanish text inside the slide, spelled correctly and clearly legible: "Paso 3".' in compiled
    assert "This is ONE single slide (slide 3)" in compiled
    assert "do NOT render a grid or contact-sheet of multiple slides" in compiled


def test_stub_renderer_and_service():
    renderer = StubRenderer()
    asset = {"asset_id": "vis-test-01", "prompt": "Test asset", "aspect_ratio": "1:1"}
    res = render_asset(asset, renderer=renderer)
    assert res.ok is True
    assert res.asset_id == "vis-test-01"
    assert res.image_bytes is not None
    assert len(res.image_bytes) > 0

    # Slide render
    slide = {"slide": 1, "prompt": "Slide 1 prompt"}
    res_slide = render_slide(asset, slide, renderer=renderer)
    assert res_slide.ok is True
    assert res_slide.slide == 1
    assert res_slide.image_bytes is not None


def test_get_renderer_offline_default(monkeypatch):
    monkeypatch.setenv("SUITE_LLM_PROVIDER", "fixture")
    monkeypatch.delenv("SUITE_RENDER_PROVIDER", raising=False)
    r = get_renderer()
    assert isinstance(r, StubRenderer)
