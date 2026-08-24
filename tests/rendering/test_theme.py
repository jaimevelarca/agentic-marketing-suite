from __future__ import annotations

import pytest

from suite.rendering.theme import (
    HUMAN_GATE_ACCENT,
    ThemeError,
    derive_theme_from_profile,
    load_theme,
    theme_css,
    validate_theme_dict,
)


def test_default_theme_loading():
    th = load_theme()
    assert th.name == "Cliente"
    assert th.colors["accent"] == HUMAN_GATE_ACCENT
    assert "primary" in th.colors
    assert th.fonts["family"]


def test_load_theme_from_dict():
    custom = {
        "name": "Acme Corp",
        "tagline": "Innovation and Quality",
        "footer_text": "Custom Footer 2026",
        "logo": "acme.svg",
        "colors": {
            "primary": "#003366",
            "accent": "#ff0000",  # should be overridden to #1ebe82
            "accent_soft": "#e9faf3",
            "gray": "#777777",
            "bg_alt": "#f0f0f0",
            "ink": "#111111",
            "danger": "#cc0000",
        },
        "fonts": {
            "family": "Inter",
        },
    }
    th = load_theme(custom)
    assert th.name == "Acme Corp"
    assert th.colors["primary"] == "#003366"
    assert th.colors["accent"] == HUMAN_GATE_ACCENT  # strictly enforced
    assert th.fonts["family"] == "Inter"


def test_load_theme_validation_error():
    broken = {
        "name": "Broken Co",
        # missing tagline, footer_text, logo, colors, fonts
    }
    with pytest.raises(ThemeError):
        validate_theme_dict(broken)


def test_derive_theme_from_profile():
    profile = {
        "name": {"trade": "Alonso y Cía", "legal": "Alonso y Cía Consultores S.C."},
        "usp": "Certeza y decisiones seguras",
        "visual_identity": {
            "top_5_hex": ["#1b2b4d", "#c2902a"],
            "heading_font": "Montserrat",
            "logo": {"url": "alonso-logo.png"},
        },
    }
    th = derive_theme_from_profile(profile, client_id="alonso-y-cia")
    assert th.name == "Alonso y Cía"
    assert th.tagline == "Certeza y decisiones seguras"
    assert th.colors["primary"] == "#1b2b4d"
    assert th.fonts["family"] == "Montserrat"
    assert th.logo == "alonso-logo.png"


def test_derive_theme_from_empty_profile():
    th = derive_theme_from_profile(None, client_id="u-storage")
    assert th.name == "U Storage"
    assert th.colors["accent"] == HUMAN_GATE_ACCENT


def test_theme_css_generation():
    th = load_theme({
        "name": "Test Brand",
        "tagline": "Testing CSS",
        "footer_text": "Footer",
        "logo": "logo.svg",
        "colors": {
            "primary": "#123456",
            "accent": "#1ebe82",
            "accent_soft": "#e9faf3",
            "gray": "#666666",
            "bg_alt": "#f9f9f9",
            "ink": "#222222",
            "danger": "#ff3333",
        },
        "fonts": {
            "family": "Roboto",
            "regular_woff2": "roboto.woff2",
        },
    })
    css = theme_css(th)
    assert ":root {" in css
    assert "--primary: #123456" in css
    assert "--accent: #1ebe82" in css
    assert "--font-family: Roboto" in css
    assert "@font-face {" in css
    assert "src: url('assets/roboto.woff2')" in css
