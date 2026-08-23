"""Unit tests for Reasoning Engine query tools."""
import pytest
from infra import clients
from suite.reasoning_engine import tools


@pytest.fixture(autouse=True)
def clean_memory_store():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_get_client_summary_empty():
    res = tools.get_client_summary("unknown-client")
    assert res["client_id"] == "unknown-client"
    assert res["name"] == "unknown-client"
    assert res["industry"] == "No especificada"
    assert res["gate_status"] == "no_iniciado"


def test_get_client_summary_populated():
    clients.write_memory_block(
        "test-corp",
        "client_profile",
        {
            "name": {"trade": "Test Corp", "legal": "Test Corp S.A. de C.V."},
            "industry": "Fintech",
            "description": "Plataforma de créditos PYME",
            "usp": "Aprobación en 24 horas sin garantías",
            "confirmed_budget_mxn": 150000,
        },
        gate_status="approved",
    )
    res = tools.get_client_summary("test-corp")
    assert res["client_id"] == "test-corp"
    assert res["name"] == "Test Corp"
    assert res["industry"] == "Fintech"
    assert res["usp"] == "Aprobación en 24 horas sin garantías"
    assert res["monthly_budget"] == 150000
    assert res["gate_status"] == "approved"


def test_get_audience_and_competition():
    clients.write_memory_block(
        "test-corp",
        "audience_segments",
        {
            "segments": [
                {"id": "seg-01", "name": "Directores de Finanzas"},
                {"id": "seg-02", "name": "Fundadores PYME"},
            ]
        },
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-corp",
        "competitive_map",
        {
            "competitors": [{"name": "Fintech A"}, {"name": "Banco Tradicional B"}],
            "content_gaps": ["Falta de calculadoras de liquidez en tiempo real"],
        },
        gate_status="approved",
    )
    res = tools.get_audience_and_competition("test-corp")
    assert res["total_segments"] == 2
    assert res["total_competitors"] == 2
    assert len(res["content_gaps"]) == 1


def test_get_marketing_strategy():
    clients.write_memory_block(
        "test-corp",
        "active_strategy",
        {
            "strategic_thesis": "Posicionarse como la alternativa ágil a la banca tradicional",
            "messaging_pillars": ["Agilidad", "Transparencia", "Cero burocracia"],
            "channel_mix": ["linkedin", "google_ads", "email"],
            "budget_allocation": {"google_ads": 60000, "linkedin": 40000},
            "kpi_contracts": {"leads_target": 500},
        },
        gate_status="pending_review",
    )
    res = tools.get_marketing_strategy("test-corp")
    assert res["gate_status"] == "pending_review"
    assert "Posicionarse como la alternativa" in res["strategic_thesis"]
    assert len(res["messaging_pillars"]) == 3
    assert res["budget_allocation"]["google_ads"] == 60000


def test_get_content_and_campaigns():
    clients.write_memory_block(
        "test-corp",
        "campaign_registry",
        {
            "campaigns": [
                {"id": "camp-01", "name": "Lanzamiento Q3"},
                {"id": "camp-02", "name": "Evergreen Search"},
            ]
        },
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-corp",
        "content_calendar",
        {
            "cycle_weeks": 4,
            "slots": [{"day": 1, "channel": "linkedin"}, {"day": 3, "channel": "email"}],
        },
        gate_status="approved",
    )
    res = tools.get_content_and_campaigns("test-corp")
    assert res["total_campaigns"] == 2
    assert res["cycle_weeks"] == 4
    assert res["total_content_slots"] == 2


def test_get_creative_deliverables():
    clients.write_memory_block(
        "test-corp",
        "copy_assets",
        {"assets": [{"id": "copy-01", "headline": "Crédito PYME en 24h"}]},
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-corp",
        "visual_assets",
        {"visuals": [{"id": "vis-01", "format": "carousel_1x1"}]},
        gate_status="approved",
    )
    clients.write_memory_block(
        "test-corp",
        "message_flows",
        {"flows": [{"id": "flow-01", "channel": "whatsapp"}]},
        gate_status="approved",
    )
    res = tools.get_creative_deliverables("test-corp")
    assert res["copy_assets_count"] == 1
    assert res["visual_specs_count"] == 1
    assert res["message_flows_count"] == 1


def test_get_run_execution_status():
    clients.write_memory_block("test-corp", "client_profile", {"name": "Test"}, gate_status="approved")
    clients.write_memory_block("test-corp", "active_strategy", {"thesis": "Tesis"}, gate_status="pending_review")

    res = tools.get_run_execution_status("test-corp")
    assert res["total_blocks_checked"] == 12
    assert res["populated_blocks_count"] == 2
    assert "active_strategy" in res["pending_human_gates"]
    assert res["is_ready_for_review"] is True
