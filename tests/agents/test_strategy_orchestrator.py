"""Offline tests for Agent 2.1 — Strategy Orchestrator.

Self-contained: inserts suite/ on sys.path exactly like test_base_agent.py, uses
only pytest + jsonschema, stubs all network/DB clients, and never mutates global
settings. Validates the canonical fixture against the active_strategy schema and
exercises a mocked end-to-end run() (binding gate + the kpi_contracts split).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

# Make `import agents...` / `import infra...` resolve to the suite/ package.
ROOT = pathlib.Path(__file__).resolve().parents[2]
SUITE = ROOT / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer2 import strategy_orchestrator as so  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE_PATH = SUITE / "fixtures" / "2.1.txt"


@pytest.fixture(scope="module")
def fixture_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


# --- output parsing -----------------------------------------------------------
def test_split_outputs_yields_three_sections(fixture_text):
    out = so.AGENT.split_outputs(fixture_text)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "active_strategy" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "BINDING GATE SUMMARY" in out["output_3"]


def test_output1_is_dict_with_client_id(fixture_text):
    out = so.AGENT.split_outputs(fixture_text)
    obj = so.AGENT.extract_json(out["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert obj["created_at"] == "2026-05-29T00:00:00Z"
    assert obj["gate_status"] == "pending_review"
    # binding agent: must embed kpi_contracts and never auto-approve
    assert "kpi_contracts" in obj
    assert obj["gate_status"] != "auto_approved"


# --- schema -------------------------------------------------------------------
def test_schema_itself_is_valid_jsonschema():
    import jsonschema
    schema = clients.load_schema("active_strategy")
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)  # raises if the schema is malformed


def test_fixture_output1_validates_against_schema(fixture_text):
    import jsonschema
    out = so.AGENT.split_outputs(fixture_text)
    obj = so.AGENT.extract_json(out["output_1"])
    schema = clients.load_schema("active_strategy")
    jsonschema.validate(obj, schema)  # raises on any violation


def test_schema_rejects_empty_object():
    import jsonschema
    schema = clients.load_schema("active_strategy")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({}, schema)


# --- mocked end-to-end run() --------------------------------------------------
def test_run_routes_strategy_and_splits_kpi_contracts(monkeypatch, fixture_text):
    # Mock the model call to return the canonical fixture; capture all routing.
    monkeypatch.setattr(so.AGENT, "call", lambda turn: fixture_text)

    written: list = []
    reviews: list = []
    published: list = []
    monkeypatch.setattr(clients, "write_memory_block",
                        lambda cid, block, obj, gate: written.append((cid, block, gate)))
    monkeypatch.setattr(clients, "add_review_doc",
                        lambda coll, doc: reviews.append(doc))
    monkeypatch.setattr(clients, "publish",
                        lambda topic, payload: published.append((topic, payload)) or "ok")

    res = so.run({
        "client_id": "acme-co",
        "client_profile": {"goals": {"primary_objective": "Sign 5 pilots"}},
        "audience_segments": {"segments": [{"id": "seg-priv-edu-director"}]},
    })

    assert res.valid is True
    assert res.structured is not None
    # active_strategy is this agent's declared block
    assert so.AGENT.memory_block == "active_strategy"
    assert so.AGENT.schema_name == "active_strategy"
    # both coupled blocks were written: active_strategy + the split-out kpi_contracts
    blocks = {b for _, b, _ in written}
    assert "active_strategy" in blocks
    assert "kpi_contracts" in blocks
    # binding gate propagated, never auto-approved
    assert all(gate == "pending_review" for _, _, gate in written)
    # a review doc was opened and the binding handoff was published
    assert reviews and reviews[0]["agent"] == "2.1"
    assert any(p.get("binding") is True for _, p in published)


def test_build_user_turn_injects_present_blocks_and_flags_missing():
    turn = so.AGENT.build_user_turn({
        "client_id": "acme-co",
        "client_profile": {"goals": {"primary_objective": "x"}},
    })
    assert "UPSTREAM MEMORY BLOCK: client_profile" in turn
    # missing blocks are explicitly flagged, not silently dropped
    assert "competitive_map" in turn
    assert "not provided" in turn
