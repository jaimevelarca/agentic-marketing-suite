"""Offline tests for Agent 1.2 — Audience Intelligence.

Self-contained: inserts suite/ on sys.path (like test_base_agent.py), stubs all
network/DB clients via monkeypatch, and validates the fixture against the
`audience_segments` JSON Schema. No GCP access or Anthropic EULA required.

Run: `pytest -q` from repo root in the project venv (jsonschema + pytest).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

# Make `import agents...` / `import infra...` resolve to the suite/ package.
ROOT = pathlib.Path(__file__).resolve().parents[2]
SUITE = ROOT / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer1 import audience_intelligence as a12  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "1.2.txt").read_text(encoding="utf-8")
BLOCK = "audience_segments"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


# (a) split_outputs yields three sections in order
def test_split_outputs_three_sections():
    out = a12.AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "audience_segments JSON" in out["output_1"]
    assert "Segment Narratives" in out["output_2"]
    assert "HUMAN GATE SUMMARY" in out["output_3"]


# (b) extract_json(OUTPUT-1) is a dict with client_id (object, not bare array)
def test_extract_json_is_object_with_client_id():
    out = a12.AGENT.split_outputs(FIXTURE)
    obj = a12.AGENT.extract_json(out["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert obj["gate_status"] == "pending_review"
    assert "created_at" in obj
    assert isinstance(obj["segments"], list) and 3 <= len(obj["segments"]) <= 5
    # Ordered by priority: index 0 is rank 1.
    assert obj["segments"][0]["priority_rank"] == 1


# (c) the fixture's OUTPUT-1 validates against the loaded schema
def test_fixture_output1_validates(schema):
    import jsonschema
    out = a12.AGENT.split_outputs(FIXTURE)
    obj = a12.AGENT.extract_json(out["output_1"])
    jsonschema.validate(obj, schema)  # raises on failure


# (d) the schema itself is a valid JSON Schema
def test_schema_is_valid_jsonschema(schema):
    import jsonschema
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)


def test_schema_rejects_bare_array(schema):
    # Guards the DEL-11 array→object conversion: a bare array must NOT validate.
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate([], schema)


def test_schema_rejects_too_few_segments(schema):
    import jsonschema
    bad = {
        "client_id": "acme-co",
        "created_at": "2026-05-29T00:00:00Z",
        "gate_status": "pending_review",
        "segments": [],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


# (e) mocked run(): canned fixture + stubbed routing → valid, routed to the block
def test_run_routes_to_audience_segments_block(monkeypatch):
    monkeypatch.setattr(a12.AGENT, "call", lambda turn: FIXTURE)

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
        lambda topic, payload: routed.setdefault("publish", (topic, payload)) or "stub",
    )

    res = a12.run({"client_id": "acme-co",
                   "client_profile": {"gate_status": "approved", "client_id": "acme-co"}})

    assert res.valid is True
    assert res.error is None
    cid, block, gate = routed["block"]
    assert cid == "acme-co"
    assert block == BLOCK
    assert gate == "pending_review"
    # review doc went to the queue at normal priority (gate is pending, not blocked)
    assert routed["review"]["agent"] == "1.2"
    assert routed["review"]["priority"] == "normal"
    # layer-handoff announced with the segment count
    topic, payload = routed["publish"]
    assert payload["block"] == BLOCK
    assert payload["segment_count"] == 3


def test_build_user_turn_injects_profile_and_tolerates_missing_inputs():
    turn = a12.AGENT.build_user_turn({
        "client_id": "acme-co",
        "client_profile": {"client_id": "acme-co", "gate_status": "approved"},
    })
    assert "Approved client_profile" in turn
    # optional sources are present as explicit "Not available." rather than crashing
    assert "CRM Export" in turn
    assert "Not available." in turn
    assert "three required outputs" in turn
