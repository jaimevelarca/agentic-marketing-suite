"""ADK workflow port — topology + offline execution + gate pause/resume.

Offline: LLM calls route to fixtures, persistence to MEMORY_STORE (the real
memory backend, so gate reads/writes work). Requires google-adk (the `adk`
extra); tests skip if it isn't installed.
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
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow.utils._workflow_hitl_utils import (  # noqa: E402
    get_request_input_interrupt_ids)
from google.genai import types  # noqa: E402

from infra import clients  # noqa: E402
from orchestration import adk_workflow  # noqa: E402
from orchestration.pipeline import GATED, PIPELINE  # noqa: E402

ACME = json.loads((pathlib.Path(SUITE) / "inputs/acme.json").read_text())
CLIENT_ID = ACME.get("client_id", "acme-co")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Fixture LLM + real memory backend (so gate reads/writes work)."""
    monkeypatch.setattr(clients, "settings",
                        replace(clients.settings, llm_provider="fixture", backend="memory"))
    clients.reset_memory_store()


def _node_names(wf):
    names = []
    for e in wf.edges:
        for n in (e.from_node, e.to_node):
            name = getattr(n, "name", None)
            if name and name not in names and name != "__START__":
                names.append(name)
    return names


def test_topology_mirrors_pipeline():
    wf = adk_workflow.build_workflow()
    expected = []
    for step in PIPELINE:
        expected.append(adk_workflow.node_name(step))
        if step.gate in GATED:
            expected.append(adk_workflow.gate_name(step))
    got = [n for n in _node_names(wf) if n != "START"]
    assert got == expected
    assert len([n for n in got if n.startswith("agent_")]) == 19
    assert len([n for n in got if n.startswith("gate_")]) == 14
    assert len(wf.edges) == len(got)  # linear chain incl. START edge


def _run(runner, session_service, state=None, message=None, session_exists=False):
    if not session_exists:
        asyncio.run(session_service.create_session(
            app_name="suite", user_id="op", session_id="run1", state=state or {}))
    events = list(runner.run(user_id="op", session_id="run1", new_message=message))
    ids = [i for e in events for i in get_request_input_interrupt_ids(e)]
    final = asyncio.run(session_service.get_session(
        app_name="suite", user_id="op", session_id="run1"))
    return events, ids, dict(final.state)


def test_full_offline_run_auto_approve():
    ss = InMemorySessionService()
    runner = Runner(node=adk_workflow.build_workflow(), app_name="suite", session_service=ss)
    _, ids, state = _run(runner, ss, state={
        "client_id": CLIENT_ID, "inputs": ACME, "auto_approve": True})
    assert ids == []  # never paused
    assert len(state["blocks"]) == 20  # 19 agent blocks + kpi_contracts export
    assert "kpi_contracts" in state["blocks"]
    valid = [t for t in state["transcript"] if t["valid"]]
    assert len(valid) == 19


def test_gated_run_pauses_then_resumes_on_approval():
    ss = InMemorySessionService()
    runner = Runner(node=adk_workflow.build_workflow(), app_name="suite", session_service=ss)
    events, ids, state = _run(runner, ss, state={
        "client_id": CLIENT_ID, "inputs": ACME, "auto_approve": False})
    # First human gate is 1.1 (client_profile is pending_review in the fixture).
    assert len(ids) == 1
    assert "client_profile" in state.get("pending_blocks", {})
    assert "client_profile" not in state.get("blocks", {})

    # Approve-as-you-go: flip each pending gate doc, resume, repeat.
    from google.adk.workflow.utils._workflow_hitl_utils import create_request_input_response
    rounds = 0
    while ids:
        rounds += 1
        assert rounds <= 20, "gate loop did not converge"
        session = asyncio.run(ss.get_session(app_name="suite", user_id="op", session_id="run1"))
        for block in dict(session.state.get("pending_blocks") or {}):
            clients.set_gate_status(CLIENT_ID, block, "approved", actor="test")
        msg = types.Content(role="user", parts=[
            create_request_input_response(ids[0], {"decision": "approved"})])
        _, ids, state = _run(runner, ss, message=msg, session_exists=True)

    assert len(state["blocks"]) == 20
    assert state.get("pending_blocks") == {}
    assert len([t for t in state["transcript"] if t["valid"]]) == 19


def test_state_client_id_beats_inputs_client_id():
    """Inputs JSON carrying its own client_id must NOT hijack the run identity:
    blocks are written under the run's client_id (live bug: agents wrote under
    'acme' from acme.json while gates read 'acme-co')."""
    ss = InMemorySessionService()
    runner = Runner(node=adk_workflow.build_workflow(), app_name="suite", session_service=ss)
    inputs = dict(ACME, client_id="intruso")
    _, ids, state = _run(runner, ss, state={
        "client_id": "cliente-real", "inputs": inputs, "auto_approve": True})
    assert ids == []
    assert "cliente-real" in clients.MEMORY_STORE["memory_blocks"]
    assert "intruso" not in clients.MEMORY_STORE["memory_blocks"]
