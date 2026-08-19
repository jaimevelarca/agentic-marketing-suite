"""Agent 4.4 — Email / WhatsApp: offline, self-contained tests.

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

from agents.layer4.email_whatsapp import AGENT, Agent44, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "4.4.txt").read_text(encoding="utf-8")
BLOCK = "message_flows"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "4.4"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer4/prompts/email_whatsapp_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "message_flows" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "FIRST-DEPLOY GATE SUMMARY" in out["output_3"]


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


def test_summary_foots_to_flows_and_messages():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    flows = obj["flows"]
    messages = [m for f in flows for m in f["messages"]]
    assert obj["summary"]["total_flows"] == len(flows)
    assert obj["summary"]["total_messages"] == len(messages)

    by_channel = {}
    for m in messages:
        by_channel[m["channel"]] = by_channel.get(m["channel"], 0) + 1
    assert obj["summary"]["messages_by_channel"] == by_channel

    by_stage = {}
    for f in flows:
        by_stage[f["funnel_stage"]] = by_stage.get(f["funnel_stage"], 0) + 1
    assert obj["summary"]["flows_by_funnel_stage"] == by_stage


def test_whatsapp_marketing_messages_carry_a_template():
    # Any WhatsApp MARKETING message sent outside the session window must
    # reference an approved/pending template (prompt + schema rule).
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    wa_marketing = [
        m for f in obj["flows"] for m in f["messages"]
        if m["channel"] == "whatsapp"
        and m.get("whatsapp_template")
        and m["whatsapp_template"].get("category") == "MARKETING"
    ]
    assert wa_marketing, "fixture should exercise a templated WhatsApp marketing message"
    for m in wa_marketing:
        assert m["whatsapp_template"]["template_name"]
        assert m["whatsapp_template"]["approval_status"] in {
            "pending", "submitted", "approved", "rejected", "not_required",
        }


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "audience_segments": {"segments": [{"segment_id": "seg-acme-co-01"}]},
        "content_calendar": {"big": "y" * 30000},  # forces truncation path
    }
    turn = Agent44(
        agent_id="4.4",
        prompt_asset="agents/layer4/prompts/email_whatsapp_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "audience_segments" in turn
    assert "content_calendar" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUTS" not in turn


def test_build_user_turn_accepts_content_plan_alias():
    # Layer 3 may inject the editorial content_plan under that key; it should
    # satisfy the calendar requirement (no MISSING flag).
    payload = {
        "client_id": "acme-co",
        "audience_segments": {"segments": []},
        "content_plan": {"campaigns": []},
    }
    turn = AGENT.build_user_turn(payload)
    assert "content_plan" in turn
    assert "MISSING REQUIRED INPUTS" not in turn


def test_build_user_turn_flags_missing_required():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUTS" in turn
    assert "audience_segments" in turn
    assert "content_calendar" in turn


def test_run_routes_to_message_flows_block(monkeypatch):
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
        "audience_segments": {"segments": []},
        "content_calendar": {},
    })
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "4.4"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
