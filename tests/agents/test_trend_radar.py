"""Offline tests for Agent 1.4 — Trend Radar.

Self-contained: inserts suite/ on sys.path exactly like test_base_agent.py, so
it needs no GCP project and no Anthropic EULA. Uses only pytest + jsonschema.

Covers:
  (a) split_outputs(fixture) yields the 3 OUTPUT sections;
  (b) extract_json(OUTPUT-1) is a dict carrying client_id;
  (c) the fixture's OUTPUT-1 validates against load_schema("trend_signals");
  (d) the schema itself passes jsonschema's check_schema;
  (e) a mocked run(): AGENT.call returns the fixture and the GCP routing helpers
      are monkeypatched — assert res.valid and that the written block is
      "trend_signals" with gate_status "auto_approved".
"""
from __future__ import annotations

import pathlib
import sys

import jsonschema

# Make `import agents...` / `import infra...` resolve to the suite/ package.
SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

from agents.layer1 import trend_radar  # noqa: E402
from infra import clients  # noqa: E402

FIXTURE = (SUITE / "fixtures" / "1.4.txt").read_text(encoding="utf-8")


def test_split_outputs_three_sections():
    out = trend_radar.AGENT.split_outputs(FIXTURE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "trend_signals" in out["output_1"]
    assert "TREND RADAR — CONTENT BRIEF" in out["output_2"]
    assert "AUTONOMOUS RUN SUMMARY" in out["output_3"]


def test_extract_json_is_dict_with_client_id():
    obj = trend_radar.AGENT.extract_json(
        trend_radar.AGENT.split_outputs(FIXTURE)["output_1"]
    )
    assert isinstance(obj, dict)
    assert obj["client_id"] == "acme-co"
    assert obj["gate_status"] == "auto_approved"
    assert isinstance(obj["signals"], list) and len(obj["signals"]) >= 4


def test_fixture_output1_validates_against_schema():
    obj = trend_radar.AGENT.extract_json(
        trend_radar.AGENT.split_outputs(FIXTURE)["output_1"]
    )
    schema = clients.load_schema("trend_signals")
    jsonschema.validate(obj, schema)  # raises on failure


def test_schema_is_valid_jsonschema():
    schema = clients.load_schema("trend_signals")
    jsonschema.Draft7Validator.check_schema(schema)


def test_every_signal_carries_required_time_fields():
    obj = trend_radar.AGENT.extract_json(
        trend_radar.AGENT.split_outputs(FIXTURE)["output_1"]
    )
    for sig in obj["signals"]:
        for field in ("relevance_score", "velocity", "ttl_days",
                      "estimated_peak_date", "confidence"):
            assert field in sig, f"signal {sig.get('signal_id')} missing {field}"
        assert 0.0 <= sig["relevance_score"] <= 1.0


def test_run_routes_to_trend_signals_block(monkeypatch):
    routed = {}
    monkeypatch.setattr(trend_radar.AGENT, "call", lambda turn: FIXTURE)
    monkeypatch.setattr(
        clients, "write_memory_block",
        lambda cid, block, obj, gate: routed.update(
            {"client_id": cid, "block": block, "gate": gate}),
    )
    monkeypatch.setattr(clients, "add_review_doc",
                        lambda coll, doc: routed.setdefault("review", doc))
    monkeypatch.setattr(clients, "publish",
                        lambda topic, payload: routed.setdefault("publish", topic))

    res = trend_radar.run({"client_id": "acme-co",
                           "rss_feeds": [], "hashtags": [], "seasonal_themes": []})

    assert res.valid is True
    assert routed["block"] == "trend_signals"
    assert routed["client_id"] == "acme-co"
    assert routed["gate"] == "auto_approved"
    assert routed["review"]["agent"] == "1.4"
    assert routed["review"]["priority"] == "normal"


def test_build_user_turn_tolerates_missing_inputs():
    turn = trend_radar.AGENT.build_user_turn({"client_id": "c1"})
    assert "AGENT 1.4 (TREND RADAR)" in turn
    assert "client_profile" in turn  # the not-available branch still names it
    assert "Tracked Hashtags" in turn
