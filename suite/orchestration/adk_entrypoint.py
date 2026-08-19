"""CLI entrypoint for the ADK workflow — start / resume / status of a run.

This is the Cloud Run Job contract (roadmap Phase 4+): `start` kicks off a run
that executes until it completes or pauses at a human gate; after the operator
approves the pending block (review UI → clients.set_gate_status), `resume`
continues the same session. Sessions persist in Firestore (FirestoreSessionService),
so start and resume can be different processes / job executions.

Usage:
  PYTHONPATH=suite python -m orchestration.adk_entrypoint start \
      --client-id acme-co --input-file suite/inputs/acme.json [--session-id ID] [--auto-approve]
  PYTHONPATH=suite python -m orchestration.adk_entrypoint resume --session-id ID
  PYTHONPATH=suite python -m orchestration.adk_entrypoint status --session-id ID

Env: SUITE_LLM_PROVIDER / SUITE_BACKEND / GCP_PROJECT_ID as usual.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

APP_NAME = "suite"
USER_ID = "operator"


def _runner_and_service():
    from google.adk.runners import Runner
    from infra.adk_sessions import FirestoreSessionService
    from orchestration.adk_workflow import build_workflow
    service = FirestoreSessionService()
    return Runner(node=build_workflow(), app_name=APP_NAME, session_service=service), service


def _pending_interrupt_ids(events) -> list[str]:
    """Ids of a still-pending pause. A session is paused iff its LAST event
    carries an unanswered interrupt (on resume, the response and subsequent
    node events land after it) — checking only the last event prevents
    double-resumes against a run that is already in flight."""
    from google.adk.workflow.utils._workflow_hitl_utils import (
        get_request_input_interrupt_ids)
    events = list(events)
    if not events:
        return []
    return get_request_input_interrupt_ids(events[-1])


def _drive(runner, session_id: str, message=None) -> list[str]:
    events = list(runner.run(user_id=USER_ID, session_id=session_id, new_message=message))
    return _pending_interrupt_ids(events)


def _report(service, session_id: str, ids: list[str]) -> dict:
    session = asyncio.run(service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id))
    state = session.state if session else {}
    return {
        "session_id": session_id,
        "status": "paused" if ids else "completed",
        "interrupt_ids": ids,
        "blocks": sorted((state.get("blocks") or {}).keys()),
        "pending_blocks": sorted((state.get("pending_blocks") or {}).keys()),
        "agents_run": len(state.get("transcript") or []),
        "agents_valid": len([t for t in (state.get("transcript") or []) if t.get("valid")]),
    }


def cmd_start(args) -> dict:
    runner, service = _runner_and_service()
    session_id = args.session_id or f"run-{time.strftime('%Y%m%d-%H%M%S')}"
    inputs = json.loads(open(args.input_file, encoding="utf-8").read()) if args.input_file else {}
    client_id = args.client_id or inputs.get("client_id")
    if not client_id:
        sys.exit("--client-id or an input file with client_id is required")
    asyncio.run(service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
        state={"client_id": client_id, "inputs": inputs,
               "auto_approve": bool(args.auto_approve)}))
    ids = _drive(runner, session_id)
    return _report(service, session_id, ids)


def cmd_resume(args) -> dict:
    from google.genai import types
    from google.adk.workflow.utils._workflow_hitl_utils import (
        create_request_input_response)
    runner, service = _runner_and_service()
    session = asyncio.run(service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=args.session_id))
    if session is None:
        sys.exit(f"no such session: {args.session_id}")
    ids = _pending_interrupt_ids(session.events)
    if not ids:
        return _report(service, args.session_id, [])
    message = types.Content(role="user", parts=[
        create_request_input_response(ids[0], {"decision": "resume"})])
    ids = _drive(runner, args.session_id, message)
    return _report(service, args.session_id, ids)


def cmd_status(args) -> dict:
    _, service = _runner_and_service()
    session = asyncio.run(service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=args.session_id))
    if session is None:
        sys.exit(f"no such session: {args.session_id}")
    return _report(service, args.session_id, _pending_interrupt_ids(session.events))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start")
    p_start.add_argument("--client-id")
    p_start.add_argument("--input-file")
    p_start.add_argument("--session-id")
    p_start.add_argument("--auto-approve", action="store_true")
    p_start.set_defaults(fn=cmd_start)
    for name, fn in (("resume", cmd_resume), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--session-id", required=True)
        p.set_defaults(fn=fn)
    args = parser.parse_args(argv)
    print(json.dumps(args.fn(args), indent=2))


if __name__ == "__main__":
    main()
