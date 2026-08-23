# Phase 8 — Real Distribution Integrations (Meta Ads & Resend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real distribution adapters for Meta Marketing API (Layer 4/5 paid media) and Resend API (Layer 4/5 email/messaging flows) behind the FastMCP `platform_apis` server, guarded by a strict Human Financial Authorization Gate (`#1ebe82`) and a default zero-risk `dry_run` simulation mode.

---

## Architectural Context & Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Target Channels** | **Meta Ads API** (Paid media) & **Resend API** (Email & flows) | Primary distribution channels for QHHE clients (covers Instagram/Facebook ads and email newsletters/nurture flows). |
| **Execution Domain** | **FastMCP `platform_apis`** server (`suite/mcp/server.py`) & Python distribution layer (`suite/distribution/`) | Decoupled tool layer runnable both as a standalone Cloud Run service and as direct library calls within the pipeline or Django console. |
| **Financial Gate (#1ebe82)** | **Mandatory Human Financial Authorization** (`suite/distribution/financial_gate.py`) | No spend or bulk email dispatch occurs without verified `gate_status == "approved"` and `authorization.status == "authorized"` in Firestore with budget ceiling checks. |
| **Execution Safety** | **`SUITE_DISTRIBUTION_MODE=dry_run` (default)** | Production calls require explicit opt-in (`SUITE_DISTRIBUTION_MODE=live`); in `dry_run`, all API calls are simulated, validated against official schemas, and logged to audit trails with zero financial charge. |
| **Credential Management** | **Secret Manager** (`meta-access-token`, `resend-api-key`) in cloud; local vault `~/.agent_dispatcher/` offline | Zero API keys or tokens in code or repository. |
| **Testing Contract** | All 271 existing tests remain 100% green; add full offline test suite for distribution adapters, financial gate, and MCP tools | Complete offline verification with mocked HTTP responses and dry-run validation. |

---

## Tasks Breakdown

### Task 1: Distribution Adapters Core (`suite/distribution/`)

**Files:**
- Create: `suite/distribution/__init__.py`
- Create: `suite/distribution/meta_ads.py`
- Create: `suite/distribution/resend_email.py`
- Create: `suite/distribution/financial_gate.py`

**Objective:**
Implement robust API clients for Meta Marketing API and Resend API, with built-in `dry_run` simulation, schema validation, and financial authorization enforcement.

- [x] **Step 1.1:** Implement `suite/distribution/financial_gate.py`:
  - `verify_financial_authorization(client_id: str, channel: str, proposed_spend_mxn: float) -> tuple[bool, str]`:
    Checks Firestore `ad_campaign_log` / `active_strategy` gate status, ensures status is `"approved"`, confirms spend does not exceed approved budget ceiling, and records audit entry.
- [x] **Step 1.2:** Implement `suite/distribution/meta_ads.py`:
  - `MetaAdsClient`:
    - `create_campaign(client_id, name, objective, daily_budget_mxn, dry_run=True) -> dict`
    - `create_ad_set(campaign_id, targeting_spec, bid_amount, dry_run=True) -> dict`
    - `create_creative_and_ad(ad_set_id, headline, body, image_url, destination_url, dry_run=True) -> dict`
    - `fetch_ad_metrics(platform, account_id, since) -> dict`
- [x] **Step 1.3:** Implement `suite/distribution/resend_email.py`:
  - `ResendEmailClient`:
    - `send_email_campaign(client_id, subject, html_content, audience_segment, dry_run=True) -> dict`
    - `send_nurture_message(client_id, recipient, message_template, dry_run=True) -> dict`
    - `fetch_email_metrics(client_id, campaign_id) -> dict`

---

### Task 2: FastMCP `platform_apis` Server Wiring (`suite/mcp/server.py`)

**Files:**
- Modify: `suite/mcp/server.py`

**Objective:**
Wire the real Meta Ads and Resend distribution tools into `build_platform_apis_server()`, replacing the `NotImplementedError` stubs with guarded, typed MCP tools.

- [x] **Step 2.1:** Implement MCP tools in `build_platform_apis_server()`:
  - `@server.tool() deploy_meta_campaign(client_id: str, campaign_spec: dict, dry_run: bool = True) -> dict`
  - `@server.tool() dispatch_email_campaign(client_id: str, email_spec: dict, dry_run: bool = True) -> dict`
  - `@server.tool() fetch_ad_metrics(platform: str, account_id: str, since: str) -> dict`
  - `@server.tool() fetch_email_metrics(client_id: str, campaign_id: str) -> dict`
- [x] **Step 2.2:** Ensure all tools invoke `verify_financial_authorization()` when `dry_run=False`.

---

### Task 3: Offline Unit & Gate Tests (`tests/distribution/`)

**Files:**
- Create: `tests/distribution/__init__.py`
- Create: `tests/distribution/test_financial_gate.py`
- Create: `tests/distribution/test_meta_ads.py`
- Create: `tests/distribution/test_resend_email.py`
- Create: `tests/distribution/test_mcp_platform_apis.py`

**Objective:**
Author comprehensive offline unit tests verifying financial gate enforcement, dry-run simulation, Meta Ads payload generation, Resend email formatting, and MCP tool invocations.

- [x] **Step 3.1:** Test `verify_financial_authorization()` in `test_financial_gate.py`:
  - Assert unauthorized spec is blocked with clear error reason.
  - Assert spend exceeding approved budget ceiling is rejected.
  - Assert approved gate permits execution and logs audit trail.
- [x] **Step 3.2:** Test Meta Ads client in `test_meta_ads.py` (dry-run output structure, API mocks).
- [x] **Step 3.3:** Test Resend client in `test_resend_email.py` (dry-run output structure, API mocks).
- [x] **Step 3.4:** Test FastMCP `platform_apis` server tools in `test_mcp_platform_apis.py`.
- [x] **Step 3.5:** Run `uv run --all-extras pytest -q` ensuring all 271+ tests pass.

---

### Task 4: Documentation & Roadmap Closeout

**Files:**
- Modify: `ROADMAP.md`
- Modify: `AGENTS.md`
- Create: `docs/session_logs/2026-08-23_phase-8-real-distribution-integrations.md`

**Objective:**
Document Phase 8 architecture, update ROADMAP marking Phase 8 completed, and record live session log.

- [x] **Step 4.1:** Update `ROADMAP.md` marking Phase 8 complete.
- [x] **Step 4.2:** Update `AGENTS.md` with final test count.
- [x] **Step 4.3:** Create session log `docs/session_logs/2026-08-23_phase-8-real-distribution-integrations.md`.
- [x] **Step 4.4:** Run `uv run --all-extras pytest -q` to confirm full test suite passes.
