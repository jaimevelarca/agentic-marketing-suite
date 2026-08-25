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


SESSION = {
    "id": "run-1", "client_id": "acme-co", "auto_approve": False,
    "blocks": ["client_profile"], "pending": ["audience_segments"],
    "transcript": [{"agent": "1.1", "name": "Business Diagnostics", "layer": "L1",
                    "gate": "review", "gate_status": "approved", "valid": True, "error": None}],
    "status": "en pausa (compuerta humana)", "paused": True,
}


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
