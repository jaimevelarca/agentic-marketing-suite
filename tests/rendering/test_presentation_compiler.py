"""Unit tests for the 9-Act Presentation Deck compiler."""
from __future__ import annotations

from suite.rendering.presentation_compiler import compile_presentation_deck


def test_presentation_deck_compiler_empty_memory():
    html_out = compile_presentation_deck("test-client")
    assert "<!DOCTYPE html>" in html_out
    assert "Plan de Marketing · Test Client" in html_out
    assert 'id="acto-0"' in html_out
    assert 'id="acto-1"' in html_out
    assert 'id="acto-2"' in html_out
    assert 'id="acto-3"' in html_out
    assert 'id="acto-4"' in html_out
    assert 'id="acto-5"' in html_out
    assert 'id="acto-6"' in html_out
    assert 'id="acto-7"' in html_out
    assert 'id="acto-8"' in html_out
    assert "#1ebe82" in html_out
    assert "Ningún entregable se publica" in html_out


def test_presentation_deck_compiler_with_rich_memory():
    blocks = {
        "client_profile": {
            "name": {"trade": "Alonso y Cía"},
            "description": "Despacho de consultoría fiscal y patrimonial.",
            "usp": "Convertimos la complejidad fiscal en certeza y decisiones seguras.",
            "primary_market": "Ciudad de México",
            "target_markets": ["CDMX", "Guadalajara", "Cancún"],
            "marketing_objective": "Generar entre 8 y 12 oportunidades calificadas al mes.",
            "confirmed_budget_mxn": 50000,
        },
        "audience_segments": {
            "segments": [
                {
                    "segment_id": "seg-1",
                    "name": "Directores Financieros (CFO)",
                    "description": "Empresas medianas que buscan asesoría técnica senior.",
                },
                {
                    "segment_id": "seg-2",
                    "name": "Dueños de Empresas Familiares",
                    "description": "Empresarios en proceso de sucesión patrimonial.",
                },
                {
                    "segment_id": "seg-3",
                    "name": "Gerentes de Cumplimiento",
                    "description": "Responsables de auditoría y prevención de lavado de dinero.",
                },
            ]
        },
        "competitive_map": {
            "differentiator": "El único despacho que combina amplitud técnica con trato de socio directo.",
            "competitors": [{"name": "Big Four", "tier": "Global"}],
        },
        "active_strategy": {
            "strategic_thesis": "Concentrar presupuesto en demanda de alta intención antes de audiencias frías.",
            "messaging_pillars": [
                {"title": "Certeza ante el SAT", "description": "Cumplimiento sin sobresaltos."},
                {"title": "PLD sin miedo", "description": "Cumplir la LFPIORPI con calma."},
                {"title": "Profundidad técnica", "description": "El nivel que su empresa requiere."},
                {"title": "Legado y patrimonio", "description": "Protección a largo plazo."},
            ],
            "channel_mix": [
                {"channel": "Google Ads — Búsqueda", "rationale": "Captura de fondo de embudo."},
                {"channel": "LinkedIn / Meta Ads", "rationale": "Segmentación B2B por cargo."},
            ],
        },
        "content_calendar": {
            "cycle_weeks": 4,
            "slots": [
                {"week": 1, "channel": "Landing Page", "format": "Diagnóstico", "cta": "Solicitar diagnóstico"},
                {"week": 1, "channel": "LinkedIn", "format": "Artículo", "cta": "Descargar guía"},
            ],
        },
        "copy_assets": {
            "assets": [
                {
                    "asset_id": "copy-01",
                    "channel": "LinkedIn",
                    "format": "Artículo",
                    "body": "La LFPIORPI lleva años vigente — asegure el cumplimiento de su empresa.",
                    "cta": "Descargar guía gratuita →",
                }
            ]
        },
        "visual_assets": {
            "visuals": [
                {
                    "asset_id": "vis-01",
                    "aspect_ratio": "1:1",
                    "prompt": "Professional B2B executive photo in modern Mexico City office.",
                }
            ]
        },
        "message_flows": {
            "flows": [
                {
                    "flow_id": "flow-01",
                    "name": "Nutrición PLD",
                    "steps": [{"subject": "Confirmación de Guía", "delay": "Inmediato"}],
                }
            ]
        },
    }

    html_out = compile_presentation_deck("alonso-y-cia", memory_blocks=blocks)
    assert "Alonso y Cía" in html_out
    assert "Convertimos la complejidad fiscal en certeza" in html_out
    assert "Directores Financieros (CFO)" in html_out
    assert "Certeza ante el SAT" in html_out
    assert "Google Ads — Búsqueda" in html_out
    assert "La LFPIORPI lleva años vigente" in html_out
    assert "Professional B2B executive photo" in html_out
    assert "Nutrición PLD" in html_out
    assert "50,000 MXN" in html_out

    # Verify interactive JS functions
    assert "IntersectionObserver" in html_out
    assert "ArrowRight" in html_out
    assert "progress" in html_out
