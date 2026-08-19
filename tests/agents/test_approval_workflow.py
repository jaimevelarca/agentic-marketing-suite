"""Agent 3.3 — Approval Workflow: offline, self-contained tests.

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

from agents.layer3.approval_workflow import AGENT, Agent33, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "3.3.txt").read_text(encoding="utf-8")
BLOCK = "approval_log"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "3.3"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer3/prompts/approval_workflow_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "approval_log" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "REVIEW QUEUE SUMMARY" in out["output_3"]


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


def test_summary_foots_to_entries():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    entries = obj["entries"]
    s = obj["summary"]
    assert s["total_items"] == len(entries)
    assert s["auto_published"] == sum(1 for e in entries if e["route"] == "auto_publish")
    assert s["human_review"] == sum(1 for e in entries if e["route"] == "human_review")
    assert s["escalated"] == sum(1 for e in entries if e["route"] == "escalate")
    assert s["on_hold"] == sum(1 for e in entries if e["route"] == "hold")
    assert s["overdue"] == sum(1 for e in entries if e.get("overdue"))
    by_pri = {}
    for e in entries:
        by_pri[e["priority"]] = by_pri.get(e["priority"], 0) + 1
    for k, v in s["by_priority"].items():
        assert by_pri.get(k, 0) == v


def test_routing_invariants():
    # auto_publish items must not require human review; escalations must.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for e in obj["entries"]:
        if e["route"] == "auto_publish":
            assert e["review_required"] is False
            assert e["status"] == "auto_approved"
            assert e["reviewer_role"] == "none"
        if e["route"] == "escalate":
            assert e["review_required"] is True
            assert e["priority"] == "urgent"
        if e["route"] == "hold":
            assert e["status"] == "blocked"


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "content_calendar": {"items": [{"item_id": "i1", "channel": "instagram"}]},
        "content_plan": {"big": "y" * 30000},  # forces truncation path
        "client_profile": {"constraints": {"pricing_claims": {"response": "none"}}},
    }
    turn = Agent33(
        agent_id="3.3",
        prompt_asset="agents/layer3/prompts/approval_workflow_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "content_calendar" in turn
    assert "content_plan" in turn
    assert "[truncated]" in turn
    assert "SOURCE BLOCK FOR ROUTING: content_calendar" in turn
    assert "NO ROUTABLE INPUT" not in turn


def test_build_user_turn_flags_no_input():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "NO ROUTABLE INPUT" in turn


def test_run_routes_to_approval_log_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "content_calendar": {"items": []}})
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "auto_approved")
    assert routed["review"]["agent"] == "3.3"
    # auto_approved is not 'blocked' and the output is valid → normal priority.
    assert routed["review"]["priority"] == "normal"
