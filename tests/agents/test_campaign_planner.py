"""Offline unit tests for Agent 2.2 — Campaign Planner.

Self-contained: inserts suite/ on sys.path exactly like test_base_agent.py, so
no GCP project / Anthropic EULA is needed. Uses only pytest + jsonschema.

Covers:
  (a) split_outputs(fixture) yields 3 non-empty sections;
  (b) extract_json(OUTPUT-1) is a dict with client_id;
  (c) the fixture OUTPUT-1 validates against clients.load_schema("campaign_registry");
  (d) the schema itself passes jsonschema.Draft7Validator.check_schema;
  (e) a mocked run(): AGENT.call -> fixture, with write_memory_block / add_review_doc
      / publish monkeypatched, asserts res.valid and the routed block == "campaign_registry".
Also a domain sanity check that campaign budgets foot to the strategy total.
"""
from __future__ import annotations

import pathlib
import sys

import jsonschema
import pytest

# Make `import agents...` / `import infra...` resolve to the suite/ package.
SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer2.campaign_planner import AGENT, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "2.2.txt").read_text(encoding="utf-8")


def test_fixture_splits_into_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "campaign_registry" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "HUMAN GATE SUMMARY" in out["output_3"]


def test_extract_output1_is_dict_with_client_id():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert "created_at" in obj
    assert obj["gate_status"] == "pending_review"


def test_fixture_validates_against_schema():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    schema = clients.load_schema("campaign_registry")
    jsonschema.validate(obj, schema)  # raises on failure


def test_schema_is_valid_draft7():
    schema = clients.load_schema("campaign_registry")
    jsonschema.Draft7Validator.check_schema(schema)


def test_budgets_foot_to_strategy_total():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    total = obj["strategy_ref"]["total_budget_usd"]
    allocated = sum(c["budget_usd"] for c in obj["campaigns"])
    assert abs(allocated - total) <= 1
    assert obj["budget_summary"]["total_allocated_usd"] == allocated
    # each campaign's channel splits foot to its own budget
    for c in obj["campaigns"]:
        ch_sum = sum(cb["budget_usd"] for cb in c.get("channel_budget", []))
        assert abs(ch_sum - c["budget_usd"]) <= 1


def test_run_mocked_routes_to_campaign_registry(monkeypatch):
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
        "active_strategy": {"gate_status": "approved", "total_budget_usd": 600},
        "client_profile": {"industry": {"primary": "private_education"}},
        "audience_segments": {"segments": [{"id": "seg-edu-directores-mkt"}]},
        "cycle_label": "2026-Q3",
    })

    assert res.valid is True
    assert res.structured is not None
    assert routed["block"] == ("acme-co", "campaign_registry", "pending_review")
    assert routed["review"]["agent"] == "2.2"
    # pending_review (not blocked, valid) routes at normal priority
    assert routed["review"]["priority"] == "normal"


def test_build_user_turn_injects_blocks_and_truncates():
    big = {"k": "x" * 20000}
    turn = AGENT.build_user_turn({
        "client_id": "acme-co",
        "active_strategy": big,
        "cycle_label": "2026-Q3",
    })
    assert "AGENT 2.2" in turn
    assert "active_strategy" in turn
    assert "2026-Q3" in turn
    assert "[truncated]" in turn  # oversized injected block is capped


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
