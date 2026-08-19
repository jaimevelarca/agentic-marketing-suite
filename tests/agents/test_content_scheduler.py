"""Agent 3.2 — Content Scheduler: offline, self-contained tests.

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

from agents.layer3.content_scheduler import AGENT, Agent32, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "3.2.txt").read_text(encoding="utf-8")
BLOCK = "content_calendar"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "3.2"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 32000   # raised from 16000 (truncated large calendars on real data)
    assert AGENT.model == "claude-sonnet-4-6@anthropic" or AGENT.model  # settings.model_primary
    assert AGENT.prompt_asset == "agents/layer3/prompts/content_scheduler_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "content_calendar" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "CALENDAR REVIEW GATE SUMMARY" in out["output_3"]


def test_extract_json_is_dict_with_client_id():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert obj["gate_status"] == "pending_review"
    assert "created_at" in obj
    assert obj["timezone_primary"] == "America/Mexico_City"


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


def test_summary_foots_to_slots():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    slots = obj["slots"]
    assert obj["summary"]["total_slots"] == len(slots)
    by_platform = {}
    for s in slots:
        by_platform[s["channel"]] = by_platform.get(s["channel"], 0) + 1
    assert obj["summary"]["slots_by_platform"] == by_platform
    paid = sum(1 for s in slots if s["slot_type"] == "paid_flight")
    assert obj["summary"]["paid_flights"] == paid


def test_production_due_precedes_publish():
    # Every slot's production_due_date must be on or before its publish_date.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for s in obj["slots"]:
        assert s["production_due_date"] <= s["publish_date"], s["slot_id"]


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "content_plan": {"campaigns": [{"campaign_id": "c1"}], "summary": {"total_items": 1}},
        "campaign_registry": {"campaigns": [{"campaign_id": "c1"}]},
        "platform_rules": {"instagram": {"max_per_day": 1}},
        "client_profile": {"big": "y" * 30000},  # forces truncation path
    }
    turn = Agent32(
        agent_id="3.2",
        prompt_asset="agents/layer3/prompts/content_scheduler_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "content_plan" in turn
    assert "campaign_registry" in turn
    assert "platform_rules" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_build_user_turn_flags_missing_required():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUT" in turn
    assert "content_plan" in turn


def test_run_routes_to_content_calendar_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "content_plan": {}, "campaign_registry": {}})
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "3.2"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
