"""FirestoreSessionService — CRUD + cross-process pause/resume of the workflow.

Uses the FakeFirestore from test_firestore_backend; skips without google-adk.
"""
from __future__ import annotations

import asyncio
import sys
import pathlib
from dataclasses import replace

SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

import pytest  # noqa: E402

pytest.importorskip("google.adk")

import json  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.workflow.utils._workflow_hitl_utils import (  # noqa: E402
    create_request_input_response, get_request_input_interrupt_ids)
from google.genai import types  # noqa: E402

from infra import clients  # noqa: E402
from infra.adk_sessions import FirestoreSessionService  # noqa: E402
from tests.infra.test_firestore_backend import FakeFirestore  # noqa: E402


@pytest.fixture
def fs(monkeypatch):
    fake = FakeFirestore()
    # memory backend for suite persistence (gate docs), fake Firestore for sessions
    monkeypatch.setattr(clients, "settings",
                        replace(clients.settings, llm_provider="fixture", backend="memory"))
    monkeypatch.setattr(clients, "firestore_client", lambda: fake)
    clients.reset_memory_store()
    return fake


def test_session_crud_roundtrip(fs):
    svc = FirestoreSessionService()
    s = asyncio.run(svc.create_session(app_name="suite", user_id="op",
                                       session_id="r1", state={"x": 1}))
    assert s.id == "r1"
    got = asyncio.run(svc.get_session(app_name="suite", user_id="op", session_id="r1"))
    assert got.state == {"x": 1} and got.events == []
    listed = asyncio.run(svc.list_sessions(app_name="suite"))
    assert [x.id for x in listed.sessions] == ["r1"]
    asyncio.run(svc.delete_session(app_name="suite", user_id="op", session_id="r1"))
    assert asyncio.run(svc.get_session(app_name="suite", user_id="op", session_id="r1")) is None


def test_workflow_pause_survives_new_service_instance(fs):
    """Start a gated run with one service instance; resume with a FRESH one
    (fresh Runner too) — simulating a second process picking up the paused run."""
    from orchestration import adk_workflow

    acme = json.loads((SUITE / "inputs/acme.json").read_text())
    client_id = acme.get("client_id", "acme-co")

    svc1 = FirestoreSessionService()
    asyncio.run(svc1.create_session(app_name="suite", user_id="op", session_id="r1",
                                    state={"client_id": client_id, "inputs": acme,
                                           "auto_approve": False}))
    r1 = Runner(node=adk_workflow.build_workflow(), app_name="suite", session_service=svc1)
    events = list(r1.run(user_id="op", session_id="r1", new_message=None))
    ids = [i for e in events for i in get_request_input_interrupt_ids(e)]
    assert len(ids) == 1  # paused at gate 1.1

    # "New process": fresh service + runner over the same fake Firestore.
    svc2 = FirestoreSessionService()
    mid = asyncio.run(svc2.get_session(app_name="suite", user_id="op", session_id="r1"))
    assert "client_profile" in (mid.state.get("pending_blocks") or {})
    clients.set_gate_status(client_id, "client_profile", "approved", actor="test")
    r2 = Runner(node=adk_workflow.build_workflow(), app_name="suite", session_service=svc2)
    msg = types.Content(role="user", parts=[
        create_request_input_response(ids[0], {"decision": "approved"})])
    events2 = list(r2.run(user_id="op", session_id="r1", new_message=msg))
    final = asyncio.run(svc2.get_session(app_name="suite", user_id="op", session_id="r1"))
    # Past gate 1.1: client_profile promoted, run advanced to the next gate (1.2).
    assert "client_profile" in final.state["blocks"]
    ids2 = [i for e in events2 for i in get_request_input_interrupt_ids(e)]
    assert len(ids2) == 1
    assert "audience_segments" in (final.state.get("pending_blocks") or {})
