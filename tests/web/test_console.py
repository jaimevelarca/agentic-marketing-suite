"""Consola Django — pruebas fuera de línea (services monkeypatched)."""
from __future__ import annotations

import pytest

pytest.importorskip("django")

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402

from console import services, views  # noqa: E402


@pytest.fixture
def operator(db):
    return User.objects.create_user("jaime", password="clave-de-prueba")


@pytest.fixture
def web(operator):
    c = Client()
    c.login(username="jaime", password="clave-de-prueba")
    return c


from console import block_renderers, pipeline_meta

SESSION = {
    "id": "run-1", "client_id": "acme-co", "auto_approve": False,
    "blocks": ["client_profile"], "pending": ["audience_segments"],
    "transcript": [{"agent": "1.1", "name": "Business Diagnostics", "layer": "L1",
                    "gate": "review", "gate_status": "approved", "valid": True, "error": None}],
    "status": "en pausa (compuerta humana)", "paused": True,
}
SESSION.update(pipeline_meta.build_pipeline_tree(SESSION))


def test_login_required(db):
    response = Client().get("/")
    assert response.status_code == 302
    assert "/acceso/" in response["Location"]


def test_panel_renders(web, monkeypatch):
    monkeypatch.setattr(services, "list_sessions", lambda: [
        {"id": "run-1", "client_id": "acme-co", "pending": ["audience_segments"],
         "blocks": 3, "agents_valid": 4, "last_update_time": 0}])
    response = web.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "run-1" in body and "audience_segments" in body


def test_session_detail_renders(web, monkeypatch):
    monkeypatch.setattr(services, "get_session",
                        lambda sid: SESSION if sid == "run-1" else None)
    assert web.get("/corridas/run-1/").status_code == 200
    assert web.get("/corridas/nope/").status_code == 404


def test_decide_calls_set_gate_status_with_actor(web, monkeypatch):
    calls = {}
    monkeypatch.setattr(views.services, "decide",
                        lambda cid, blk, dec, actor, note="": calls.update(
                            cid=cid, blk=blk, dec=dec, actor=actor, note=note))
    response = web.post("/clientes/acme-co/bloques/audience_segments/decidir/",
                        {"decision": "approved", "nota": "se ve bien", "volver": "run-1"})
    assert response.status_code == 302
    assert calls == {"cid": "acme-co", "blk": "audience_segments", "dec": "approved",
                     "actor": "jaime", "note": "se ve bien"}
    assert "/corridas/run-1/" in response["Location"]


def test_decide_rejects_unknown_decision(web, monkeypatch):
    def boom(*a, **k):
        raise ValueError("decisión desconocida")
    monkeypatch.setattr(views.services, "decide", boom)
    response = web.post("/clientes/acme-co/bloques/x/decidir/", {"decision": "yolo"})
    assert response.status_code == 302  # vuelve al bloque con mensaje de error


def test_nueva_starts_run(web, monkeypatch):
    started = {}
    monkeypatch.setattr(views.services, "start_run",
                        lambda cid, inputs, auto_approve, session_id: started.update(
                            cid=cid, inputs=inputs, auto=auto_approve, sid=session_id))
    response = web.post("/corridas/nueva/",
                        {"client_id": "acme-co", "inputs_json": '{"client_id": "acme-co"}'})
    assert response.status_code == 302
    assert started["cid"] == "acme-co" and started["auto"] is False
    assert started["sid"].startswith("run-")


def test_nueva_rejects_bad_json(web, monkeypatch):
    monkeypatch.setattr(views.services, "start_run", lambda *a, **k: pytest.fail("no debió iniciar"))
    response = web.post("/corridas/nueva/", {"client_id": "acme-co", "inputs_json": "{malo"})
    assert response.status_code == 200  # re-render con mensaje de error


