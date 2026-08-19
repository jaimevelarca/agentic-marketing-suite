"""Agent 6.2 — Client Reporting: offline, self-contained tests.

Stubs all network/DB clients (monkeypatched), so no GCP project / Anthropic
EULA is needed. Uses only pytest + jsonschema (both installed). Mirrors
tests/agents/test_base_agent.py: inserts suite/ on sys.path.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

# Make `import agents...` / `import infra...` resolve to the suite/ package.
ROOT = pathlib.Path(__file__).resolve().parents[2]
SUITE = ROOT / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer6.client_reporting import AGENT, Agent62, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "6.2.txt").read_text(encoding="utf-8")
BLOCK = "client_health_score"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "6.2"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer6/prompts/client_reporting_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "client_health_score" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "PRE-CLIENT GATE SUMMARY" in out["output_3"]


def test_extract_json_is_dict_with_client_id():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert obj["gate_status"] == "pending_review"
    assert "created_at" in obj


def test_fixture_output1_validates_against_schema(schema):
    jsonschema = pytest.importorskip("jsonschema")
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    jsonschema.validate(obj, schema)  # raises on failure


def test_schema_itself_is_valid(schema):
    jsonschema = pytest.importorskip("jsonschema")
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)  # raises if the schema is malformed


def test_schema_rejects_bare_array(schema):
    # OUTPUT-1 must be an object, never a bare array.
    jsonschema = pytest.importorskip("jsonschema")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate([], schema)


def test_health_score_is_bounded_and_banded():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    hs = obj["health_score"]
    assert 0 <= hs["composite"] <= 100
    assert hs["band"] in {"healthy", "watch", "at_risk", "critical"}
    for sub in ("kpi_attainment", "engagement", "retention_signal"):
        assert 0 <= hs["components"][sub] <= 100


def test_kpi_scorecard_lines_well_formed():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    valid_status = {"on_track", "ahead", "behind", "at_risk", "no_target", "no_data"}
    assert obj["kpi_scorecard"], "fixture should reconcile at least one KPI"
    for line in obj["kpi_scorecard"]:
        assert line["kpi"]
        assert line["status"] in valid_status
        # a missing actual must be reported as no_data, never invented
        if line["actual"] is None:
            assert line["status"] in {"no_data", "no_target"}


def test_no_internal_economics_leak_in_client_facing_outputs():
    # Confidentiality rule: client-facing OUTPUT 1 + OUTPUT 2 must not carry any
    # Acme Co. internal-economics vocabulary (COGS / margin / cost-to-serve / bonus).
    out = AGENT.split_outputs(FIXTURE)
    haystack = (out["output_1"] + out["output_2"]).lower()
    for forbidden in ("cogs", "margin", "margen", "cost-to-serve", "cost to serve",
                      "bonus", "bono de desempe", "gross profit"):
        assert forbidden not in haystack, f"leak of internal economics term: {forbidden!r}"


def test_build_user_turn_injects_required_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "performance_history": {"big": "y" * 30000},  # forces truncation path
        "active_strategy": {"kpi_contracts": {"leads_per_month": 15}},
        "client_profile": {"lifecycle_stage": "pre-launch"},
    }
    turn = Agent62(
        agent_id="6.2",
        prompt_asset="agents/layer6/prompts/client_reporting_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "performance_history" in turn
    assert "active_strategy" in turn
    assert "client_profile" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUTS" not in turn


def test_build_user_turn_flags_missing_required():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUTS" in turn
    assert "performance_history" in turn
    assert "active_strategy" in turn


def test_build_user_turn_accepts_prior_report_for_trend():
    payload = {
        "client_id": "acme-co",
        "performance_history": {"leads": 12},
        "active_strategy": {"kpi_contracts": {}},
        "prior_health_score": {"health_score": {"composite": 55}},
    }
    turn = AGENT.build_user_turn(payload)
    assert "prior_health_score" in turn
    assert "MISSING REQUIRED INPUTS" not in turn


def test_run_routes_to_client_health_score_block(monkeypatch):
    # Mock the model to return the fixture; capture routing without touching GCP.
    monkeypatch.setattr(AGENT, "call", lambda turn: FIXTURE)
    routed = {}
    monkeypatch.setattr(
        clients, "write_memory_block",
        lambda cid, block, obj, gate: routed.setdefault("block", (cid, block, gate)),
    )
    monkeypatch.setattr(
        clients, "add_review_doc",
        lambda coll, doc: routed.setdefault("review", doc),
    )
    monkeypatch.setattr(
        clients, "publish",
        lambda topic, payload: routed.setdefault("published", (topic, payload)),
    )
    res = run({
        "client_id": "acme-co",
        "performance_history": {},
        "active_strategy": {},
    })
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "6.2"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
