"""Unit tests for MarketingSuiteReasoningEngine."""
import pytest
from infra import clients
from suite.reasoning_engine.engine import MarketingSuiteReasoningEngine


@pytest.fixture(autouse=True)
def clean_memory():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_reasoning_engine_setup():
    engine = MarketingSuiteReasoningEngine()
    assert not engine._is_setup
    engine.set_up()
    assert engine._is_setup
    assert len(engine.tools_map) == 7


def test_reasoning_engine_query_strategy_routing():
    clients.write_memory_block(
        "u-storage",
        "active_strategy",
        {
            "strategic_thesis": "Capitalizar Cerradura NoKe y Hub Storage para liderar el mercado",
            "channel_mix": ["google_ads", "meta_ads", "tiktok_ads"],
            "budget_allocation": {"google_ads": 8170, "meta_ads": 6880},
        },
        gate_status="pending_review",
    )
    engine = MarketingSuiteReasoningEngine()
    res = engine.query("¿Cuál es la estrategia y el presupuesto de U-Storage?", client_id="u-storage")

    assert res["client_id"] == "u-storage"
    assert "get_marketing_strategy" in res["tools_invoked"]
    assert "Capitalizar Cerradura NoKe" in res["response"]
    assert "pending_review" in res["response"]


def test_reasoning_engine_query_audience_routing():
    clients.write_memory_block(
        "alonso-y-cia",
        "audience_segments",
        {"segments": [{"name": "Sector Inmobiliario Industrial"}]},
        gate_status="approved",
    )
    clients.write_memory_block(
        "alonso-y-cia",
        "competitive_map",
        {"competitors": [{"name": "Competidor X"}], "content_gaps": ["Falta de comparativas de retorno"]},
        gate_status="approved",
    )
    engine = MarketingSuiteReasoningEngine()
    res = engine.query("Muéstrame los competidores y segmentos de audiencia", client_id="alonso-y-cia")

    assert res["client_id"] == "alonso-y-cia"
    assert "get_audience_and_competition" in res["tools_invoked"]
    assert "Competidores Analizados" in res["response"]


def test_reasoning_engine_query_explicit_tool():
    clients.write_memory_block(
        "ceneval",
        "client_profile",
        {"name": "CENEVAL", "industry": "Evaluación Educativa", "usp": "Evaluación confiable"},
        gate_status="approved",
    )
    engine = MarketingSuiteReasoningEngine()
    res = engine.query("Dame datos", client_id="ceneval", tool_name="get_client_summary")

    assert res["tools_invoked"] == ["get_client_summary"]
    assert "CENEVAL" in res["response"]
    assert "Evaluación Educativa" in res["response"]


def test_reasoning_engine_query_fallback_when_no_keyword_matched():
    clients.write_memory_block(
        "generic-brand",
        "client_profile",
        {"name": "Marca Genérica", "industry": "Retail"},
        gate_status="pending",
    )
    engine = MarketingSuiteReasoningEngine()
    res = engine.query("Hola, ¿qué puedes decirme?", client_id="generic-brand")

    assert "get_client_summary" in res["tools_invoked"]
    assert "get_run_execution_status" in res["tools_invoked"]
    assert "Marca Genérica" in res["response"]
