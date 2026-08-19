"""Agent 5.3 — Lead Capture + Nurture: offline, self-contained tests.

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

from agents.layer5.lead_capture_nurture import AGENT, Agent53, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "5.3.txt").read_text(encoding="utf-8")
BLOCK = "lead_register"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "5.3"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer5/prompts/lead_capture_nurture_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "lead_register" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "CONDITIONAL GATE SUMMARY" in out["output_3"]


def test_extract_json_is_dict_with_client_id():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert obj["gate_status"] == "auto_approved"
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


def test_summary_foots_to_leads():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    leads = obj["leads"]
    assert obj["summary"]["total_leads"] == len(leads)

    by_temp = {}
    for ld in leads:
        by_temp[ld["temperature"]] = by_temp.get(ld["temperature"], 0) + 1
    assert obj["summary"]["by_temperature"] == by_temp

    by_routing = {}
    for ld in leads:
        by_routing[ld["routing"]] = by_routing.get(ld["routing"], 0) + 1
    assert obj["summary"]["by_routing"] == by_routing

    enrolled = [ld for ld in leads if ld.get("enrolled_flow_id")]
    assert obj["summary"]["enrolled_count"] == len(enrolled)


def test_conditional_gate_hot_leads_do_not_block():
    # The defining rule: hot leads are flagged but the routine batch stays
    # auto_approved (conditional gate, not review gate).
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert obj["gate_status"] == "auto_approved"
    hot = obj["hot_leads_for_human"]
    assert len(hot) >= 1
    assert obj["summary"]["hot_count"] == len(hot)
    # Every flagged hot lead is actually routed to a human and not drip-enrolled.
    hot_ids = {h["lead_id"] for h in hot}
    for ld in obj["leads"]:
        if ld["lead_id"] in hot_ids:
            assert ld["temperature"] == "hot"
            assert ld["routing"] == "human_followup"
            assert ld.get("enrolled_flow_id") is None


def test_score_breakdown_components_sum_to_score():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for ld in obj["leads"]:
        bd = ld.get("score_breakdown")
        if bd:
            assert sum(bd.values()) == ld["score"]


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "inbound_leads": [{"email": "a@b.mx", "company": "Colegio X"}],
        "audience_segments": {"segments": [{"segment_id": "seg-acme-co-01"}]},
        "message_flows": {"big": "y" * 30000},  # forces truncation path
    }
    turn = Agent53(
        agent_id="5.3",
        prompt_asset="agents/layer5/prompts/lead_capture_nurture_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "inbound_leads" in turn
    assert "audience_segments" in turn
    assert "message_flows" in turn
    assert "[truncated]" in turn
    assert "NO INBOUND LEADS" not in turn
    assert "MESSAGE_FLOWS NOT PROVIDED" not in turn


def test_build_user_turn_flags_no_inbound_leads():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "NO INBOUND LEADS" in turn
    assert "blocked" in turn


def test_build_user_turn_flags_missing_message_flows():
    # Leads present but no message_flows → degrade to pending_review path.
    payload = {
        "client_id": "acme-co",
        "inbound_leads": [{"email": "a@b.mx"}],
        "audience_segments": {"segments": []},
    }
    turn = AGENT.build_user_turn(payload)
    assert "MESSAGE_FLOWS NOT PROVIDED" in turn
    assert "pending_review" in turn
    assert "NO INBOUND LEADS" not in turn


def test_run_routes_to_lead_register_block(monkeypatch):
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
        "inbound_leads": [{"email": "a@b.mx"}],
        "audience_segments": {"segments": []},
        "message_flows": {"flows": []},
    })
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "auto_approved")
    assert routed["review"]["agent"] == "5.3"
    assert routed["review"]["priority"] == "normal"  # auto_approved is not urgent
