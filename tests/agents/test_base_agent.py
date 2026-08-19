"""Unit tests for the shared BaseAgent runner.

Run: `pytest -q` from repo root in a 3.11+ venv with deps installed
(`pip install -e .` + `pip install pytest`). These tests stub all network/DB
clients, so they don't need GCP access or the Anthropic EULA.
"""
from __future__ import annotations

import sys
import pathlib

# Make `import agents...` / `import infra...` resolve to the suite/ package.
SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

from agents.base import BaseAgent, split_named  # noqa: E402


SAMPLE = """Preamble.

## OUTPUT 1 — client_profile JSON

```json
{"client_id": "acme", "gate_status": "returned", "name": "Acme Co."}
```

## OUTPUT 2 — Interview Questions for Client

INTERVIEW QUESTIONS: None required — all critical fields resolved.

## OUTPUT 3 — Human Gate Summary

=== AGENT 1.1 — HUMAN GATE SUMMARY ===
Gate status: RETURNED
"""


class _DummyAgent(BaseAgent):
    def build_user_turn(self, payload):
        return "turn: " + payload.get("x", "")


def _agent(**kw):
    return _DummyAgent(agent_id="t", prompt_asset="does/not/load.txt", **kw)


def test_split_outputs_three_sections():
    out = _agent().split_outputs(SAMPLE)
    assert out["output_1"].startswith("## OUTPUT 1")
    assert "client_id" in out["output_1"]
    assert "None required" in out["output_2"]
    assert "HUMAN GATE SUMMARY" in out["output_3"]


def test_split_outputs_missing_marker_is_empty_not_error():
    out = _agent().split_outputs("## OUTPUT 1 only\nstuff")
    assert out["output_1"].startswith("## OUTPUT 1")
    assert out["output_2"] == ""
    assert out["output_3"] == ""


def test_extract_json_ok_and_bad():
    a = _agent()
    obj = a.extract_json(a.split_outputs(SAMPLE)["output_1"])
    assert obj["client_id"] == "acme"
    assert a.extract_json("no json here") is None
    assert a.extract_json("```json\n{bad json}\n```") is None


def test_validate_no_schema_passes():
    ok, err = _agent(schema_name=None).validate({"anything": 1})
    assert ok and err is None


def test_validate_missing_object_fails_gracefully():
    ok, err = _agent(schema_name="DEL-17").validate(None)
    assert not ok and "did not contain" in err


def test_run_routes_and_returns(monkeypatch):
    a = _agent(schema_name=None)
    monkeypatch.setattr(a, "call", lambda turn: SAMPLE)
    routed = {}
    from dataclasses import replace
    from infra import clients
    # This test asserts the gcp-backend routing path (upsert_client_profile);
    # the library default is now the safe "memory" backend, so pin it here.
    monkeypatch.setattr(clients, "settings", replace(clients.settings, backend="gcp"))
    monkeypatch.setattr(clients, "upsert_client_profile",
                        lambda cid, obj, gate: routed.setdefault("sql", (cid, gate)))
    monkeypatch.setattr(clients, "add_review_doc",
                        lambda coll, doc: routed.setdefault("review", doc))
    res = a.run({"client_id": "acme", "x": "hi"})
    assert res.valid is True
    assert res.outputs["output_1"].startswith("## OUTPUT 1")
    assert routed["sql"] == ("acme", "returned")
    assert routed["review"]["agent"] == "t"
    assert routed["review"]["priority"] == "normal"


def test_run_invalid_output_escalates_to_urgent(monkeypatch):
    # With a schema declared, garbage output → no parseable OUTPUT-1 JSON →
    # validate() False → routed to review as URGENT, never raised.
    a = _agent(schema_name="DEL-17")
    monkeypatch.setattr(a, "call", lambda turn: "garbage with no outputs")
    from infra import clients
    seen = {}
    monkeypatch.setattr(clients, "upsert_client_profile", lambda *x: None)
    monkeypatch.setattr(clients, "add_review_doc", lambda coll, doc: seen.update(doc))
    res = a.run({"client_id": "c1"})
    assert res.valid is False
    assert res.error and "did not contain" in res.error
    assert seen["priority"] == "urgent"


def test_split_named_helper():
    out = split_named("A: alpha\nB: beta", {"a": "A:", "b": "B:"})
    assert out["a"].startswith("A:") and out["b"].startswith("B:")
