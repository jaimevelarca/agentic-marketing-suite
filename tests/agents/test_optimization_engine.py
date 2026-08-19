"""Agent 6.3 — Optimization Engine: offline, self-contained tests.

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

from agents.layer6.optimization_engine import AGENT, Agent63, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "6.3.txt").read_text(encoding="utf-8")
BLOCK = "content_learnings"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "6.3"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.model == clients.settings.model_primary
    assert AGENT.prompt_asset == "agents/layer6/prompts/optimization_engine_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "content_learnings" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "OPTIMIZATION SUMMARY" in out["output_3"]


def test_extract_json_is_dict_with_client_id():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert "created_at" in obj
    assert obj["gate_status"] in ("auto_approved", "pending_review")


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


def test_summary_foots_to_arrays():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    actions = obj["optimization_actions"]
    reallocs = obj["budget_reallocations"]
    s = obj["summary"]
    assert s["total_actions"] == len(actions)
    assert s["auto_applied"] == sum(1 for a in actions if a["auto_apply"])
    assert s["human_required"] == sum(1 for a in actions if a["requires_human"])
    assert s["total_learnings"] == len(obj["learnings"])
    assert s["reallocations"] == len(reallocs)
    assert s["reallocations_requiring_human"] == sum(1 for r in reallocs if r["requires_human"])
    by_type = {}
    for a in actions:
        by_type[a["action_type"]] = by_type.get(a["action_type"], 0) + 1
    for k, v in s["by_action_type"].items():
        assert by_type.get(k, 0) == v


def test_action_gating_is_exclusive():
    # Exactly one of auto_apply / requires_human is true on every action.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for a in obj["optimization_actions"]:
        assert a["auto_apply"] != a["requires_human"]


def test_bounded_autonomy_20pct_line_and_gate():
    # The 20% line: any reallocation >20% of source OR any total-spend increase
    # must be requires_human; and any such item forces gate_status pending_review.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    any_human = False
    for r in obj["budget_reallocations"]:
        binding = r["pct_of_source_budget"] > 0.20 or r.get("increases_total_spend", False)
        if binding:
            assert r["requires_human"] is True
        if r["requires_human"]:
            any_human = True
    any_human = any_human or any(a["requires_human"] for a in obj["optimization_actions"])
    expected_gate = "pending_review" if any_human else "auto_approved"
    assert obj["gate_status"] == expected_gate


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "performance_history": {"campaigns": [{"id": "c1", "cpl_usd": 16.0}]},
        "content_learnings": {"big": "y" * 30000},  # forces truncation path
        "kpi_contracts": {"cpl_target_usd": 18},
        "client_profile": {"budget": {"monthly": {"max": 100}}},
    }
    turn = Agent63(
        agent_id="6.3",
        prompt_asset="agents/layer6/prompts/optimization_engine_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "performance_history" in turn
    assert "content_learnings" in turn
    assert "kpi_contracts" in turn
    assert "[truncated]" in turn
    assert "NO PERFORMANCE DATA" not in turn


def test_build_user_turn_flags_no_performance_data():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "NO PERFORMANCE DATA" in turn


def test_run_routes_to_content_learnings_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "performance_history": {"campaigns": []}})
    assert res.valid is True
    cid, block, gate = routed["block"]
    assert cid == "acme-co"
    assert block == BLOCK
    # Fixture is a pending_review (binding budget move) case.
    assert gate == "pending_review"
    assert routed["review"]["agent"] == "6.3"
    # pending_review is not 'blocked' and the output is valid → normal priority.
    assert routed["review"]["priority"] == "normal"
    # pending_review → not handed off downstream (waits for the human).
    assert "published" not in routed


def test_run_auto_approved_hands_off_downstream(monkeypatch):
    # An all-bounded (auto_approved) block should publish a handoff so the loop closes.
    auto_fixture = FIXTURE.replace(
        '"gate_status": "pending_review"', '"gate_status": "auto_approved"', 1
    )
    monkeypatch.setattr(AGENT, "call", lambda turn: auto_fixture)
    routed = {}
    monkeypatch.setattr(clients, "write_memory_block", lambda *a: None)
    monkeypatch.setattr(clients, "add_review_doc", lambda coll, doc: None)
    monkeypatch.setattr(
        clients, "publish",
        lambda topic, payload: routed.setdefault("published", (topic, payload)),
    )
    res = run({"client_id": "acme-co", "performance_history": {"campaigns": [{"id": "c1"}]}})
    assert res.valid is True
    assert "published" in routed
    topic, payload = routed["published"]
    assert payload["block"] == BLOCK
    assert payload["from_agent"] == "6.3"
    # Only the auto_apply actions are handed off.
    assert all(a["auto_apply"] for a in payload["auto_applied_actions"])
