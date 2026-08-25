"""ADK 2.x graph Workflow port of the suite DAG (roadmap Phase 4).

Builds a `google.adk.workflow.Workflow` from `orchestration.pipeline.PIPELINE`:
one FunctionNode per agent in dependency order, plus a gate node after every
human-gated step. Gate nodes pause the run (request-input interrupt) until the
block's Firestore gate doc says approved — the decision's source of truth is
`clients.set_gate_status`, written by the review UI (Phase 5).

Execution model (verified against google-adk 2.7.1 — see the Phase 4 plan):
  - session state carries: client_id, inputs, auto_approve, blocks (approved,
    downstream-visible payloads), pending_blocks (produced but awaiting a gate),
    transcript (per-agent event dicts, same shape as run_pipeline's).
  - Gate nodes use rerun_on_resume=True: on resume the gate re-reads the gate
    doc; approved → promotes the pending block and the run continues.
  - State size note: blocks live in session state, so a very large live run
    approaches Firestore's 1 MiB doc limit on persisted sessions; if that bites,
    switch state["blocks"] to block *references* resolved via
    clients.read_memory_block at payload-build time.

google-adk is an optional dependency (`.[adk]`): all ADK imports stay inside
functions so the rest of the suite imports without it.
"""
from __future__ import annotations

from infra import clients
from infra.log import get_logger
from orchestration.pipeline import GATED, PIPELINE, AgentStep, _load_run

log = get_logger("adk")

APPROVED = ("approved", "auto_approved")


def node_name(step: AgentStep) -> str:
    return "agent_" + step.id.replace(".", "_")


def gate_name(step: AgentStep) -> str:
    return "gate_" + step.id.replace(".", "_")


def _promote(step: AgentStep, obj: dict, blocks: dict) -> None:
    """Make a validated block visible to downstream agents (incl. exports)."""
    blocks[step.block] = obj
    for export_block, key in step.exports.items():
        val = obj.get(key)
        if val is not None:
            blocks[export_block] = val


def _make_agent_fn(step: AgentStep):
    def agent_fn(ctx):
        inputs = ctx.state.get("inputs") or {}
        blocks = dict(ctx.state.get("blocks") or {})
        # The run's client_id is authoritative — spread inputs FIRST so an
        # onboarding JSON carrying its own client_id can't hijack the identity
        # (agents would write one client while gates read another).
        payload: dict = {**inputs, "client_id": ctx.state["client_id"]}
        for blk in step.reads:
            if blk in blocks:
                payload[blk] = blocks[blk]

        try:
            result = _load_run(step.module)(payload)
            valid, error, structured = result.valid, result.error, result.structured
        except Exception as e:
            log.exception("agent %s crashed: %s", step.id, e)
            valid, error, structured = False, str(e), None

        entry = {"agent": step.id, "name": step.name, "layer": step.layer,
                 "gate": step.gate, "valid": valid, "error": error}
        if valid and structured:
            obj = dict(structured)
            gate_status = obj.get("gate_status", "auto_approved")
            if ctx.state.get("auto_approve") and gate_status in (
                    "pending_review", "returned", "blocked"):
                obj["gate_status"] = "approved"
            entry["gate_status"] = obj.get("gate_status")
            if step.gate in GATED and obj.get("gate_status") not in APPROVED:
                pending = dict(ctx.state.get("pending_blocks") or {})
                pending[step.block] = obj
                ctx.state["pending_blocks"] = pending
            else:
                _promote(step, obj, blocks)
                ctx.state["blocks"] = blocks
        ctx.state["transcript"] = list(ctx.state.get("transcript") or []) + [entry]

    agent_fn.__name__ = node_name(step)
    return agent_fn


def _make_gate_fn(step: AgentStep):
    def gate_fn(ctx):
        pending = dict(ctx.state.get("pending_blocks") or {})
        if step.block not in pending:
            return None  # nothing awaiting this gate (approved inline or invalid)
        status = clients.read_gate_status(ctx.state["client_id"], step.block)
        if status in APPROVED:
            blocks = dict(ctx.state.get("blocks") or {})
            obj = pending.pop(step.block)
            obj["gate_status"] = status
            _promote(step, obj, blocks)
            ctx.state["blocks"] = blocks
            ctx.state["pending_blocks"] = pending
            log.info("gate %s: %s %s — promoted", step.id, step.block, status)
            return None
        from google.adk.workflow.utils._workflow_hitl_utils import RequestInput
        log.info("gate %s: %s status=%s — pausing for human review", step.id, step.block, status)
        return RequestInput(
            prompt=(f"Human gate {step.id} ({step.gate}) on block '{step.block}': "
                    f"current status is {status!r}. Approve via the review UI "
                    f"(clients.set_gate_status) and resume."),
            keys=[f"gate_{step.id}"],
        )

    gate_fn.__name__ = gate_name(step)
    return gate_fn


def build_workflow(name: str = "agentic_marketing_suite"):
    """The full 19-agent DAG as an ADK graph Workflow (sequential, PIPELINE
    order — same execution semantics as run_pipeline, plus real gate pauses)."""
    from google.adk.workflow import Edge, FunctionNode, Workflow, START

    nodes = []
    for step in PIPELINE:
        nodes.append(FunctionNode(func=_make_agent_fn(step), name=node_name(step)))
        if step.gate in GATED:
            nodes.append(FunctionNode(func=_make_gate_fn(step), name=gate_name(step),
                                      rerun_on_resume=True))

    edges = [Edge(from_node=START, to_node=nodes[0])]
    edges += [Edge(from_node=a, to_node=b) for a, b in zip(nodes, nodes[1:])]
    return Workflow(name=name, edges=edges)
