"""Agent 4.2 — Visual Creative: offline, self-contained tests.

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

from agents.layer4.visual_creative import AGENT, Agent42, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "4.2.txt").read_text(encoding="utf-8")
BLOCK = "visual_assets"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "4.2"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer4/prompts/visual_creative_system.txt"
    assert AGENT.model == clients.settings.model_primary


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "visual_assets" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "BATCH REVIEW GATE SUMMARY" in out["output_3"]


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


def test_summary_foots_to_assets():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assets = obj["assets"]
    assert obj["summary"]["total_assets"] == len(assets)
    by_engine = {}
    for a in assets:
        by_engine[a["engine"]] = by_engine.get(a["engine"], 0) + 1
    assert obj["summary"]["by_engine"] == by_engine
    video_count = sum(1 for a in assets if a["asset_type"] == "video")
    assert obj["summary"]["video_asset_count"] == video_count
    needs_rev = sum(1 for a in assets if a["status"] == "needs_revision")
    assert obj["summary"]["needs_revision_count"] == needs_rev


def test_assets_use_only_adr04_engines():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    allowed = {"flux-2-pro", "ideogram-3.0", "kling-2.5", "runway-gen-4.5"}
    for a in obj["assets"]:
        assert a["engine"] in allowed
        for s in a.get("slides", []):
            assert s["engine"] in allowed


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "content_calendar": {"items": [{"content_item_id": "i1", "format": "reel"}]},
        "copy_assets": {"assets": [{"content_item_id": "i1", "caption": "x"}]},
        "client_profile": {"big": "y" * 30000},  # forces truncation path
    }
    turn = Agent42(
        agent_id="4.2",
        prompt_asset="agents/layer4/prompts/visual_creative_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "content_calendar" in turn
    assert "copy_assets" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_build_user_turn_flags_missing_work_queue():
    # No content_calendar and no content_plan -> the agent must flag it so the
    # model emits a blocked batch rather than inventing items.
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUT" in turn


def test_build_user_turn_accepts_content_plan_fallback():
    turn = AGENT.build_user_turn({
        "client_id": "acme-co",
        "content_plan": {"campaigns": []},
    })
    assert "content_plan" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_run_routes_to_visual_assets_block(monkeypatch):
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
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "4.2"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
