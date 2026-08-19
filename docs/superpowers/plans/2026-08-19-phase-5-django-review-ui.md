# Phase 5 — Django Review & Ops UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A human runs and approves an entire client pipeline from the browser — review queue with approve/return/block + audit, run browser, new-run form — Django 5.x, es-MX, against the suite's Firestore layer.

**Architecture:** `web/` Django project (`core` settings + `console` app). Django's own DB is SQLite locally / `DATABASE_URL` Postgres in prod (Cloud SQL lands with Phase 6 deploy — it is NOT needed for the phase exit). All domain data flows through `suite/infra/clients.py` and `infra.adk_sessions` — Django never talks to Firestore directly. Long operations (start/resume of a run) execute in daemon threads; the UI shows session status on reload. UI copy: español es-MX profesional, sin anglicismos. `#1ebe82` appears ONLY on human-gate approve controls.

**Tech Stack:** Django ≥5.0 (`web` extra), pytest-django (dev), suite package via `sys.path` (same PYTHONPATH=suite convention).

**Spec:** `ROADMAP.md` Phase 5.

## Global Constraints

- The 226 existing tests stay green; web tests are offline (suite functions monkeypatched).
- No secrets in repo; `DJANGO_SECRET_KEY` from env (dev fallback clearly marked).
- Every view requires login (Django auth); admin enabled for user management.
- Gate actions write through `clients.set_gate_status` with `actor=<username>` — the audit trail must show who decided.

## Tasks

### Task 1: Scaffold + settings + auth
`web/manage.py`, `web/core/{settings,urls,wsgi}.py`, `console` app registered,
es-MX (`LANGUAGE_CODE="es-mx"`, `TIME_ZONE="America/Mexico_City"`), SQLite default +
`DATABASE_URL` override, login/logout views, base template with nav.
- [ ] scaffold; `migrate` + `runserver` smoke; commit

### Task 2: `console/services.py` — the only bridge to the suite
`list_sessions()`, `get_session(session_id)`, `pending_blocks(state)`,
`block_detail(client_id, block)` (payload + gate + audit),
`decide(client_id, block, decision, actor, note)` → `clients.set_gate_status`,
`start_run(client_id, inputs, auto_approve)` / `resume_run(session_id)` (daemon
threads over `orchestration.adk_entrypoint` internals). Offline tests with
monkeypatched clients/session service.
- [ ] tests → implement → commit

### Task 3: Views + templates (es-MX)
Panel (sessions + pending count), session detail (transcript, blocks,
pending, Reanudar button), block review (JSON payload, audit trail,
Aprobar `#1ebe82` / Devolver / Bloquear + nota), Nueva corrida form
(client_id + JSON inputs textarea prefilled from `suite/inputs/acme.json`,
auto-approve checkbox). Offline view tests: auth required, render, decide POST
calls `set_gate_status(actor=username)`, start POST calls `start_run`.
- [ ] tests → implement → commit

### Task 4: Live browser-equivalent proof (exit criterion)
Against dev Firestore (fixture LLM, gcp backend): drive the full flow through
the Django test client — login → nueva corrida (no auto-approve) → pauses →
approve each pending block via the review view → Reanudar each round →
session completed 19/19. Record in plan; ROADMAP ✅; runserver instructions in
web/README.md for the human to do the same by hand.
- [ ] live proof → docs → commit + push
