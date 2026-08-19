"""Firestore-backed ADK session service (roadmap Phase 4).

The official Firestore session service is Java-only; this is the minimal Python
implementation the suite needs for cross-process pause/resume of the ADK
workflow (a paused run's session must survive the Cloud Run Job that started
it). Layout:

    adk_sessions/{app_name}__{user_id}__{session_id}     root doc:
        app_name, user_id, id, state (dict), last_update_time (epoch seconds)
      /events/{seq:08d}                                  one doc per event:
        seq, event (Event JSON string — events exceed 1 MiB as a single array)

google-adk is an optional dependency: import this module only where the `adk`
extra is installed.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from google.adk.events import Event
from google.adk.sessions import BaseSessionService, Session
from google.adk.sessions.base_session_service import ListSessionsResponse

from infra import clients

_COLLECTION = "adk_sessions"


def _doc_id(app_name: str, user_id: str, session_id: str) -> str:
    return f"{app_name}__{user_id}__{session_id}"


class FirestoreSessionService(BaseSessionService):
    """Persist ADK sessions in Firestore (sync client under async methods —
    fine at suite scale: one operator, few concurrent runs)."""

    def _root(self, app_name: str, user_id: str, session_id: str):
        return clients.firestore_client().collection(_COLLECTION).document(
            _doc_id(app_name, user_id, session_id))

    async def create_session(
        self, *, app_name: str, user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = (session_id or "").strip() or hex(int(time.time() * 1000))[2:]
        session = Session(app_name=app_name, user_id=user_id, id=session_id,
                          state=state or {}, last_update_time=time.time())
        self._root(app_name, user_id, session_id).set({
            "app_name": app_name, "user_id": user_id, "id": session_id,
            "state": session.state, "last_update_time": session.last_update_time,
        })
        return session

    async def get_session(self, *, app_name: str, user_id: str, session_id: str,
                          config=None) -> Optional[Session]:
        root = self._root(app_name, user_id, session_id)
        snap = root.get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        events = []
        for doc in root.collection("events").stream():
            d = doc.to_dict() or {}
            events.append((d.get("seq", 0), Event.model_validate_json(d["event"])))
        events.sort(key=lambda p: p[0])
        return Session(app_name=app_name, user_id=user_id, id=session_id,
                       state=data.get("state") or {},
                       events=[e for _, e in events],
                       last_update_time=data.get("last_update_time") or 0.0)

    async def delete_session(self, *, app_name: str, user_id: str, session_id: str) -> None:
        root = self._root(app_name, user_id, session_id)
        for doc in root.collection("events").stream():
            doc.reference.delete()
        root.delete()

    async def list_sessions(self, *, app_name: str,
                            user_id: Optional[str] = None) -> ListSessionsResponse:
        sessions = []
        for snap in clients.firestore_client().collection(_COLLECTION).stream():
            d = snap.to_dict() or {}
            if d.get("app_name") != app_name:
                continue
            if user_id is not None and d.get("user_id") != user_id:
                continue
            sessions.append(Session(app_name=d["app_name"], user_id=d["user_id"],
                                    id=d["id"], state=d.get("state") or {},
                                    last_update_time=d.get("last_update_time") or 0.0))
        return ListSessionsResponse(sessions=sessions)

    async def append_event(self, session: Session, event: Event) -> Event:
        event = await super().append_event(session, event)
        if event.partial:
            return event
        session.last_update_time = time.time()
        root = self._root(session.app_name, session.user_id, session.id)
        seq = len(session.events)  # session.events already includes this event
        root.collection("events").document(f"{seq:08d}").set(
            {"seq": seq, "event": event.model_dump_json()})
        root.set({"state": session.state, "last_update_time": session.last_update_time},
                 merge=True)
        return event
