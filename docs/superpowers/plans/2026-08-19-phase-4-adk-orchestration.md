# Phase 4 — ADK 2.x Orchestration Implementation Plan (DRAFT — verified API notes)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status: draft.** API surface verified against google-adk 2.7.1 on 2026-08-19;
> finalize task steps when the phase starts.

**Goal:** The 19-agent DAG runs as an ADK 2.x graph `Workflow` on Cloud Run, pausing at human gates and resuming on Firestore gate approval — the legacy Cloud Workflows YAML retired.

**Verified API facts (google-adk 2.7.1, probed locally — trust these over blog posts):**
- Module is `google.adk.workflow` (singular). Exports: `Workflow`, `Edge`, `Node`, `BaseNode`, `FunctionNode`, `JoinNode`, `RetryConfig`, `START`, `DEFAULT_ROUTE`, `NodeTimeoutError`.
- All are Pydantic models. `Workflow` fields: `name, description, rerun_on_resume, wait_for_output, retry_config, timeout, input_schema, output_schema, state_schema, edges, max_concurrency, graph`. `Edge` fields: `from_node, to_node, route`.
- `FunctionNode` fields add `auth_config, parameter_binding` — one per suite agent, wrapping `BaseAgent.run`.
- **HITL is NOT `NodeInterruptedError`** (that class does not exist in 2.7.1). The mechanism is request-input interrupt events: `google.adk.workflow.utils._workflow_hitl_utils` provides `create_request_input_event`, `RequestInput`, `get_request_input_interrupt_ids`, `create_request_input_response` — a node emits a request-input event to pause; the runner resumes with a response event. Gate design: gate nodes emit request-input; the resume payload comes from the Firestore gate doc (approved/returned) written by `clients.set_gate_status`.
- Sessions: `google.adk.sessions` → `BaseSessionService`, `InMemorySessionService`, `DatabaseSessionService`, `VertexAiSessionService`. No Firestore session service in Python — implement `BaseSessionService` over Firestore or defer to `DatabaseSessionService`.
- Retries: per-node `RetryConfig`; per-workflow default via `Workflow.retry_config`.
- Dep pinned: `pyproject.toml` extra `adk = ["google-adk>=2.7,<3"]`.

**Sketch (finalize into tasks at phase start):**
1. `suite/orchestration/adk_workflow.py`: build `Workflow` from `PIPELINE` (FunctionNode per step, edges from `reads`/layer order, gate nodes after human-gated steps).
2. Firestore-backed session service (or DatabaseSessionService on the Phase 5 Cloud SQL).
3. Runner entrypoint for Cloud Run Job; resume path triggered by gate-doc change (Eventarc on Firestore write, or poll-on-start).
4. Offline tests: workflow topology mirrors `PIPELINE` exactly (node count, edge set, gate placement); gate pause/resume with fake session service.
5. Retire `deploy/workflows/suite-pipeline.yaml` + `deploy/cloudbuild.yaml` rewrite (image → Artifact Registry from Phase 1).
