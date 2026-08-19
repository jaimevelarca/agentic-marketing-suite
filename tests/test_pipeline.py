"""End-to-end pipeline integration test (offline).

Runs the whole 19-agent orchestrator with the canned per-agent fixtures and
asserts every agent produces a valid memory block and the layer milestones hold.
Provider/persistence are monkeypatched (rather than set via env) so the test is
robust to pytest's single-process frozen `settings`.

Requires the agent modules + fixtures to exist (built in Session 4).
"""
from __future__ import annotations

import sys
import pathlib
import pytest

SUITE = pathlib.Path(__file__).resolve().parents[1] / "suite"
sys.path.insert(0, str(SUITE))

from infra import clients  # noqa: E402
from orchestration.pipeline import run_pipeline, PIPELINE  # noqa: E402

SEED = {
    "quick_start_form": {"name": "Acme Co.", "objective": "5 pilot clients in 90 days"},
    "scraper_output": {"detected_offer": "Digital Marketing AI Suite"},
    "competitor_list": ["agency-x"],
    "inbound_leads": [],
}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # Route the model call to the per-agent fixture file; keep all persistence
    # in-process so no GCP/EULA is touched.
    monkeypatch.setattr(
        clients, "llm_complete",
        lambda *, model, system, user_turn, max_tokens, agent_id: clients._load_fixture(agent_id),
    )
    monkeypatch.setattr(clients, "write_memory_block", lambda cid, blk, obj, gate: None)
    monkeypatch.setattr(clients, "add_review_doc", lambda coll, doc: None)
    monkeypatch.setattr(clients, "publish", lambda topic, payload: "memory")


def test_every_agent_runs_and_is_valid():
    res = run_pipeline("acme-co", SEED, auto_approve=True)
    invalid = [t for t in res["transcript"] if not t.get("valid")]
    assert not invalid, f"agents that did not produce a valid block: {invalid}"
    assert len(res["transcript"]) == len(PIPELINE) == 19


def test_key_memory_blocks_present():
    res = run_pipeline("acme-co", SEED, auto_approve=True)
    # one representative block per layer + the 2.1 nested export
    for blk in ("client_profile", "audience_segments", "competitive_map", "trend_signals",
                "active_strategy", "kpi_contracts", "campaign_registry",
                "content_plan", "content_calendar", "copy_assets", "ad_campaign_log",
                "performance_history", "client_health_score", "content_learnings"):
        assert blk in res["memory"], f"missing memory block: {blk}"


def test_phase1_milestone_stop_after_l1():
    res = run_pipeline("acme-co", SEED, auto_approve=True, stop_after_layer="L1")
    assert "client_profile" in res["memory"]
    assert "audience_segments" in res["memory"]
    # stopped after L1 — no Layer-2 block yet
    assert "active_strategy" not in res["memory"]


def test_gate_halts_without_approval():
    # With auto_approve off, every review/binding-gated block is withheld from
    # downstream until an operator approves it; only autonomous agents flow.
    res = run_pipeline("acme-co", SEED, auto_approve=False)
    e11 = next(t for t in res["transcript"] if t["agent"] == "1.1")
    assert e11["valid"] and e11.get("blocked_downstream"), "review gate should withhold 1.1's block"
    assert "client_profile" not in res["memory"]      # review-gated → withheld
    assert "trend_signals" in res["memory"]            # 1.4 autonomous → flows
    assert "campaign_registry" not in res["memory"]    # downstream of withheld blocks