def test_iap_header_auto_login(db, monkeypatch):
    """Verify that Google IAP email header auto-authenticates the user seamlessly."""
    monkeypatch.setattr(services, "list_sessions", lambda: [])
    c = Client()
    # Unauthenticated client with IAP header
    response = c.get("/", HTTP_X_GOOG_AUTHENTICATED_USER_EMAIL="accounts.google.com:js@qhhe.net")
    assert response.status_code == 200
    assert "_auth_user_id" in c.session


def test_email_or_username_login(db):
    """Verify that users can log in via username OR email address."""
    User.objects.create_user(username="jaime", email="js@qhhe.net", password="clave-de-prueba")
    c = Client()
    # Log in via email
    assert c.login(username="js@qhhe.net", password="clave-de-prueba") is True
    c.logout()
    # Log in via username
    assert c.login(username="jaime", password="clave-de-prueba") is True


def test_nueva_starts_run_with_structured_wizard_fields(web, monkeypatch):
    """Verify that submitting visual structured wizard fields compiles the canonical input structure."""
    started = {}
    monkeypatch.setattr(views.services, "start_run",
                        lambda cid, inputs, auto_approve, session_id: started.update(
                            cid=cid, inputs=inputs, auto=auto_approve, sid=session_id))
    
    post_data = {
        "company_name": "Alonso y Cía.",
        "client_id": "alonso-y-cia",
        "website_url": "https://alonsoycia.com.mx",
        "industry": "Seguridad Industrial y Contra Incendios",
        "offer_description": "Instalación y mantenimiento de sistemas contra incendios",
        "value_propositions": "Certificación NFPA\nAtención 24/7",
        "primary_market": "México",
        "target_customer": "Gerentes de Planta y Seguridad Industrial",
        "marketing_objective": "Generar 30 prospectos calificados por mes",
        "monthly_budget": "$35,000 MXN",
        "channels": "Meta Ads, Email Marketing, Google Ads",
        "brand_voice_tone": "professional/corporate",
        "primary_hex": "#1E3A8A",
    }
    response = web.post("/corridas/nueva/", post_data)
    assert response.status_code == 302
    assert started["cid"] == "alonso-y-cia"
    assert started["inputs"]["quick_start_form"]["company_name"] == "Alonso y Cía."
    assert started["inputs"]["quick_start_form"]["industry"] == "Seguridad Industrial y Contra Incendios"
    assert "Certificación NFPA" in started["inputs"]["scraper_output"]["value_propositions"]
    assert started["inputs"]["scraper_output"]["visual_identity"]["top_5_hex"] == ["#1E3A8A"]


def test_pipeline_meta_builds_complete_dag():
    tree = pipeline_meta.build_pipeline_tree({
        "blocks": ["client_profile", "audience_segments"],
        "pending": ["active_strategy"],
        "transcript": [{"agent": "1.1", "valid": True}, {"agent": "1.2", "valid": True}],
        "paused": True,
    })
    assert tree["total_agents"] == 19
    assert tree["total_completed"] == 2
    assert len(tree["layers"]) == 6
    assert tree["percent"] == 10
    # Layer 1 has 4 agents
    l1 = tree["layers"][0]
    assert l1["id"] == "L1"
    assert len(l1["agents"]) == 4
    # Agent 1.1 has complete mission, deliverable, handoff
    a11 = l1["agents"][0]
    assert a11["id"] == "1.1"
    assert a11["status"] == "completed"
    assert "Diagnóstico" in a11["title"]
    assert len(a11["mission"]) > 10
    assert len(a11["deliverable"]) > 10
    assert len(a11["handoff"]) > 10


def test_block_renderer_formats_deliverables():
    # Test client_profile
    cp = block_renderers.format_block_payload("client_profile", {
        "quick_start_form": {"company_name": "Hausit Studio", "industry": "Arquitectura"},
        "scraper_output": {
            "value_propositions": ["Diseño de interiores premium"],
            "visual_identity": {"top_5_hex": ["#2C3E50", "#E74C3C"]},
        },
    })
    assert cp["type"] == "client_profile"
    assert cp["company_name"] == "Hausit Studio"
    assert cp["colors"] == ["#2C3E50", "#E74C3C"]

    # Test audience_segments
    aud = block_renderers.format_block_payload("audience_segments", {
        "segments": [
            {"name": "Compradores Residenciales", "pain_points": ["Falta de tiempo"], "core_message": "Diseño sin fricción"}
        ]
    })
    assert aud["type"] == "audience_segments"
    assert aud["total_segments"] == 1
    assert aud["segments"][0]["name"] == "Compradores Residenciales"


