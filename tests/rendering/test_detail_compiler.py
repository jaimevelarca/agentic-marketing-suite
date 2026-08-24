"""Unit tests for Executive Detail / PDF Report compiler and compiler facade."""
from __future__ import annotations

import tempfile
from pathlib import Path

from suite.rendering.compiler import compile_proposal
from suite.rendering.detail_compiler import compile_detail_report


def test_detail_compiler_structure():
    blocks = {
        "client_profile": {
            "name": "U-Storage",
            "description": "Líder en renta de minibodegas y soluciones de autoalmacenaje en México.",
            "usp": "Expande tu vida con espacio seguro.",
            "services": ["Minibodegas Personales", "Autoalmacenaje Empresarial", "Logística Ligera"],
            "target_markets": ["CDMX", "Puebla", "Querétaro"],
            "budget": "75,000 MXN",
        },
        "audience_segments": {
            "segments": [
                {
                    "segment_id": "icp-1",
                    "name": "Familias en Mudanza / Remodelación",
                    "description": "Personas que requieren espacio temporal seguro durante transiciones del hogar.",
                    "pain_points": ["Falta de espacio", "Seguridad de pertenencias"],
                    "preferred_channels": ["Google Search", "Meta Ads"],
                }
            ]
        },
        "content_calendar": {
            "slots": [
                {
                    "slot_id": "slot-01",
                    "week": 1,
                    "channel": "Google Ads",
                    "format": "Search Ad",
                    "theme": "Mudanza sin estrés",
                    "cta": "Cotiza tu minibodega",
                }
            ]
        },
        "copy_assets": {
            "assets": [
                {
                    "asset_id": "cp-01",
                    "channel": "Meta Ads",
                    "format": "Anuncio",
                    "headline": "¿Te falta espacio en casa?",
                    "body": "Renta una minibodega desde 1.5m² con seguridad 24/7.",
                    "cta": "Cotizar ahora",
                }
            ]
        },
    }

    report_html = compile_detail_report("u-storage", memory_blocks=blocks)
    assert "<!DOCTYPE html>" in report_html
    assert "Anexo de Detalle Ejecutivo" in report_html
    assert "U-Storage" in report_html
    assert "Expande tu vida con espacio seguro." in report_html
    assert "Minibodegas Personales" in report_html
    assert "Familias en Mudanza" in report_html
    assert "slot-01" in report_html
    assert "Cotiza tu minibodega" in report_html
    assert "cp-01" in report_html
    assert "¿Te falta espacio en casa?" in report_html
    assert "@media print" in report_html
    assert "#1ebe82" in report_html


def test_compiler_facade_export():
    with tempfile.TemporaryDirectory() as tmpdir:
        res = compile_proposal("acme-test", out_dir=tmpdir)
        assert res["client_id"] == "acme-test"
        assert res["presentation_html"]
        assert res["detail_html"]
        assert res["presentation_path"] is not None
        assert res["detail_path"] is not None

        p_deck = Path(res["presentation_path"])
        p_detail = Path(res["detail_path"])

        assert p_deck.exists()
        assert p_detail.exists()
        assert p_deck.stat().st_size > 1000
        assert p_detail.stat().st_size > 1000
