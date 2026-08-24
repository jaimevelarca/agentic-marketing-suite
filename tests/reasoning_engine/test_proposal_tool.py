from __future__ import annotations

import pytest

from infra import clients
from suite.reasoning_engine import tools
from suite.reasoning_engine.engine import MarketingSuiteReasoningEngine


@pytest.fixture(autouse=True)
def clean_memory_store():
    clients.reset_memory_store()
    yield
    clients.reset_memory_store()


def test_compile_client_proposal_tool():
    clients.write_memory_block(
        "test-client",
        "client_profile",
        {
            "name": "Empresa Demo",
            "usp": "Calidad demostrada",
            "description": "Servicios de tecnología empresarial.",
        },
        gate_status="approved",
    )
    res = tools.compile_client_proposal("test-client")
    assert res["client_id"] == "test-client"
    assert res["client_name"] == "Empresa Demo"
    assert res["status"] == "ready"
    assert "Plan_EmpresaDemo_QHHE_" in res["presentation_filename"]
    assert "Detalle_EmpresaDemo_QHHE_" in res["detail_filename"]
    assert res["presentation_size_chars"] > 1000
    assert res["detail_size_chars"] > 1000


def test_reasoning_engine_query_proposal_routing():
    clients.write_memory_block(
        "alonso-corp",
        "client_profile",
        {
            "name": "Alonso Corp",
            "usp": "Certeza y asesoría especializada.",
        },
        gate_status="approved",
    )
    engine = MarketingSuiteReasoningEngine()
    resp = engine.query("Compila la propuesta ejecutiva y la presentación", client_id="alonso-corp")
    assert "compile_client_proposal" in resp["tools_invoked"]
    proposal_res = resp["tool_data"]["compile_client_proposal"]
    assert proposal_res["client_id"] == "alonso-corp"
    assert proposal_res["client_name"] == "Alonso Corp"
    assert "Propuesta Generada" in resp["response"]