def test_block_review_renders_human_friendly_cards(web, monkeypatch):
    sample_block = {
        "client_id": "hausit-studio",
        "block": "client_profile",
        "gate_status": "approved",
        "agent_info": pipeline_meta.find_agent_for_block("client_profile"),
        "visual": block_renderers.format_block_payload("client_profile", {
            "quick_start_form": {"company_name": "Hausit Studio", "industry": "Arquitectura y Diseño"},
            "scraper_output": {"value_propositions": ["Arquitectura residencial boutique"]},
        }),
        "payload": {"client_id": "hausit-studio"},
        "payload_json": '{"client_id": "hausit-studio"}',
    }
    monkeypatch.setattr(views.services, "block_detail", lambda cid, blk: sample_block)

    response = web.get("/clientes/hausit-studio/bloques/client_profile/")
    assert response.status_code == 200
    content = response.content.decode()
    # Check that human-friendly sections render
    assert "Hausit Studio" in content
    assert "Arquitectura y Diseño" in content
    assert "Arquitectura residencial boutique" in content
    assert "Decisión de Compuerta Humana" in content
    assert "Ver JSON Técnico Crudo" in content  # Collapsible JSON present


def test_clean_test_data_view(web, monkeypatch):
    cleaned = {"count": 0}
    monkeypatch.setattr(views.services, "clean_all_test_sessions", lambda: 5)
    response = web.post("/mantenimiento/limpiar-pruebas/")
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_block_renderer_formats_real_del17_client_profile():
    # Test real DEL-17 output shape as emitted by Agent 1.1
    del17_payload = {
        "client_id": "real-client",
        "name": {"trade": "Mi Empresa Real", "legal": "Mi Empresa Real S.A."},
        "website_url": {"primary": "https://www.miempresa.com.mx", "additional": []},
        "industry": {"primary": "technology_consulting"},
        "offers": {"description": "Consultoría especializada en marketing agéntico"},
        "usp": {"statement": "Resultados comprobados con agentes de IA autónomos"},
        "visual_identity": {"primary_colors_hex": ["#1A365D", "#1EBE82"]},
        "brand_voice_tokens": {"tokens": ["profesional", "estratégico"], "languages": ["es-MX"]},
    }
    cp = block_renderers.format_block_payload("client_profile", del17_payload)
    assert cp["type"] == "client_profile"
    assert cp["company_name"] == "Mi Empresa Real"
    assert cp["website_url"] == "https://www.miempresa.com.mx"
    assert cp["industry"] == "technology_consulting"
    assert cp["offer_description"] == "Consultoría especializada en marketing agéntico"
    assert "Resultados comprobados" in cp["value_propositions"][0]
    assert cp["colors"] == ["#1A365D", "#1EBE82"]
    assert "profesional" in cp["voice_tokens"]


def test_block_renderer_formats_content_calendar_slots_and_copy():
    # Test content_calendar with real slots schema
    cal = block_renderers.format_block_payload("content_calendar", {
        "slots": [{
            "slot_id": "s-1",
            "week": 1,
            "publish_date": "2026-09-01",
            "channel": "linkedin",
            "format": "carousel",
            "content_ref": {"topic_title": "Estrategia Agéntica", "messaging_pillar": "Innovación B2B"},
        }]
    })
    assert cal["type"] == "content_calendar"
    assert cal["total_posts"] == 1
    assert cal["posts"][0]["topic"] == "Estrategia Agéntica"
    assert cal["posts"][0]["day"] == "2026-09-01"

    # Test copy_assets with hook and primary_caption
    cpy = block_renderers.format_block_payload("copy_assets", {
        "assets": [{
            "channel": "meta_ads",
            "hook": "¿Sigues perdiendo leads?",
            "primary_caption": "Automatiza la prospección B2B con agentes inteligentes.",
            "cta": "Agenda tu diagnóstico",
            "risk_tier": "low",
        }]
    })
    assert cpy["type"] == "copy_assets"
    assert cpy["total_copies"] == 1
    assert cpy["copies"][0]["headline"] == "¿Sigues perdiendo leads?"
    assert "Automatiza la prospección" in cpy["copies"][0]["body"]


