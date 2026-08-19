"""Único puente entre Django y la suite (Firestore / sesiones ADK).

Las vistas jamás tocan Firestore directamente: todo pasa por
suite/infra/clients.py y infra.adk_sessions. Las corridas (start/resume)
corren en hilos daemon — la interfaz muestra el estado al recargar.
"""
from __future__ import annotations

import asyncio
import threading

from infra import clients

APP_NAME = "suite"
USER_ID = "operator"

GATE_DECISIONS = {"approved", "returned", "blocked"}


def _service():
    from infra.adk_sessions import FirestoreSessionService
    return FirestoreSessionService()


def list_sessions() -> list[dict]:
    resp = asyncio.run(_service().list_sessions(app_name=APP_NAME))
    out = []
    for s in sorted(resp.sessions, key=lambda x: x.last_update_time, reverse=True):
        out.append({
            "id": s.id,
            "client_id": s.state.get("client_id"),
            "pending": sorted((s.state.get("pending_blocks") or {}).keys()),
            "blocks": len(s.state.get("blocks") or {}),
            "agents_valid": len([t for t in (s.state.get("transcript") or []) if t.get("valid")]),
            "last_update_time": s.last_update_time,
        })
    return out


def _last_interrupt_ids(session) -> list[str]:
    """Una sesión está en pausa si y solo si su ÚLTIMO evento trae una
    interrupción sin responder (al reanudar, la respuesta y los eventos de los
    nodos siguientes quedan después). Esto evita dobles reanudaciones cuando el
    estado (`pending_blocks`) aún no se actualiza por un hilo en curso."""
    from google.adk.workflow.utils._workflow_hitl_utils import (
        get_request_input_interrupt_ids)
    if not session.events:
        return []
    return get_request_input_interrupt_ids(session.events[-1])


def get_session(session_id: str) -> dict | None:
    s = asyncio.run(_service().get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id))
    if s is None:
        return None
    state = s.state
    pending = sorted((state.get("pending_blocks") or {}).keys())
    paused = bool(_last_interrupt_ids(s))
    done = len([t for t in (state.get("transcript") or []) if t]) >= 19 and not paused
    return {
        "id": s.id,
        "client_id": state.get("client_id"),
        "auto_approve": state.get("auto_approve", False),
        "blocks": sorted((state.get("blocks") or {}).keys()),
        "pending": pending,
        "transcript": state.get("transcript") or [],
        "status": ("en pausa (compuerta humana)" if paused
                   else ("terminada" if done else "en curso")),
        "paused": paused,
    }


def block_detail(client_id: str, block: str) -> dict:
    payload = clients.read_memory_block(client_id, block)
    status = clients.read_gate_status(client_id, block)
    return {"client_id": client_id, "block": block,
            "payload": payload, "gate_status": status}


def decide(client_id: str, block: str, decision: str, actor: str, note: str = "") -> None:
    if decision not in GATE_DECISIONS:
        raise ValueError(f"decisión desconocida: {decision!r}")
    clients.set_gate_status(client_id, block, decision, actor=actor, note=note or None)


def _run_in_thread(fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    return t


def start_run(client_id: str, inputs: dict, auto_approve: bool, session_id: str) -> str:
    from google.adk.runners import Runner
    from orchestration.adk_workflow import build_workflow

    service = _service()
    asyncio.run(service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
        state={"client_id": client_id, "inputs": inputs, "auto_approve": auto_approve}))

    def drive():
        runner = Runner(node=build_workflow(), app_name=APP_NAME, session_service=service)
        list(runner.run(user_id=USER_ID, session_id=session_id, new_message=None))

    _run_in_thread(drive)
    return session_id


def resume_run(session_id: str) -> bool:
    """Reanuda una sesión en pausa. Regresa False si no hay pausa pendiente."""
    from google.adk.runners import Runner
    from google.genai import types
    from google.adk.workflow.utils._workflow_hitl_utils import (
        create_request_input_response)
    from orchestration.adk_workflow import build_workflow

    service = _service()
    session = asyncio.run(service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id))
    if session is None:
        return False
    ids = _last_interrupt_ids(session)  # solo si la pausa sigue vigente
    if not ids:
        return False
    message = types.Content(role="user", parts=[
        create_request_input_response(ids[0], {"decision": "resume"})])

    def drive():
        runner = Runner(node=build_workflow(), app_name=APP_NAME, session_service=service)
        list(runner.run(user_id=USER_ID, session_id=session_id, new_message=message))

    _run_in_thread(drive)
    return True
