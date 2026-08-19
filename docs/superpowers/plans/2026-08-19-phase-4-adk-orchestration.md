# Phase 4 — ADK 2.x Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The 19-agent DAG runs as an ADK 2.x graph `Workflow` on Cloud Run, pausing at human gates and resuming on Firestore gate approval — the legacy Cloud Workflows YAML retired.

**Verified API facts (google-adk 2.7.1, probed locally — trust these over blog posts):**
- Module is `google.adk.workflow` (singular). Exports: `Workflow`, `Edge`, `Node`, `BaseNode`, `FunctionNode`, `JoinNode`, `RetryConfig`, `START`, `DEFAULT_ROUTE`, `NodeTimeoutError`.
- All are Pydantic models. `Workflow` fields: `name, description, rerun_on_resume, wait_for_output, retry_config, timeout, input_schema, output_schema, state_schema, edges, max_concurrency, graph`. `Edge` fields: `from_node, to_node, route`.
- `FunctionNode` fields add `auth_config, parameter_binding` — one per suite agent, wrapping `BaseAgent.run`.
- **HITL is NOT `NodeInterruptedError`** (that class does not exist in 2.7.1). The mechanism is request-input interrupt events: `google.adk.workflow.utils._workflow_hitl_utils` provides `create_request_input_event`, `RequestInput`, `get_request_input_interrupt_ids`, `create_request_input_response` — a node emits a request-input event to pause; the runner resumes with a response event. Gate design: gate nodes emit request-input; the resume payload comes from the Firestore gate doc (approved/returned) written by `clients.set_gate_status`.
- Sessions: `google.adk.sessions` → `BaseSessionService`, `InMemorySessionService`, `DatabaseSessionService`, `VertexAiSessionService`. No Firestore session service in Python — implement `BaseSessionService` over Firestore or defer to `DatabaseSessionService`.
- Retries: per-node `RetryConfig`; per-workflow default via `Workflow.retry_config`.
- Dep pinned: `pyproject.toml` extra `adk = ["google-adk>=2.7,<3"]`.

**Executed spike (2026-08-19, all verified locally against 2.7.1):**
- Construction: `FunctionNode(func=fn, name=...)`; `Edge(from_node=<node instance or START>, to_node=<node instance>)` — edges take node INSTANCES, not name strings.
- Entry point: `Runner(node=workflow, app_name=..., session_service=...)`; seed state via `session_service.create_session(app_name, user_id, session_id, state={...})` (the `state_delta` kwarg of `runner.run` does NOT seed state before the first node); then `runner.run(user_id=..., session_id=..., new_message=None)`.
- State flow: functions declare `ctx: Context` and mutate `ctx.state[...]`; plain return values become `Event.output` (per-node output), NOT state. Params bind from state by name.
- HITL verified end-to-end: gate function returns `RequestInput(prompt=..., keys=[...])` → run pauses (downstream never executes). Collect ids via `get_request_input_interrupt_ids(event)`; resume with `runner.run(..., new_message=types.Content(role="user", parts=[create_request_input_response(interrupt_id, {key: value})]))` → workflow continues.
- Resume subtlety: with default `rerun_on_resume=False` the gate function is NOT re-executed on resume — the workflow proceeds past it. So don't rely on the gate node to write the decision into state on resume; the decision's source of truth is the Firestore gate doc (`clients.set_gate_status`), which the resume driver reads.

## Tasks

### Task 1: `suite/orchestration/adk_workflow.py` (test-first)
`build_workflow(auto_approve: bool) -> Workflow`: one `FunctionNode` per `PIPELINE`
step (name `agent_<id>` with dots→underscores), sequential edges in PIPELINE order
(same semantics as `run_pipeline` today). Each agent fn(ctx): payload = client_id +
inputs + upstream blocks from `ctx.state["blocks"]`; call the step's `run`; store
result block(s) into state; record `gate_status`. After each human-gated step
(gate in `GATED`), a gate node `gate_<id>`: if auto_approve → pass; else read the
Firestore gate doc via `clients.read_gate_status` — approved/auto_approved → pass;
else return `RequestInput(prompt=..., keys=["decision"])` (pause).
Tests (offline): topology (19 agent nodes + gate nodes after exactly the GATED
steps, edge chain in order); full fixture run via Runner+InMemorySessionService
(auto_approve) → 20 blocks in final state; gated run pauses at first gate,
resume after set_gate_status("approved") completes downstream.
- [ ] tests → fail → implement → 221+N green → commit

### Task 2: `read_gate_status` in clients.py (tiny, test-first)
`read_gate_status(client_id, block) -> str | None` for both backends.
- [ ] test + implement + commit (folded into Task 1's commit if convenient)

### Task 3: `suite/infra/adk_sessions.py` — FirestoreSessionService
Implements the 4 abstract methods + `append_event` persistence over
`adk_sessions/{app}:{user}:{session}` root docs + `events` subcollection
(events too large for one doc). Offline tests with FakeFirestore.
- [ ] tests → implement → commit

### Task 4: `suite/orchestration/adk_entrypoint.py` + live dev proof (exit criterion)
CLI: `start` (create session, run until pause/complete) and `resume` (rebuild
resume Content from pending interrupt ids + gate docs, continue). Live proof
against dev Firestore: fixture LLM + gcp backend, no auto-approve → pauses at
gate 1.1; `clients.set_gate_status(...approved)`; `resume` → run completes.
- [ ] live proof → record in plan → ROADMAP ✅ → commit + push

### Task 5: retire legacy choreography
Delete `deploy/workflows/suite-pipeline.yaml`; note in deploy/README that
orchestration is the ADK workflow (containerization lands in Phase 6).
- [ ] commit
