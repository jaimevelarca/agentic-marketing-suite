# Phase 7 — Gemini Enterprise Agent Platform Surface & Vertex Reasoning Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Gemini Enterprise Agent Platform surface (Phase 7) for `agentic-marketing-suite`, allowing QHHE team members to converse with, inspect, and trigger the 19-agent marketing intelligence engine directly from Gemini Enterprise (Pay-as-you-go edition) via Vertex AI Reasoning Engine (`gcp.vertex.AiReasoningEngine` / `agent_engines`) and A2A agent cards backed by Firestore.

---

## Architectural Context & Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Runtime Surface** | **Vertex AI Reasoning Engine** (`vertexai.preview.reasoning_engines` / `google.genai`) | Native managed agent runtime on GCP with built-in query session management, tool execution, and Gemini 3.x integration. |
| **Data Layer Integration** | Direct **Firestore Native** queries (`clients/{id}`, `runs/{id}/blocks/{block}`) | Reuses the existing Phase 2 Firestore data layer; zero data drift between the batch pipeline, the Django Console, and the Gemini Enterprise conversational surface. |
| **Conversational Tooling** | Domain-specific query tools (`get_client_profile`, `get_audience_segments`, `get_competitive_radar`, `get_active_strategy`, `get_content_calendar`, `get_creative_specs`, `get_run_status`, `execute_pipeline`) | Gives Gemini Enterprise precise, typed access to all 19 delivered memory blocks across active client runs (e.g. Alonso y Cía, CENEVAL, U-Storage). |
| **A2A Agent Registration** | **A2A Agent Card Manifest** (`deploy/a2a/marketing_suite_agent_card.json`) | Defines agent identity, skills, tools, and endpoints for discovery in Gemini Enterprise for authorized QHHE workspace users (`js@qhhe.net`). |
| **IaC Management** | Pulumi `infra/__main__.py` with `gcp.vertex.AiReasoningEngine` / artifact deployment | Reproducible across `dev` (`agentic-marketing-suite`) and `prod` (`agentic-marketing-suite-prod`). |
| **Testing Contract** | 257 existing offline tests remain green; add dedicated offline unit tests for Reasoning Engine and A2A specs | Complete offline test coverage with mocked Firestore and Gemini backends. |

---

## Tasks Breakdown

### Task 1: Reasoning Engine Core Implementation (`suite/reasoning_engine/`)

**Files:**
- Create: `suite/reasoning_engine/__init__.py`
- Create: `suite/reasoning_engine/engine.py`
- Create: `suite/reasoning_engine/tools.py`

**Objective:**
Implement the `MarketingSuiteReasoningEngine` class adhering to Vertex AI Reasoning Engine protocol, exposing typed domain query tools over Firestore and conversational synthesis via Gemini 3.7 Flash.

- [x] **Step 1.1:** Implement query tools in `suite/reasoning_engine/tools.py`:
  - `get_client_summary(client_id: str) -> dict`: Reads client profile, industry, target budget, and active lifecycle status.
  - `get_audience_and_competition(client_id: str) -> dict`: Reads `audience_segments` and `competitive_map` memory blocks.
  - `get_marketing_strategy(client_id: str) -> dict`: Reads `active_strategy` (thesis, channel mix, budget allocation, KPI targets).
  - `get_content_and_campaigns(client_id: str) -> dict`: Reads `campaign_registry` and `content_calendar`.
  - `get_creative_deliverables(client_id: str) -> dict`: Reads `copy_assets`, `visual_assets`, and `message_flows`.
  - `get_run_execution_status(client_id: str, run_id: str | None = None) -> dict`: Checks current gate status, latest run timestamp, and pending review items.
- [x] **Step 1.2:** Implement `MarketingSuiteReasoningEngine` in `suite/reasoning_engine/engine.py`:
  - Inherits/follows standard Vertex Reasoning Engine interface (`set_up()`, `query(prompt, client_id, **kwargs)`).
  - System prompt grounded in professional Mexican Spanish (`es-MX`), structured output formatting, and reference data citations.
  - Uses `google-genai` client configured with Gemini 3.7 Flash (`gemini-3.7-flash`).

---

### Task 2: A2A Agent Card & OpenAPI Discovery Manifest (`deploy/a2a/`)

**Files:**
- Create: `deploy/a2a/marketing_suite_agent_card.json`
- Create: `deploy/a2a/openapi_spec.yaml`

**Objective:**
Define the A2A (Agent-to-Agent) agent card and OpenAPI service specification required to register the Marketing Suite into Gemini Enterprise.

- [x] **Step 2.1:** Create `deploy/a2a/marketing_suite_agent_card.json`:
  - Agent Name: `QHHE Marketing Suite Agent` (`qhhe-marketing-suite`)
  - Description: Conversational interface to the 19-agent marketing intelligence engine.
  - Capabilities & Skills: Audience segmentation, competitive radar, campaign planning, content calendar inspection, and creative specifications.
  - Target Audience: Internal QHHE users (`js@qhhe.net`).
- [x] **Step 2.2:** Create `deploy/a2a/openapi_spec.yaml` defining REST endpoints fronting the reasoning engine queries.

---

### Task 3: Pulumi IaC Support for Reasoning Engine (`infra/`)

**Files:**
- Modify: `infra/__main__.py`
- Modify: `infra/Pulumi.dev.yaml`
- Modify: `infra/Pulumi.prod.yaml`

**Objective:**
Add infrastructure definitions in Pulumi to provision and configure the Vertex AI Reasoning Engine and associated IAM permissions.

- [x] **Step 3.1:** Add `aiplatform.reasoningEngines` permissions to `suite-runner` and `console-web` service accounts.
- [x] **Step 3.2:** Export Reasoning Engine endpoint metadata in Pulumi stack outputs (`reasoning_engine_id`, `reasoning_engine_resource_name`).

---

### Task 4: Offline Unit & Contract Tests

**Files:**
- Create: `tests/reasoning_engine/__init__.py`
- Create: `tests/reasoning_engine/test_engine.py`
- Create: `tests/reasoning_engine/test_tools.py`
- Create: `tests/reasoning_engine/test_a2a_card.py`

**Objective:**
Author full offline unit tests verifying Reasoning Engine initialization, tool execution against offline fixtures, and schema validation of A2A agent cards.

- [x] **Step 4.1:** Test all query tools in `test_tools.py` using offline memory/fixture data.
- [x] **Step 4.2:** Test `MarketingSuiteReasoningEngine.query()` with mocked Gemini client in `test_engine.py`.
- [x] **Step 4.3:** Validate `deploy/a2a/marketing_suite_agent_card.json` against standard A2A schema specifications in `test_a2a_card.py`.
- [x] **Step 4.4:** Run `uv run --all-extras pytest -q` ensuring all 257+ tests pass.

---

### Task 5: Documentation & Session Closeout

**Files:**
- Modify: `ROADMAP.md`
- Modify: `AGENTS.md`
- Create: `docs/session_logs/2026-08-23_phase-7-gemini-enterprise-surface.md`

**Objective:**
Document Phase 7 architecture, usage guide for Gemini Enterprise integration, and update project roadmap.

- [x] **Step 5.1:** Update `ROADMAP.md` marking Phase 7 complete / live.
- [x] **Step 5.2:** Create session log `docs/session_logs/2026-08-23_phase-7-gemini-enterprise-surface.md`.
- [x] **Step 5.3:** Verify entire test suite is green (`uv run --all-extras pytest -q`).
