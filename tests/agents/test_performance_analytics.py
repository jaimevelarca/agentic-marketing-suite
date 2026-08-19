"""Offline unit tests for Agent 6.1 — Performance Analytics (Layer 6).

Self-contained: inserts suite/ on sys.path exactly like test_base_agent.py, so
no GCP project / Anthropic EULA is needed. Uses only pytest + jsonschema.

Covers:
  (a) split_outputs(fixture) yields 3 non-empty sections;
  (b) extract_json(OUTPUT-1) is a dict with client_id;
  (c) the fixture OUTPUT-1 validates against clients.load_schema("performance_history");
  (d) the schema itself passes jsonschema.Draft7Validator.check_schema;
  (e) a mocked run(): AGENT.call -> fixture, with write_memory_block / add_review_doc
      / publish monkeypatched, asserts res.valid and the routed block == "performance_history".
Plus domain checks: the summary counts foot to kpi_reconciliation, the auto+alert
gate posture, and the breach escalation fan-out (Pub/Sub alert + urgent review doc).
"""
from __future__ import annotations

import pathlib
import sys

import jsonschema
import pytest

# Make `import agents...` / `import infra...` resolve to the suite/ package.
SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer6.performance_analytics import AGENT, run  # noqa: E402
from infra import clients  # noqa: E402
from infra.config import settings  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "6.1.txt").read_text(encoding="utf-8")


def _obj():
    return AGENT.extract_json(AGENT.split_outputs(FIXTURE)["output_1"])


def test_fixture_splits_into_three_sections():
    out = AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "performance_history" in out["output_1"]
    assert out["output_2"].startswith("## OUTPUT 2")
    assert out["output_3"].startswith("## OUTPUT 3")
    assert "PERFORMANCE ALERT SUMMARY" in out["output_3"]


def test_extract_output1_is_dict_with_client_id():
    obj = _obj()
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert "created_at" in obj
    assert obj["gate_status"] == "auto_approved"


def test_fixture_validates_against_schema():
    obj = _obj()
    schema = clients.load_schema("performance_history")
    jsonschema.validate(obj, schema)  # raises on failure


def test_schema_is_valid_draft7():
    schema = clients.load_schema("performance_history")
    jsonschema.Draft7Validator.check_schema(schema)


def test_summary_foots_to_reconciliation():
    obj = _obj()
    recon = obj["kpi_reconciliation"]
    summary = obj["summary"]
    counts = {
        "on_track": 0, "ahead": 0, "at_risk": 0,
        "breach": 0, "no_data": 0, "no_contract": 0,
    }
    for k in recon:
        counts[k["status"]] += 1
    assert summary["kpis_total"] == len(recon)
    assert summary["kpis_on_track"] == counts["on_track"]
    assert summary["kpis_ahead"] == counts["ahead"]
    assert summary["kpis_at_risk"] == counts["at_risk"]
    assert summary["kpis_breached"] == counts["breach"]
    assert summary["kpis_no_data"] == counts["no_data"]


def test_breach_drives_escalation_and_action():
    obj = _obj()
    # auto + alert: a breach escalates but never blocks the pipeline.
    assert obj["gate_status"] == "auto_approved"
    assert obj["escalated"] is True
    assert obj["summary"]["recommended_action"] == "ALERT"
    assert any(a["status"] == "breach" for a in obj["kpi_reconciliation"])
    assert any(a["type"] == "kpi_breach" and a["severity"] == "critical"
               for a in obj["alerts"])


def test_funnel_math_is_self_consistent():
    m = _obj()["metrics"]
    # cpl = spend / leads ; roas = revenue / spend (rounded as the prompt requires)
    assert abs(m["cpl_usd"] - m["spend_usd"] / m["leads"]) < 0.05
    assert abs(m["roas"] - m["revenue_usd"] / m["spend_usd"]) < 0.05


def test_build_user_turn_injects_blocks_and_truncates():
    big = {"k": "x" * 30000}
    turn = AGENT.build_user_turn({
        "client_id": "acme-co",
        "ad_campaign_log": big,
        "active_strategy": {"kpi_contracts": {"review_cadence": "monthly"}},
        "cycle_label": "2026-Q3 launch cycle",
    })
    assert "AGENT 6.1" in turn
    assert "ad_campaign_log" in turn
    assert "active_strategy" in turn
    assert "2026-Q3 launch cycle" in turn
    assert "[truncated]" in turn  # oversized injected block is capped


def test_build_user_turn_flags_no_measurable_actuals():
    turn = AGENT.build_user_turn({"client_id": "acme-co"})
    assert "NO MEASURABLE ACTUALS" in turn
    assert "NO BINDING CONTRACT" in turn


def test_run_mocked_routes_to_performance_history_and_alerts(monkeypatch):
    monkeypatch.setattr(AGENT, "call", lambda turn: FIXTURE)
    routed = {"review": [], "published": []}
    monkeypatch.setattr(
        clients, "write_memory_block",
        lambda cid, block, obj, gate: routed.setdefault("block", (cid, block, gate)),
    )
    monkeypatch.setattr(
        clients, "add_review_doc",
        lambda coll, doc: routed["review"].append(doc),
    )
    monkeypatch.setattr(
        clients, "publish",
        lambda topic, payload: routed["published"].append((topic, payload)),
    )

    res = run({
        "client_id": "acme-co",
        "ad_campaign_log": {"campaigns": [{"channel": "meta_ads", "spend_usd": 300}]},
        "publish_log": {"posts": []},
        "lead_register": {"leads": []},
        "active_strategy": {"gate_status": "approved",
                            "kpi_contracts": {"review_cadence": "monthly"}},
        "cycle_label": "2026-Q3 launch cycle",
    })

    assert res.valid is True
    assert res.structured is not None
    # block written under the agent's memory block name, gate stays auto_approved
    assert routed["block"] == (
        "acme-co", "performance_history", "auto_approved")
    # auto+alert fan-out: a Pub/Sub alert AND an urgent review doc on the breach
    assert any(t == settings.review_topic and p["event"] == "kpi_breach"
               for t, p in routed["published"])
    urgent = [d for d in routed["review"] if d.get("priority") == "urgent"]
    assert urgent and urgent[0]["agent"] == "6.1"
    assert urgent[0]["alert"] == "kpi_breach"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
