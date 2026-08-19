"""Agent 5.2 — Social Publisher: offline, self-contained tests.

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

from agents.layer5.social_publisher import AGENT, Agent52, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "5.2.txt").read_text(encoding="utf-8")
BLOCK = "publish_log"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "5.2"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer5/prompts/social_publisher_system.txt"
    # Haiku (routing/formatting/dispatch tier), not the primary Sonnet.
    from infra.config import settings
    assert AGENT.model == settings.model_routing


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "publish_log" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "PUBLISH SUMMARY" in out["output_3"]


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
    assert s["total_slots"] == len(entries)
    assert s["published"] == sum(1 for e in entries if e["status"] == "published")
    assert s["scheduled"] == sum(1 for e in entries if e["status"] == "scheduled")
    assert s["held"] == sum(1 for e in entries if e["status"] == "held")
    assert s["skipped"] == sum(1 for e in entries if e["status"] == "skipped")
    assert s["failed"] == sum(1 for e in entries if e["status"] == "failed")
    by_platform = {}
    for e in entries:
        if e["status"] in ("published", "scheduled") and e["platform"]:
            by_platform[e["platform"]] = by_platform.get(e["platform"], 0) + 1
    assert s["by_platform"] == by_platform


def test_publishing_invariants():
    # published/scheduled items carry a post_ref + platform + no reason; held/
    # skipped/failed carry a reason and no post_ref; paid slots are skipped, not
    # auto-published; risk-flagged copy is never published.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for e in obj["entries"]:
        if e["status"] in ("published", "scheduled"):
            assert e["post_ref"]
            assert e["platform"]
            assert e["reason"] is None
            assert e["action"] in ("publish_now", "schedule")
        if e["status"] in ("held", "skipped", "failed"):
            assert e["reason"]
            assert e["post_ref"] is None
            assert e["action"] == "none"
        if e["channel"] in ("meta_ads", "google_ads", "tiktok_ads"):
            assert e["status"] == "skipped"
            assert e["reason"] == "out_of_scope_paid_or_nonsocial"
        if e.get("reason") == "risk_flagged_needs_human":
            assert e["status"] == "held"


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "content_calendar": {"slots": [{"slot_id": "s1", "channel": "instagram"}]},
        "copy_assets": {"big": "y" * 30000},  # forces truncation path
        "visual_assets": {"assets": [{"asset_id": "v1"}]},
        "now": "2026-06-01T15:00:00Z",
    }
    turn = Agent52(
        agent_id="5.2",
        prompt_asset="agents/layer5/prompts/social_publisher_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "content_calendar" in turn
    assert "copy_assets" in turn
    assert "visual_assets" in turn
    assert "[truncated]" in turn
    assert "SOURCE BLOCK FOR PUBLISHING: content_calendar" in turn
    assert "run_timestamp (now): 2026-06-01T15:00:00Z" in turn
    assert "NO ROUTABLE INPUT" not in turn


def test_build_user_turn_flags_no_input():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "NO ROUTABLE INPUT" in turn


def test_run_routes_to_publish_log_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "content_calendar": {"slots": []}})
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "auto_approved")
    assert routed["review"]["agent"] == "5.2"
    # auto_approved is not 'blocked' and the output is valid -> normal priority.
    assert routed["review"]["priority"] == "normal"
