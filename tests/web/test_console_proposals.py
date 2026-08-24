"""Tests for proposal compilation, viewing, and downloading via the Django review console."""
from __future__ import annotations

import pytest

pytest.importorskip("django")

from console import services
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def operator(db):
    return User.objects.create_user("jaime_test", password="clave-de-prueba")


@pytest.fixture
def web(operator):
    c = Client()
    c.login(username="jaime_test", password="clave-de-prueba")
    return c


def test_get_client_proposal_service():
    html_deck, filename_deck = services.get_client_proposal("acme", doc_type="deck")
    assert "<!DOCTYPE html>" in html_deck
    assert "Plan_" in filename_deck
    assert filename_deck.endswith(".html")

    html_detail, filename_detail = services.get_client_proposal("acme", doc_type="detail")
    assert "<!DOCTYPE html>" in html_detail
    assert "Detalle_" in filename_detail
    assert filename_detail.endswith(".html")


def test_proposal_view_deck_endpoint(web):
    resp = web.get("/propuestas/acme/deck/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/html")
    content = resp.content.decode("utf-8")
    assert "Plan de Marketing" in content
    assert 'id="acto-0"' in content


def test_proposal_view_detail_endpoint(web):
    resp = web.get("/propuestas/acme/detail/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/html")
    content = resp.content.decode("utf-8")
    assert "Anexo de Detalle Ejecutivo" in content


def test_proposal_download_endpoint(web):
    resp = web.get("/propuestas/acme/deck/descargar/")
    assert resp.status_code == 200
    assert "attachment; filename=" in resp["Content-Disposition"]
    assert resp["Content-Type"].startswith("text/html")


def test_proposal_generate_endpoint(web, tmp_path, monkeypatch):
    monkeypatch.setattr(
        services,
        "compile_and_export_proposal",
        lambda cid: {
            "presentation_filename": f"Plan_{cid}_QHHE_20260824.html",
            "detail_filename": f"Detalle_{cid}_QHHE_20260824.html",
        },
    )
    resp = web.get("/propuestas/acme/generar/?volver=run-1")
    assert resp.status_code == 302
    assert resp["Location"] == "/corridas/run-1/"
