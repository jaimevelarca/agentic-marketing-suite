"""Unit tests for Meta Ads distribution adapter."""
import pytest
from infra import clients
from suite.distribution.financial_gate import FinancialAuthorizationError
from suite.distribution.meta_ads import MetaAdsClient


@pytest.fixture(autouse=True)
def clean_memory():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_meta_ads_create_campaign_dry_run():
    client = MetaAdsClient(mode="dry_run")
    res = client.create_campaign(
        client_id="u-storage",
        name="Camp-NoKe-Leads",
        objective="OUTCOME_LEADS",
        daily_budget_mxn=650.0,
    )
    assert res["status"] == "simulated"
    assert res["mode"] == "dry_run"
    assert res["client_id"] == "u-storage"
    assert res["platform"] == "meta_ads"
    assert "Camp-NoKe-Leads" in res["name"]
    assert res["daily_budget_mxn"] == 650.0


def test_meta_ads_create_ad_set_dry_run():
    client = MetaAdsClient(mode="dry_run")
    res = client.create_ad_set(
        client_id="u-storage",
        campaign_id="meta_camp_123456",
        name="AdSet-CDMX-PYME",
        targeting={"geo_locations": {"cities": ["Mexico City"]}},
        daily_budget_mxn=400.0,
    )
    assert res["status"] == "simulated"
    assert res["ad_set_id"].startswith("meta_adset_")
    assert res["targeting"]["geo_locations"]["cities"] == ["Mexico City"]


def test_meta_ads_create_ad_dry_run():
    client = MetaAdsClient(mode="dry_run")
    res = client.create_ad(
        client_id="u-storage",
        ad_set_id="meta_adset_123456",
        name="Ad-NoKe-Reel",
        headline="Abre tu bodega desde el celular",
        body="Sin llaves. Sin horarios. Sin complicaciones.",
        destination_url="https://u-storage.com.mx/lp-noke",
    )
    assert res["status"] == "simulated"
    assert res["ad_id"].startswith("meta_ad_")
    assert res["creative"]["headline"] == "Abre tu bodega desde el celular"
    assert res["creative"]["destination_url"] == "https://u-storage.com.mx/lp-noke"


def test_meta_ads_fetch_metrics():
    client = MetaAdsClient()
    res = client.fetch_ad_metrics(platform="meta", since="14d")
    assert res["platform"] == "meta"
    assert res["timeframe"] == "14d"
    m = res["metrics"]
    assert m["spend_mxn"] > 0
    assert m["clicks"] > 0
    assert m["leads"] > 0
    assert m["roas"] > 0


def test_meta_ads_live_mode_blocked_without_financial_authorization():
    client = MetaAdsClient(mode="live")
    # Client has unapproved ad_campaign_log
    clients.write_memory_block(
        "u-storage",
        "ad_campaign_log",
        {"authorization": {"status": "awaiting_authorization"}},
        gate_status="pending_review",
    )
    with pytest.raises(FinancialAuthorizationError):
        client.create_campaign(
            client_id="u-storage",
            name="Camp-Blocked",
            daily_budget_mxn=500.0,
            dry_run=False,
        )
