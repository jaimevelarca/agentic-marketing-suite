"""Firestore persistence layer (gcp backend) — exercised against a fake client.

No network: `clients.firestore_client` is monkeypatched with FakeFirestore,
which records document paths and written payloads.
"""
from __future__ import annotations

import sys
import pathlib
from dataclasses import replace

SUITE = pathlib.Path(__file__).resolve().parents[2] / "suite"
sys.path.insert(0, str(SUITE))

import pytest  # noqa: E402
from infra import clients  # noqa: E402


# --- fake firestore ----------------------------------------------------------
class FakeDoc:
    def __init__(self, store: dict, path: str):
        self.store, self.path = store, path

    def set(self, data, merge=False):
        if merge and self.path in self.store:
            self.store[self.path].update(data)
        else:
            self.store[self.path] = dict(data)

    def update(self, data):
        if self.path not in self.store:
            raise KeyError(f"update on missing doc {self.path}")
        self.store[self.path].update(data)

    def get(self):
        class Snap:
            def __init__(s, d):
                s._d = d
            @property
            def exists(s):
                return s._d is not None
            def to_dict(s):
                return s._d
        return Snap(self.store.get(self.path))

    def collection(self, name):
        return FakeCollection(self.store, f"{self.path}/{name}")


class FakeCollection:
    _n = 0

    def __init__(self, store: dict, path: str):
        self.store, self.path = store, path

    def document(self, doc_id):
        return FakeDoc(self.store, f"{self.path}/{doc_id}")

    def add(self, data):
        FakeCollection._n += 1
        self.store[f"{self.path}/auto{FakeCollection._n}"] = dict(data)


class FakeFirestore:
    def __init__(self):
        self.store: dict[str, dict] = {}

    def collection(self, name):
        return FakeCollection(self.store, name)

    def document(self, path):
        return FakeDoc(self.store, path)


@pytest.fixture
def fs(monkeypatch):
    fake = FakeFirestore()
    monkeypatch.setattr(clients, "settings", replace(clients.settings, backend="gcp"))
    monkeypatch.setattr(clients, "firestore_client", lambda: fake)
    return fake


# --- write/read blocks -------------------------------------------------------
def test_write_memory_block_lands_in_blocks_subcollection(fs):
    clients.write_memory_block("acme", "trend_signals", {"a": 1}, "pending_review")
    doc = fs.store["clients/acme/blocks/trend_signals"]
    assert doc["payload"] == {"a": 1}
    assert doc["gate_status"] == "pending_review"
    audits = [p for p in fs.store if p.startswith("clients/acme/blocks/trend_signals/audit/")]
    assert len(audits) == 1
    assert fs.store[audits[0]]["action"] == "write"


def test_upsert_client_profile_writes_block_and_root_doc(fs):
    clients.upsert_client_profile("acme", {"client_id": "acme", "name": "Acme Co."}, "approved")
    assert fs.store["clients/acme/blocks/client_profile"]["gate_status"] == "approved"
    root = fs.store["clients/acme"]
    assert root["client_id"] == "acme"
    assert root["name"] == "Acme Co."


def test_read_memory_block_roundtrip_and_missing(fs):
    clients.write_memory_block("acme", "content_plan", {"posts": []}, "pending")
    assert clients.read_memory_block("acme", "content_plan") == {"posts": []}
    assert clients.read_memory_block("acme", "nope") is None


def test_write_memory_block_routes_client_profile_via_upsert(fs):
    clients.write_memory_block("acme", "client_profile", {"client_id": "acme"}, "pending")
    assert "clients/acme" in fs.store  # root doc written → took the upsert path


# --- gate state machine ------------------------------------------------------
def test_set_gate_status_updates_block_and_appends_audit(fs):
    clients.write_memory_block("acme", "content_plan", {"posts": []}, "pending_review")
    clients.set_gate_status("acme", "content_plan", "approved", actor="jaime", note="ok")
    assert fs.store["clients/acme/blocks/content_plan"]["gate_status"] == "approved"
    audits = sorted(p for p in fs.store if "content_plan/audit/" in p)
    assert len(audits) == 2  # write + gate
    gate = fs.store[audits[-1]]
    assert (gate["action"], gate["status"], gate["actor"], gate["note"]) == (
        "gate", "approved", "jaime", "ok")


def test_set_gate_status_rejects_unknown_status(fs):
    clients.write_memory_block("acme", "content_plan", {}, "pending")
    with pytest.raises(ValueError):
        clients.set_gate_status("acme", "content_plan", "yolo")


# --- memory backend mirrors the same API -------------------------------------
def test_memory_backend_set_gate_status(monkeypatch):
    monkeypatch.setattr(clients, "settings", replace(clients.settings, backend="memory"))
    clients.reset_memory_store()
    clients.write_memory_block("acme", "content_plan", {"x": 1}, "pending_review")
    clients.set_gate_status("acme", "content_plan", "returned", actor="jaime")
    blk = clients.MEMORY_STORE["memory_blocks"]["acme"]["content_plan"]
    assert blk["gate_status"] == "returned"
    assert clients.MEMORY_STORE["audit"][-1]["status"] == "returned"
