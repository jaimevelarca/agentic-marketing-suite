"""Agent 5.1 — Campaign Launcher: offline, self-contained tests.

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

from agents.layer5.campaign_launcher import AGENT, Agent51, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "5.1.txt").read_text(encoding="utf-8")
BLOCK = "ad_campaign_log"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "5.1"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 16000
    assert AGENT.prompt_asset == "agents/layer5/prompts/campaign_launcher_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "ad_campaign_log" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "FINANCIAL AUTHORIZATION GATE SUMMARY" in out["output_3"]


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


def test_financial_auth_never_self_authorizes():
    # The single most important invariant: this agent never spends or authorizes.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    assert obj["gate_status"] == "pending_review"
    assert obj["gate_status"] not in ("approved", "auto_approved")
    auth = obj["authorization"]
    assert auth["status"] == "awaiting_authorization"
    assert auth["requires_human_authorization"] is True
    assert auth["authorized_by"] is None
    assert auth["authorized_at"] is None


def test_budget_reconciliation_foots():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    recon = obj["budget_reconciliation"]
    # Planned spend never exceeds the authorized envelope; unallocated >= 0.
    assert recon["total_planned_spend_usd"] <= recon["authorized_paid_budget_usd"]
    assert recon["unallocated_usd"] >= 0
    assert (
        recon["unallocated_usd"]
        == recon["authorized_paid_budget_usd"] - recon["total_planned_spend_usd"]
    )
    # Per-platform planned spend sums to total planned spend.
    assert sum(recon["by_platform_usd"].values()) == recon["total_planned_spend_usd"]
    # Per-platform spend matches each platform campaign's budget.
    by_platform = {}
    for pc in obj["platform_campaigns"]:
        by_platform[pc["platform"]] = by_platform.get(pc["platform"], 0) + pc["campaign_budget_usd"]
    assert by_platform == recon["by_platform_usd"]
    # The money at stake equals the (monthly) planned spend.
    assert obj["authorization"]["total_amount_at_stake_usd"] == recon["total_planned_spend_usd"]
    assert obj["currency"] == "USD"


def test_conversion_ad_sets_point_at_a_landing_page():
    # Every conversion/leads ad set must reference an approved landing page.
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for pc in obj["platform_campaigns"]:
        for ad_set in pc["ad_sets"]:
            if ad_set["optimization_goal"] in ("leads", "conversions"):
                refs = [c.get("landing_page_ref") for c in ad_set["creatives"]]
                assert any(refs), (
                    f"ad set {ad_set['ad_set_id']} optimizes for "
                    f"{ad_set['optimization_goal']} but has no landing_page_ref"
                )


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "campaign_registry": {"campaigns": [{"campaign_id": "cmp-edu-convocatoria-ago", "budget_usd": 600}]},
        "active_strategy": {"big": "y" * 30000},  # forces truncation path
        "copy_assets": {"assets": [{"asset_id": "cpy-acme-co-01"}]},
        "page_assets": {"pages": [{"page_id": "lp-admisiones-agosto"}]},
    }
    turn = Agent51(
        agent_id="5.1",
        prompt_asset="agents/layer5/prompts/campaign_launcher_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "campaign_registry" in turn
    assert "page_assets" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_build_user_turn_flags_missing_required_and_optional():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUT" in turn
    assert "campaign_registry" in turn
    # active_strategy and page_assets absent → soft notes, not blockers
    assert "active_strategy not provided" in turn
    assert "page_assets not provided" in turn


def test_run_routes_to_ad_campaign_log_block(monkeypatch):
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
    res = run({"client_id": "acme-co", "campaign_registry": {}, "copy_assets": {}})
    assert res.valid is True
    assert routed["block"] == ("acme-co", BLOCK, "pending_review")
    assert routed["review"]["agent"] == "5.1"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
