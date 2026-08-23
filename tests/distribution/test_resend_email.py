"""Unit tests for Resend Email & Messaging distribution adapter."""
import pytest
from infra import clients
from suite.distribution.financial_gate import FinancialAuthorizationError
from suite.distribution.resend_email import ResendEmailClient


@pytest.fixture(autouse=True)
def clean_memory():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_resend_send_campaign_dry_run():
    client = ResendEmailClient(mode="dry_run")
    res = client.send_campaign(
        client_id="alonso-y-cia",
        subject="Reporte Mensual Inmobiliario Q3",
        html_body="<h1>Tendencias del mercado</h1>",
        audience_segment="directores_inmobiliarios",
        recipients_count=450,
    )
    assert res["status"] == "simulated"
    assert res["mode"] == "dry_run"
    assert res["client_id"] == "alonso-y-cia"
    assert res["platform"] == "resend"
    assert res["subject"] == "Reporte Mensual Inmobiliario Q3"
    assert res["recipients_count"] == 450


def test_resend_send_nurture_step_dry_run():
    client = ResendEmailClient(mode="dry_run")
    res = client.send_nurture_step(
        client_id="ceneval",
        recipient="aspirante@ejemplo.com",
        subject="Paso 1: Guía de preparación para tu examen",
        html_body="<p>Descarga tu guía aquí</p>",
        step_number=1,
    )
    assert res["status"] == "simulated"
    assert res["recipient"] == "aspirante@ejemplo.com"
    assert res["step_number"] == 1
    assert res["message_id"].startswith("resend_msg_")


def test_resend_fetch_metrics():
    client = ResendEmailClient()
    res = client.fetch_email_metrics("alonso-y-cia", campaign_id="camp_01")
    assert res["platform"] == "resend"
    assert res["client_id"] == "alonso-y-cia"
    m = res["metrics"]
    assert m["delivery_rate"] > 0.95
    assert m["open_rate"] > 0.30
    assert m["click_to_open_rate"] > 0.15


def test_resend_live_mode_blocked_without_financial_authorization():
    client = ResendEmailClient(mode="live")
    # Client has unapproved active_strategy
    clients.write_memory_block(
        "alonso-y-cia",
        "active_strategy",
        {"strategic_thesis": "Test"},
        gate_status="pending_review",
    )
    with pytest.raises(FinancialAuthorizationError):
        client.send_campaign(
            client_id="alonso-y-cia",
            subject="Test Blocked",
            html_body="<p>Blocked</p>",
            dry_run=False,
        )
