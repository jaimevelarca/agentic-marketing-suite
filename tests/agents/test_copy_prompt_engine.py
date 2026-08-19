"""Agent 4.1 — Copy + Prompt Engine: offline, self-contained tests.

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

from agents.layer4.copy_prompt_engine import AGENT, Agent41, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "4.1.txt").read_text(encoding="utf-8")
BLOCK = "copy_assets"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "4.1"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 32000   # raised from 16000 (large copy batches truncated on real data)
    assert AGENT.prompt_asset == "agents/layer4/prompts/copy_prompt_engine_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "copy_assets" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "RISK GATE SUMMARY" in out["output_3"]


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
    summary = obj["summary"]
    assert summary["total_assets"] == len(assets)

    by_channel = {}
    by_stage = {}
    by_tier = {}
    image_prompts = 0
    needs_review = 0
    for a in assets:
        by_channel[a["channel"]] = by_channel.get(a["channel"], 0) + 1
        by_stage[a["funnel_stage"]] = by_stage.get(a["funnel_stage"], 0) + 1
        by_tier[a["risk_tier"]] = by_tier.get(a["risk_tier"], 0) + 1
        image_prompts += len(a.get("image_prompts", []))
        if a["risk_tier"] in ("medium", "high"):
            needs_review += 1

    assert summary["assets_by_channel"] == by_channel
    assert summary["assets_by_funnel_stage"] == by_stage
    assert summary["assets_by_risk_tier"] == by_tier
    assert summary["total_image_prompts"] == image_prompts
    assert summary["assets_needing_review"] == needs_review


def test_gate_status_matches_risk_rollup():
    # Risk-tiered rollup: any medium/high -> pending_review (never auto_approved).
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    tiers = {a["risk_tier"] for a in obj["assets"]}
    if tiers & {"medium", "high"}:
        assert obj["gate_status"] == "pending_review"
    elif tiers == {"low"}:
        assert obj["gate_status"] == "auto_approved"


def test_image_prompts_target_only_supported_models():
    # Only fal.ai models flux-2-pro / ideogram-3.0; ideogram carries in-image text.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for a in obj["assets"]:
        for ip in a.get("image_prompts", []):
            assert ip["model_target"] in ("flux-2-pro", "ideogram-3.0")
            assert ip["aspect_ratio"] in ("9:16", "1:1", "4:5", "16:9")
            if ip["model_target"] == "flux-2-pro":
                assert ip.get("in_image_text") is None


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "content_calendar": {"items": [{"topic": "x"}]},
        "audience_segments": {"big": "y" * 30000},  # forces truncation path
        "competitive_map": {"competitors": []},
        "client_profile": {"brand_voice_tokens": {"tokens": ["professional"]}},
    }
    turn = Agent41(
        agent_id="4.1",
        prompt_asset="agents/layer4/prompts/copy_prompt_engine_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "content_calendar" in turn
    assert "audience_segments" in turn
    assert "client_profile" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_build_user_turn_accepts_content_plan_fallback():
    # content_plan (3.1 output) satisfies the driver requirement too.
    turn = AGENT.build_user_turn({
        "client_id": "acme-co",
        "content_plan": {"campaigns": []},
    })
    assert "content_plan" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_build_user_turn_flags_missing_required():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUT" in turn


def test_run_routes_to_copy_assets_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "content_calendar": {"items": [{"topic": "x"}]}})
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "4.1"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
