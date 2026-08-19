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
