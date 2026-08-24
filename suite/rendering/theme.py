"""Brand theming and color/font configuration system for presentation decks and reports.

Strictly adheres to QHHE design tokens:
- Primary brand color (--primary)
- Accent (--accent) is strictly RESERVED for human decisions/gates (#1ebe82)
- Accent soft (--accent-soft, #e9faf3)
- Neutral gray, ink, background alternate, and danger tokens.
- Font family and typography tokens.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REQUIRED_TOP = ["name", "tagline", "footer_text", "logo"]
REQUIRED_COLORS = ["primary", "accent", "accent_soft", "gray", "bg_alt", "ink", "danger"]
REQUIRED_FONTS = ["family"]

HUMAN_GATE_ACCENT = "#1ebe82"
HUMAN_GATE_ACCENT_SOFT = "#e9faf3"

DEFAULT_THEME: dict[str, Any] = {
    "name": "Cliente",
    "tagline": "Estrategia y Crecimiento",
    "footer_text": "Plan generado por QHHE · AI Marketing Suite · Documento para revisión humana",
    "logo": "logo.svg",
    "colors": {
        "primary": "#1b2b4d",
        "accent": HUMAN_GATE_ACCENT,
        "accent_soft": HUMAN_GATE_ACCENT_SOFT,
        "gray": "#667085",
        "bg_alt": "#f4f5f8",
        "ink": "#1a2230",
        "danger": "#b3261e",
    },
    "fonts": {
        "family": "Helvetica, Arial, sans-serif",
        "regular_woff2": "",
        "bold_woff2": "",
    },
}


class ThemeError(ValueError):
    """Raised when a theme configuration is missing required keys or invalid."""



@dataclass
class Theme:
    name: str
    tagline: str
    footer_text: str
    logo: str
    colors: dict[str, str] = field(default_factory=dict)
    fonts: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tagline": self.tagline,
            "footer_text": self.footer_text,
            "logo": self.logo,
            "colors": dict(self.colors),
            "fonts": dict(self.fonts),
        }


def validate_theme_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate that the theme data contains all mandatory fields and valid colors."""
    missing = [k for k in REQUIRED_TOP if k not in data]
    colors = data.get("colors", {})
    missing += [f"colors.{k}" for k in REQUIRED_COLORS if k not in colors]
    fonts = data.get("fonts", {})
    missing += [f"fonts.{k}" for k in REQUIRED_FONTS if k not in fonts]

    if missing:
        raise ThemeError(f"theme incompleto, faltan: {', '.join(missing)}")

    # Enforce human gate accent color rule
    if colors.get("accent", "").lower() != HUMAN_GATE_ACCENT.lower():
        # Keep accent strictly reserved for human gates
        colors["accent"] = HUMAN_GATE_ACCENT

    if not colors.get("accent_soft"):
        colors["accent_soft"] = HUMAN_GATE_ACCENT_SOFT

    return data


def load_theme(source: str | Path | dict[str, Any] | None = None) -> Theme:
    """Load a theme from a TOML file path, raw TOML string, or dictionary."""
    if source is None:
        data = dict(DEFAULT_THEME)
    elif isinstance(source, (str, Path)):
        p = Path(source)
        if p.exists() and p.is_file():
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        elif isinstance(source, str) and ("[" in source or "=" in source):
            data = tomllib.loads(source)
        else:
            data = dict(DEFAULT_THEME)
            data["name"] = str(source)
    elif isinstance(source, dict):
        data = dict(source)
    else:
        raise ThemeError(f"Tipo de fuente de tema inválido: {type(source)}")

    # Merge with defaults for any missing non-critical entries
    merged: dict[str, Any] = dict(DEFAULT_THEME)
    for k, v in data.items():
        if k in ("colors", "fonts") and isinstance(v, dict):
            merged[k] = {**merged.get(k, {}), **v}
        else:
            merged[k] = v

    validated = validate_theme_dict(merged)
    return Theme(
        name=validated["name"],
        tagline=validated["tagline"],
        footer_text=validated["footer_text"],
        logo=validated["logo"],
        colors=validated["colors"],
        fonts=validated["fonts"],
        raw=validated,
    )


def derive_theme_from_profile(client_profile: dict[str, Any] | None, client_id: str = "") -> Theme:
    """Derive a customized theme from client profile memory block data."""
    theme_dict = dict(DEFAULT_THEME)
    if not client_profile:
        if client_id:
            theme_dict["name"] = client_id.replace("-", " ").title()
            theme_dict["footer_text"] = f"Plan generado por QHHE · AI Marketing Suite · Documento para revisión humana · {theme_dict['name']}"
        return load_theme(theme_dict)

    name_field = client_profile.get("name")
    if isinstance(name_field, dict):
        trade_name = name_field.get("trade") or name_field.get("legal") or client_id
    elif isinstance(name_field, str) and name_field.strip():
        trade_name = name_field.strip()
    else:
        trade_name = client_id.replace("-", " ").title() or "Cliente"

    theme_dict["name"] = trade_name
    theme_dict["tagline"] = (
        client_profile.get("tagline")
        or client_profile.get("usp")
        or client_profile.get("positioning_statement")
        or "Certeza y decisiones seguras"
    )
    theme_dict["footer_text"] = (
        f"Plan generado por QHHE · AI Marketing Suite · Documento para revisión humana · {trade_name}"
    )

    visual = client_profile.get("visual_identity") or {}
    hex_list = visual.get("top_5_hex") or []
    if hex_list:
        theme_dict["colors"]["primary"] = hex_list[0]
        if len(hex_list) > 1:
            theme_dict["colors"]["brand_secondary"] = hex_list[1]

    if visual.get("heading_font"):
        theme_dict["fonts"]["family"] = visual["heading_font"]
    elif visual.get("body_font"):
        theme_dict["fonts"]["family"] = visual["body_font"]

    logo_info = visual.get("logo") or {}
    if isinstance(logo_info, dict) and logo_info.get("url"):
        theme_dict["logo"] = logo_info["url"]

    return load_theme(theme_dict)


def theme_css(theme: Theme | dict[str, Any]) -> str:
    """Generate CSS style block with root custom properties and font definitions."""
    t = theme if isinstance(theme, Theme) else load_theme(theme)
    c, f = t.colors, t.fonts

    vars_list = [f"--{k.replace('_', '-')}: {v}" for k, v in c.items()]
    font_fam = f.get("family", "Helvetica, Arial, sans-serif")
    if "," not in font_fam and " " in font_fam:
        font_fam = f'"{font_fam}", sans-serif'
    vars_list.append(f"--font-family: {font_fam}")

    vars_css = ";\n  ".join(vars_list)
    faces = []

    for w, k in ((400, "regular_woff2"), (700, "bold_woff2")):
        font_file = f.get(k)
        if font_file:
            faces.append(
                f"@font-face {{\n"
                f"  font-family: '{f.get('family', 'CustomFont')}';\n"
                f"  font-weight: {w};\n"
                f"  src: url('assets/{font_file}') format('woff2');\n"
                f"  font-display: swap;\n"
                f"}}"
            )

    faces_css = "\n".join(faces)
    return f"<style>\n:root {{\n  {vars_css};\n}}\n{faces_css}\n</style>"
