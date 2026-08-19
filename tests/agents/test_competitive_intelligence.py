"""Offline tests for Agent 1.3 — Competitive Intelligence.

Self-contained: inserts suite/ on sys.path exactly like test_base_agent.py, uses
only pytest + jsonschema (both installed), stubs all network/DB clients, and does
NOT mutate global settings. Guards the full contract:
  - the fixture splits into 3 OUTPUT sections,
  - OUTPUT-1 extracts to a dict with client_id,
  - that dict validates against the competitive_map schema,
  - the schema itself is a valid JSON Schema,
  - a mocked run() routes the validated block under the name "competitive_map".
"""
from __future__ import annotations

import pathlib
import sys

import pytest

# Make `import agents...` / `import infra...` resolve to the suite/ package.
SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer1 import competitive_intelligence as ci  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "1.3.txt").read_text(encoding="utf-8")


def test_fixture_splits_into_three_sections():
    out = ci.AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "competitive_map" in out["output_1"]
    assert "COMPETITIVE BRIEF" in out["output_2"]
    assert "HUMAN GATE SUMMARY" in out["output_3"]


def test_output1_extracts_to_dict_with_client_id():
    out = ci.AGENT.split_outputs(FIXTURE)
    obj = ci.AGENT.extract_json(out["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert "created_at" in obj
    assert obj["gate_status"] == "pending_review"
    assert isinstance(obj["competitors"], list)
    assert 3 <= len(obj["competitors"]) <= 8


def test_fixture_validates_against_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = clients.load_schema("competitive_map")
    obj = ci.AGENT.extract_json(ci.AGENT.split_outputs(FIXTURE)["output_1"])
    jsonschema.validate(obj, schema)  # raises on any violation


def test_schema_is_valid_jsonschema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = clients.load_schema("competitive_map")
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)  # raises if the schema itself is malformed


def test_empty_object_is_rejected_by_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = clients.load_schema("competitive_map")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({}, schema)


def test_agent_wiring():
    assert ci.AGENT.agent_id == "1.3"
    assert ci.AGENT.schema_name == "competitive_map"
    assert ci.AGENT.memory_block == "competitive_map"
    assert ci.AGENT.prompt_asset == "agents/layer1/prompts/competitive_intelligence_system.txt"
    assert ci.AGENT.max_tokens == 16000


def test_build_user_turn_anchors_and_tolerates_missing_inputs():
    # Upstream block present + raw input present.
    turn = ci.AGENT.build_user_turn({
        "client_id": "acme-co",
        "client_profile": {"industry": {"primary": "technology_consulting"}},
        "competitor_list": [{"name": "Acme Agency"}],
    })
    assert "acme-co" in turn
    assert "client_profile" in turn
    assert "Acme Agency" in turn
    # Missing upstream anchor + no raw inputs must not raise.
    turn2 = ci.AGENT.build_user_turn({"client_id": "c1"})
    assert "MISSING" in turn2


def test_run_routes_competitive_map_block(monkeypatch):
    # Mock the model to return the fixture, and stub the three routing sinks so
    # the run is fully offline and asserts the routed block name.
    monkeypatch.setattr(ci.AGENT, "call", lambda turn: FIXTURE)
    routed = {}
    monkeypatch.setattr(clients, "write_memory_block",
                        lambda cid, block, obj, gate: routed.setdefault(
                            "block", (cid, block, gate)))
    monkeypatch.setattr(clients, "add_review_doc",
                        lambda coll, doc: routed.setdefault("review", doc))
    monkeypatch.setattr(clients, "publish",
                        lambda topic, payload: routed.setdefault("published", topic))

    res = ci.run({"client_id": "acme-co",
                  "client_profile": {"industry": {"primary": "technology_consulting"}}})

    assert res.valid is True
    assert res.structured is not None
    assert routed["block"] == ("acme-co", "competitive_map", "pending_review")
    assert routed["review"]["agent"] == "1.3"
    # pending_review (not invalid, not blocked) → normal priority.
    assert routed["review"]["priority"] == "normal"
