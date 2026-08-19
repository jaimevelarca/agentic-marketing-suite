"""Agent 4.3 — Web + Landing Pages: offline, self-contained tests.

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

from agents.layer4.web_landing_pages import AGENT, Agent43, run  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "4.3.txt").read_text(encoding="utf-8")
BLOCK = "page_assets"


@pytest.fixture(scope="module")
def schema():
    return clients.load_schema(BLOCK)


def test_agent_wiring():
    assert AGENT.agent_id == "4.3"
    assert AGENT.schema_name == BLOCK
    assert AGENT.memory_block == BLOCK
    assert AGENT.max_tokens == 32000   # raised from 16000 (large landing-page specs truncated on real data)
    assert AGENT.prompt_asset == "agents/layer4/prompts/web_landing_pages_system.txt"


def test_split_outputs_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "page_assets" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "HUMAN REVIEW GATE SUMMARY" in out["output_3"]


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


def test_summary_foots_to_pages_and_sections():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    pages = obj["pages"]
    sections = [s for p in pages for s in p["sections"]]
    variants = [t for p in pages for t in p.get("ab_tests", [])]
    reused = [s for s in sections if s.get("source_copy_ref")]
    assert obj["summary"]["total_pages"] == len(pages)
    assert obj["summary"]["total_sections"] == len(sections)
    assert obj["summary"]["total_variants"] == len(variants)
    assert obj["summary"]["reused_copy_refs"] == len(reused)
    by_goal = {}
    for p in pages:
        by_goal[p["goal"]] = by_goal.get(p["goal"], 0) + 1
    assert obj["summary"]["pages_by_goal"] == by_goal


def test_each_page_has_single_primary_cta_and_consent_field():
    obj = AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])
    for page in obj["pages"]:
        form = page["form"]
        # exactly one primary CTA per page
        assert "primary_cta" in form and form["primary_cta"]["label"]
        # a required consent/checkbox field is present (data_privacy)
        consent = [f for f in form["fields"] if f["type"] == "checkbox" and f["required"]]
        assert consent, f"page {page['page_id']} missing a required consent checkbox"


def test_build_user_turn_injects_blocks_and_truncates():
    payload = {
        "client_id": "acme-co",
        "campaign_registry": {"campaigns": [{"campaign_id": "cmp-edu-convocatoria-ago"}]},
        "audience_segments": {"big": "y" * 30000},  # forces truncation path
        "copy_assets": {"assets": [{"id": "copy-hero-convocatoria-ago"}]},
    }
    turn = Agent43(
        agent_id="4.3",
        prompt_asset="agents/layer4/prompts/web_landing_pages_system.txt",
        schema_name=BLOCK,
        memory_block=BLOCK,
    ).build_user_turn(payload)
    assert "campaign_registry" in turn
    assert "copy_assets" in turn
    assert "[truncated]" in turn
    assert "MISSING REQUIRED INPUT" not in turn


def test_build_user_turn_flags_missing_required_and_copy():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "MISSING REQUIRED INPUT" in turn
    assert "campaign_registry" in turn
    # copy_assets absent → soft note, not a blocker
    assert "copy_assets not provided" in turn


def test_run_routes_to_page_assets_block(monkeypatch):
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
    assert routed["review"]["agent"] == "4.3"
    assert routed["review"]["priority"] == "normal"  # pending_review is not urgent
