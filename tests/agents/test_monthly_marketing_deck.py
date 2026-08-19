"""Agent 3.1 — Monthly Marketing Deck: offline, self-contained tests.

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

from agents.layer3.monthly_marketing_deck import AGENT, Agent31, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "3.1.txt").read_text(encoding="utf-8")
BLOCK = "content_plan"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "3.1"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 32000
    assert AGENT.prompt_asset == "agents/layer3/prompts/monthly_marketing_deck_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "content_plan" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "EDITORIAL REVIEW GATE SUMMARY" in out["output_3"]


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


def test_summary_foots_to_items():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    items = [it for c in obj["campaigns"] for w in c["weeks"] for it in w["items"]]
    assert obj["summary"]["total_items"] == len(items)
    assert obj["summary"]["campaigns_covered"] == len(obj["campaigns"])
    by_stage = {}
    for it in items:
        by_stage[it["funnel_stage"]] = by_stage.get(it["funnel_stage"], 0) + 1
    assert obj["summary"]["items_by_funnel_stage"] == by_stage


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "active_strategy": {"objectives": ["x"], "pillars": ["ROI medible"]},
        "campaign_registry": {"campaigns": [{"campaign_id": "c1"}]},
        "audience_segments": {"big": "y" * 30000},  # forces truncation path
        "trend_signals": {"signals": []},
    }
    turn = Agent31(
        agent_id="3.1",
        prompt_asset="agents/layer3/prompts/monthly_marketing_deck_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "active_strategy" in turn
    assert "campaign_registry" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUTS" not in turn


def test_build_user_turn_flags_missing_required():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUTS" in turn
    assert "active_strategy" in turn
    assert "campaign_registry" in turn


def test_run_routes_to_content_plan_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "active_strategy": {}, "campaign_registry": {}})
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "3.1"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
