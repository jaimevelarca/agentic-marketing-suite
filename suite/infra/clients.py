"""Client factories + routing helpers for the LLM providers, Firestore, and
Pub/Sub — plus an offline ('memory'/'fixture') mode so the whole Suite runs
end-to-end with no GCP project and no API key. Firestore is the only
persistence backend (roadmap Phase 2 removed Cloud SQL).

Two independent runtime switches (see infra.config.Settings):
  - settings.llm_provider: "vertex" (prod) | "fixture" (canned per-agent text)
  - settings.backend:      "gcp"    (prod) | "memory" (in-process MEMORY_STORE)

All GCP SDK imports stay lazy/inside functions so the module imports cleanly in
offline dev and tests. All calls are synchronous to match the Vertex/Firestore/
Pub-Sub SDKs; concurrency comes from separate Cloud Run Job / Agent Engine
invocations, not in-process async.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from infra.config import settings

_ROOT = Path(__file__).resolve().parents[2]


# --- Offline store -----------------------------------------------------------
# When settings.backend == "memory", memory-block writes, review-queue docs, and
# Pub/Sub publishes land here instead of GCP. The orchestrator reads this for
# the offline demo; tests reset it between runs.
MEMORY_STORE: dict = {"memory_blocks": {}, "review_queue": [], "published": [], "audit": []}


def reset_memory_store() -> None:
    MEMORY_STORE["memory_blocks"] = {}
    MEMORY_STORE["review_queue"] = []
    MEMORY_STORE["published"] = []
    MEMORY_STORE["audit"] = []


# --- LLM (provider-pluggable) ------------------------------------------------
@lru_cache
def anthropic_vertex_client():
    from anthropic import AnthropicVertex
    return AnthropicVertex(region=settings.vertex_region, project_id=settings.project_id)


@lru_cache
def anthropic_direct_client():
    """Claude on Anthropic's first-party API (not Vertex). Reads ANTHROPIC_API_KEY
    from the environment. Used as the 'anthropic' provider so the Suite can run
    live on real data while Vertex base-model quota is still being granted —
    same code path, same model strings, just a different backbone."""
    from anthropic import Anthropic
    return Anthropic()


def _direct_model_id(model: str) -> str:
    """Vertex model IDs may carry an '@<date>' suffix (e.g. claude-haiku-4-5@20251001);
    the first-party API uses the bare name. Strip the suffix for the direct provider."""
    return model.split("@", 1)[0]


def _load_fixture(agent_id: str) -> str:
    """Canned response for the offline 'fixture' provider, from
    suite/fixtures/<agent_id>.txt (e.g. '1.1.txt'). These are schema-valid
    sample outputs used to exercise the full pipeline without a live model."""
    path = settings.fixtures_dir / f"{agent_id}.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"fixture LLM provider is on but no fixture for agent {agent_id} "
            f"(expected {path}). Add it or set SUITE_LLM_PROVIDER=vertex."
        )
    return path.read_text(encoding="utf-8")


def llm_complete(*, model: str, system: str, user_turn: str, max_tokens: int,
                 agent_id: str) -> str:
    """One cached completion. Dispatches on settings.llm_provider so callers
    (BaseAgent.call) are provider-agnostic. The system prompt is always sent
    with an Anthropic ephemeral cache marker (Vertex passes it through)."""
    if settings.llm_provider == "fixture":
        return _load_fixture(agent_id)
    if settings.llm_provider == "anthropic":
        client, model = anthropic_direct_client(), _direct_model_id(model)
    else:
        client = anthropic_vertex_client()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},  # always cache the system prompt
        }],
        messages=[{"role": "user", "content": user_turn}],
    )
    # Stream the call: large max_tokens (the heavy agents emit 30k+ tokens) exceed
    # the SDK's non-streaming 10-minute ceiling, which hard-errors. Streaming also
    # avoids request timeouts on long generations. get_final_message() reassembles.
    with client.messages.stream(**kwargs) as stream:
        final = stream.get_final_message()
    return final.content[0].text


# --- Firestore (review queue) ------------------------------------------------
@lru_cache
def firestore_client():
    from google.cloud import firestore
    return firestore.Client(project=settings.project_id)


def add_review_doc(collection: str, doc: dict) -> None:
    """Append a document to a review-queue collection. In 'memory' backend this
    captures to MEMORY_STORE; in 'gcp' it writes Firestore with SERVER_TIMESTAMP."""
    if settings.backend == "memory":
        MEMORY_STORE["review_queue"].append({"collection": collection, **doc})
        return
    from google.cloud import firestore
    fs = firestore_client()
    payload = dict(doc)
    payload["created_at"] = firestore.SERVER_TIMESTAMP
    fs.collection(collection).add(payload)


# --- Pub/Sub -----------------------------------------------------------------
@lru_cache
def _publisher():
    from google.cloud import pubsub_v1
    return pubsub_v1.PublisherClient()


def publish(topic: str, payload: dict) -> str:
    if settings.backend == "memory":
        MEMORY_STORE["published"].append({"topic": topic, "payload": payload})
        return "memory"
    publisher = _publisher()
    topic_path = publisher.topic_path(settings.project_id, topic)
    future = publisher.publish(topic_path, json.dumps(payload).encode("utf-8"))
    return future.result(timeout=30)


# --- Firestore persistence (memory blocks + gate state) ----------------------
# Layout: clients/{client_id}                     root doc (metadata)
#         clients/{client_id}/blocks/{block}      payload + gate_status + updated_at
#         clients/{client_id}/blocks/{block}/audit/{auto}   append-only history
GATE_STATUSES = {"pending", "pending_review", "approved", "auto_approved", "returned", "blocked"}


def _now_field():
    from google.cloud import firestore
    return firestore.SERVER_TIMESTAMP


def _block_ref(fs, client_id: str, block: str):
    return fs.collection("clients").document(client_id).collection("blocks").document(block)


def _append_audit(fs, client_id: str, block: str, entry: dict) -> None:
    entry = dict(entry)
    entry["at"] = _now_field()
    _block_ref(fs, client_id, block).collection("audit").add(entry)


def write_memory_block(client_id: str, block: str, obj: dict, gate_status: str) -> None:
    """Persist any agent's validated structured output to its memory block.
    The 'client_profile' block additionally refreshes the client root doc."""
    if settings.backend == "memory":
        MEMORY_STORE["memory_blocks"].setdefault(client_id, {})[block] = {
            "payload": obj, "gate_status": gate_status,
        }
        MEMORY_STORE.setdefault("audit", []).append(
            {"client_id": client_id, "block": block, "action": "write", "gate_status": gate_status})
        return
    if block == "client_profile":
        upsert_client_profile(client_id, obj, gate_status)
        return
    fs = firestore_client()
    _block_ref(fs, client_id, block).set(
        {"payload": obj, "gate_status": gate_status, "updated_at": _now_field()}, merge=True)
    _append_audit(fs, client_id, block, {"action": "write", "gate_status": gate_status,
                                         "agent_write": True})


def upsert_client_profile(client_id: str, profile: dict, gate_status: str) -> None:
    """client_profile block write + refresh of the client root doc (metadata
    other surfaces list clients by)."""
    if settings.backend == "memory":
        MEMORY_STORE["memory_blocks"].setdefault(client_id, {})["client_profile"] = {
            "payload": profile, "gate_status": gate_status,
        }
        MEMORY_STORE.setdefault("audit", []).append(
            {"client_id": client_id, "block": "client_profile", "action": "write",
             "gate_status": gate_status})
        return
    fs = firestore_client()
    _block_ref(fs, client_id, "client_profile").set(
        {"payload": profile, "gate_status": gate_status, "updated_at": _now_field()}, merge=True)
    root = {"client_id": client_id, "updated_at": _now_field()}
    if isinstance(profile, dict) and profile.get("name"):
        root["name"] = profile["name"]
    fs.collection("clients").document(client_id).set(root, merge=True)
    _append_audit(fs, client_id, "client_profile",
                  {"action": "write", "gate_status": gate_status, "agent_write": True})


def read_memory_block(client_id: str, block: str) -> dict | None:
    """Load one structured memory block for a client (for an agent that reads an
    upstream block when running as its own Cloud Run Job). Returns None if absent."""
    if settings.backend == "memory":
        return MEMORY_STORE["memory_blocks"].get(client_id, {}).get(block, {}).get("payload")
    snap = _block_ref(firestore_client(), client_id, block).get()
    if not snap.exists:
        return None
    return (snap.to_dict() or {}).get("payload")


def set_gate_status(client_id: str, block: str, status: str, actor: str = "system",
                    note: str | None = None) -> None:
    """Human/system gate decision on a block: update gate_status + audit trail.
    This is the write path the review UI (roadmap Phase 5) calls; the paused
    orchestrator watches the same doc to resume."""
    if status not in GATE_STATUSES:
        raise ValueError(f"unknown gate status {status!r} (allowed: {sorted(GATE_STATUSES)})")
    if settings.backend == "memory":
        MEMORY_STORE["memory_blocks"].setdefault(client_id, {}).setdefault(
            block, {"payload": None})["gate_status"] = status
        MEMORY_STORE.setdefault("audit", []).append(
            {"client_id": client_id, "block": block, "action": "gate", "status": status,
             "actor": actor, "note": note})
        return
    fs = firestore_client()
    _block_ref(fs, client_id, block).update({"gate_status": status, "updated_at": _now_field()})
    _append_audit(fs, client_id, block,
                  {"action": "gate", "status": status, "actor": actor, "note": note})


# --- JSON Schemas (auto-discovered) ------------------------------------------
# Each product agent drops its memory-block schema at
# project/resources/schemas/<block>.json and references it by name (schema_name
# == block name). No central registry edit needed when adding an agent.
_SCHEMA_DIRS = [_ROOT / "project/resources/schemas"]
_LEGACY_SCHEMAS = {
    "DEL-17": _ROOT / "project/resources/schemas/DEL-17_client_profile_schema.json",
}


@lru_cache
def load_schema(name: str) -> dict:
    if name in _LEGACY_SCHEMAS:
        return json.loads(_LEGACY_SCHEMAS[name].read_text(encoding="utf-8"))
    for d in _SCHEMA_DIRS:
        for cand in (d / f"{name}.json", d / f"{name}_schema.json"):
            if cand.exists():
                return json.loads(cand.read_text(encoding="utf-8"))
    raise KeyError(
        f"unknown schema: {name} (looked for {name}.json / {name}_schema.json "
        f"under {[str(d) for d in _SCHEMA_DIRS]} and legacy registry)"
    )
