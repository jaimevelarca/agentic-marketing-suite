"""Unit tests for FastMCP platform_apis server."""
import pytest
from infra import clients
from suite.mcp_servers.server import build_platform_apis_server


@pytest.fixture(autouse=True)
def clean_memory():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_platform_apis_server_creation_and_tools():
    pytest.importorskip("mcp")
    server = build_platform_apis_server()
    assert server.name == "acme-platform-apis"


def test_platform_apis_deploy_meta_campaign_dry_run():
    pytest.importorskip("mcp")
    from suite.distribution.meta_ads import MetaAdsClient
    client = MetaAdsClient()
    res = client.create_campaign("u-storage", "Test Campaign", daily_budget_mxn=500.0, dry_run=True)
    assert res["status"] == "simulated"
    assert res["name"] == "Test Campaign"


def test_platform_apis_dispatch_email_campaign_dry_run():
    pytest.importorskip("mcp")
    from suite.distribution.resend_email import ResendEmailClient
    client = ResendEmailClient()
    res = client.send_campaign("alonso-y-cia", "Test Subject", "<p>Body</p>", dry_run=True)
    assert res["status"] == "simulated"
    assert res["subject"] == "Test Subject"


def test_platform_apis_check_financial_authorization_unapproved():
    from suite.distribution.financial_gate import verify_financial_authorization, FinancialAuthorizationError
    clients.write_memory_block(
        "test-client",
        "ad_campaign_log",
        {"authorization": {"status": "awaiting_authorization"}},
        gate_status="pending_review",
    )
    with pytest.raises(FinancialAuthorizationError):
        verify_financial_authorization("test-client", "meta_ads", 1000)


def test_platform_apis_check_financial_authorization_approved():
    from suite.distribution.financial_gate import verify_financial_authorization
    clients.write_memory_block(
        "test-client",
        "client_profile",
        {"confirmed_budget_mxn": 50000},
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-client",
        "ad_campaign_log",
        {"authorization": {"status": "authorized"}},
        gate_status="approved",
    )
    ok, msg = verify_financial_authorization("test-client", "meta_ads", 15000)
    assert ok is True
    assert "verified" in msg