def test_block_edit_view_saves_and_approves(web, monkeypatch):
    updated = {}

    def mock_update(client_id, block, payload, decision, actor, note=""):
        updated["client_id"] = client_id
        updated["block"] = block
        updated["payload"] = payload
        updated["decision"] = decision

    monkeypatch.setattr(views.services, "update_block_payload", mock_update)

    # 1. Action = save (keep in review)
    res = web.post("/clientes/nuevo-cliente/bloques/client_profile/editar/", {
        "payload_json": '{"name": "Actualizado"}',
        "action": "save",
        "nota": "Corrección de datos",
    })
    assert res.status_code == 302
    assert updated["payload"] == {"name": "Actualizado"}
    assert updated["decision"] is None

    # 2. Action = save_and_approve
    res_approve = web.post("/clientes/nuevo-cliente/bloques/client_profile/editar/", {
        "payload_json": '{"name": "Aprobado Final"}',
        "action": "save_and_approve",
        "nota": "Aprobación con cambios",
    })
    assert res_approve.status_code == 302
    assert updated["payload"] == {"name": "Aprobado Final"}
    assert updated["decision"] == "approved"


def test_campaign_registry_trend_signals_renderers():
    # Campaign registry
    cr = block_renderers.format_block_payload("campaign_registry", {
        "campaigns": [
            {
                "name": "Campaña TOFU Q3",
                "funnel_stage": "top_of_funnel",
                "theme": "Educativo",
                "objective": "Atracción de leads",
                "channels": ["Meta Ads", "LinkedIn"],
                "messaging_pillars": ["Ahorro de costos", "Velocidad"],
                "success_metrics": [{"metric": "CPL", "target": "15", "unit": "USD"}],
            }
        ]
    })
    assert cr["type"] == "campaign_registry"
    assert cr["total_campaigns"] == 1
    assert cr["campaigns"][0]["index"] == 0
    assert cr["campaigns"][0]["name"] == "Campaña TOFU Q3"
    assert "Atracción" in cr["campaigns"][0]["funnel_stage"]
    assert "CPL: 15 USD" in cr["campaigns"][0]["metrics"]

    # Trend signals
    ts = block_renderers.format_block_payload("trend_signals", {
        "signals": [
            {
                "topic": "IA Generativa en Pymes",
                "category": "industry",
                "velocity": "exploding",
                "suggested_angle": "Automatización accesible",
            }
        ]
    })
    assert ts["type"] == "trend_signals"
    assert ts["signals"][0]["index"] == 0
    assert ts["signals"][0]["topic"] == "IA Generativa en Pymes"


def test_session_restart_from_view(web, monkeypatch):
    restart_calls = []

    def mock_restart(session_id, client_id, from_block):
        restart_calls.append((session_id, client_id, from_block))
        return True

    monkeypatch.setattr(views.services, "restart_run_from", mock_restart)
    monkeypatch.setattr(views.services, "update_block_payload", lambda **kwargs: None)

    res = web.post("/corridas/run-test-123/reiniciar-desde/audience_segments/", {
        "client_id": "test-client",
        "payload_json": '{"segments": [{"name": "Nuevo ICP"}]}',
    })
    assert res.status_code == 302
    assert len(restart_calls) == 1
    assert restart_calls[0] == ("run-test-123", "test-client", "audience_segments")




