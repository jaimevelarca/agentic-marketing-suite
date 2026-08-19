"""Agent 3.3 — Approval Workflow (Layer 3 — Content Planning).

Built on `suite/agents/base.py`. The review-queue manager for the whole Suite:
it takes the scheduled content for a cycle and routes each item through the
single human reviewer's queue — deciding lane (human_review / auto_publish /
escalate / hold), priority, reviewer role, and a review-by deadline — and emits
the `approval_log` ledger that Layer 6 reporting and the Firestore review-queue
UI consume. It does NOT write content; it dispatches.

The production system prompt is the versioned asset
`suite/agents/layer3/prompts/approval_workflow_system.txt` (the machine source
of truth; DEL-25 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  content_calendar (3.2, primary upstream); content_plan (3.1) as a fallback
  when the calendar is absent/thin; optionally client_profile for constraint-
  driven escalation (approval_chain / pricing_claims / legal / brand-safety).
Writes: approval_log. Human gate: queue manager — autonomous; this agent's own
gate_status is always 'auto_approved' (per-item gating lives in entries[]).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 3.3) and
`agents/3.3-approval_workflow.md`. Model = Haiku (routing/dispatch tier); system
prompt cached; bursty (fires per cycle over many small items) so cache hit is
high. Cheapest agent in the fleet ($0.003/run).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream blocks this agent reads, in fallback priority order. content_calendar
# (Agent 3.2) is the canonical scheduled list; content_plan (Agent 3.1) is the
# editorial fallback when no calendar has been produced yet.
_UPSTREAM_BLOCKS = ("content_calendar", "content_plan")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the Haiku input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent33(BaseAgent):
    """Approval Workflow — routes each scheduled content item through the single
    reviewer's queue and emits the `approval_log` routing ledger."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## REVIEW-QUEUE ROUTING REQUEST — AGENT 3.3\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")
        if payload.get("now"):
            # Optional explicit run timestamp for overdue detection; otherwise the
            # model uses created_at it stamps.
            parts.append(f"run_timestamp (now): {payload['now']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)
        # Optional client_profile context — constraints drive Rule-1 escalation.
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))

        if not present:
            parts.append(
                "### NO ROUTABLE INPUT\n"
                "Neither content_calendar nor content_plan was provided. Per the prompt "
                "rules, emit a minimal valid approval_log with an empty entries array, "
                "gate_status='auto_approved', source_block='none', explain in notes, and "
                "recommend MONITOR in OUTPUT 3.\n"
            )
        else:
            parts.append(f"### SOURCE BLOCK FOR ROUTING: {present[0]}\n")

        parts.append(
            "\n---\nRoute every scheduled content item through the single reviewer's "
            "queue per the system prompt (first-match rule order; dependency-hold and "
            "overdue overlays). Set gate_status='auto_approved' on your own output, keep "
            "the summary footing to the entries, and produce the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent33(
    agent_id="3.3",
    prompt_asset="agents/layer3/prompts/approval_workflow_system.txt",
    model=settings.model_routing,   # Haiku — routing / dispatch tier
    max_tokens=16000,
    schema_name="approval_log",
    memory_block="approval_log",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks content_calendar (3.2) and/or content_plan (3.1) injected by the
    orchestrator under their block names; optional client_profile, cycle_month,
    and `now` (run timestamp for overdue detection)."""
    return AGENT.run(payload)
