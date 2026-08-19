# Phase 2 — Firestore Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `gcp` backend persists everything to Firestore — Cloud SQL, psycopg and SQL migrations are gone; gate status becomes an auditable update path; a live fixture-provider run persists a full 19-agent run to the real `(default)` database.

**Architecture:** All persistence flows through `suite/infra/clients.py` exactly as today (the `BaseAgent`/pipeline contract is untouched). Firestore layout: `clients/{client_id}` root doc (metadata) with subcollection `blocks/{block}` (one doc per memory block: `payload`, `gate_status`, `updated_at`) and per-block subcollection `audit/{auto}` (append-only gate/status history). Review queue stays `review_queue/{auto}` as today. The `memory` backend keeps identical semantics for tests/offline.

**Tech Stack:** `google-cloud-firestore` (already a dep), pytest with a fake Firestore client (no network).

**Spec:** `ROADMAP.md` Phase 2.

## Global Constraints

- The 207 existing tests keep passing unmodified (they monkeypatch `write_memory_block`/`upsert_client_profile`/`add_review_doc`/`publish` — keep those names and signatures).
- No GCP call at import time; all SDK imports stay lazy.
- Gate vocabulary (from baseline fixtures): `pending`, `pending_review`, `approved`, `auto_approved`, `returned`, `blocked`.

---

### Task 1: Firestore persistence in `clients.py` (test-first)

**Files:**
- Create: `tests/infra/__init__.py`, `tests/infra/test_firestore_backend.py`
- Modify: `suite/infra/clients.py` (replace the Cloud SQL section)

**Interfaces:**
- Produces (gcp backend):
  - `write_memory_block(client_id, block, obj, gate_status)` → set `clients/{cid}/blocks/{block}` = `{payload, gate_status, updated_at}` (merge) + audit entry `{action: "write", gate_status, agent_write: True}`.
  - `upsert_client_profile(client_id, profile, gate_status)` → same block write for `client_profile` + merge `{client_id, name?, updated_at}` into root `clients/{cid}`.
  - `read_memory_block(client_id, block)` → payload dict or None.
  - `set_gate_status(client_id, block, status, actor="system", note=None)` → update block doc's `gate_status` + audit entry `{action: "gate", status, actor, note}`; raises `ValueError` on unknown status. Memory backend mirrors all of the above (audit under `MEMORY_STORE["audit"]`).

- [ ] Step 1: Write failing tests with a `FakeFirestore` (records `document(path).set/update` calls) monkeypatched over `clients.firestore_client`.
- [ ] Step 2: Run → fail (no `set_gate_status`, SQL path raises).
- [ ] Step 3: Implement; delete `_pg_pool`/SQL code.
- [ ] Step 4: Full suite green (207 + new).
- [ ] Step 5: Commit.

### Task 2: Purge Cloud SQL from config, deps, scripts, migrations

**Files:**
- Modify: `suite/infra/config.py` (drop `sql_*`, `db_*`, `sql_instance_connection_name`), `pyproject.toml` (drop psycopg, psycopg-pool), `suite/scripts/run_live.sh` (drop proxy/PGPASSWORD block)
- Delete: `suite/migrations/`

- [ ] Step 1: Grep proves no remaining consumer of the removed names.
- [ ] Step 2: `uv sync` re-lock; full suite green.
- [ ] Step 3: Commit.

### Task 3: Live smoke run against real Firestore (exit criterion)

- [ ] Step 1: `PYTHONPATH=suite SUITE_LLM_PROVIDER=fixture SUITE_BACKEND=gcp GCP_PROJECT_ID=agentic-marketing-suite python -m orchestration.demo` (fixture LLM, real Firestore; ADC).
- [ ] Step 2: Verify with a read-back script: 20 blocks under `clients/acme_smb_001/blocks`, review-queue docs present, audit entries present.
- [ ] Step 3: Record result in ROADMAP (Phase 2 ✅) + commit + push.
