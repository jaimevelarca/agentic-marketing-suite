"""Agent 6.3 — Optimization Engine (Layer 6 — Analytics & Feedback).

Built on `suite/agents/base.py`. The closed-loop optimizer at the end of the
Suite: it takes the measured results (`performance_history`, written by Agent
6.1) and its own accumulated `content_learnings` from prior cycles, and turns
them into a small, prioritized set of optimization actions (A/B conclusions,
scale up/down, creative/copy/audience retunes, budget reallocations) plus the
durable, accumulating learnings ledger that Layer 3 (Content Planning) and
Layer 4 (Production) read on the next cycle. This is the feedback loop that lets
the Suite get better month over month instead of just reporting numbers.

Bounded automation: small, reversible moves (concluding a clear A/B winner,
pausing a clear loser, budget reallocations <=20% of source that don't raise
total spend) auto-apply (gate_status 'auto_approved'). Any reallocation >20% of
source — or any move that increases total spend — is a binding spend decision
and requires a human (gate_status 'pending_review').

The production system prompt is the versioned asset
`suite/agents/layer6/prompts/optimization_engine_system.txt` (the machine source
of truth; DEL-35 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  performance_history (6.1, primary evidence base) and content_learnings (this
  agent's OWN prior block, merged/de-duplicated forward); optionally
  kpi_contracts / active_strategy / campaign_registry / client_profile for the
  contracted KPI targets, budget math, and the client's budget ceiling.
Writes: content_learnings. Human gate: bounded automation (auto_approved /
pending_review on >20% reallocation).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 6.3) and
`agents/6.3-optimization_engine.md`. Model = Sonnet (primary reasoning — the
statistical judgment about what to change is non-trivial but not a binding spend
authorization; the binding spend decision is gated to a human, so Opus is not
warranted); system prompt cached.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra import clients
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
# performance_history is the evidence base; content_learnings is this agent's
# own prior block, carried forward and merged.
_UPSTREAM_BLOCKS = ("performance_history", "content_learnings")

# Optional grounding context (targets, budgets, constraints).
_CONTEXT_BLOCKS = ("kpi_contracts", "active_strategy", "campaign_registry", "client_profile")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent63(BaseAgent):
    """Optimization Engine — turns performance_history (+ prior content_learnings)
    into a prioritized optimization action set and a durable learnings ledger,
    applying the bounded-automation 20%-budget-reallocation gate."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## OPTIMIZATION REQUEST — AGENT 6.3\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")
        if payload.get("now"):
            # Optional explicit run timestamp; otherwise the model stamps created_at.
            parts.append(f"run_timestamp (now): {payload['now']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        # Optional grounding context (KPI targets, budgets, constraints/ceiling).
        for name in _CONTEXT_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))

        if "performance_history" not in present:
            parts.append(
                "### NO PERFORMANCE DATA\n"
                "performance_history was not provided (or is empty). Per the prompt "
                "rules, you have no evidence to optimize on: carry forward any prior "
                "content_learnings unchanged, emit empty optimization_actions and "
                "budget_reallocations arrays, set gate_status='auto_approved', explain "
                "in notes, and recommend MONITOR in OUTPUT 3. Do not invent metrics.\n"
            )

        parts.append(
            "\n---\nOptimize per the system prompt: derive a small, high-leverage set "
            "of evidence-backed optimization_actions from performance_history (vs the "
            "KPI contracts), merge/de-duplicate the durable learnings ledger forward, "
            "and record every budget move in budget_reallocations with its "
            "pct_of_source_budget. Apply the 20% bounded-autonomy line: set "
            "requires_human=true (and the block gate_status='pending_review') for any "
            "reallocation >20% of source or any total-spend increase; otherwise "
            "gate_status='auto_approved'. Keep the summary footing to the arrays and "
            "produce the three required outputs."
        )
        return "\n".join(parts)

    def route(self, client_id, obj, outputs, valid, err) -> None:
        # Default routing: write the content_learnings block + a Firestore review
        # doc (urgent on invalid/blocked, normal otherwise).
        super().route(client_id, obj, outputs, valid, err)
        # 6.3-specific: when the optimization is valid and bounded (auto_approved),
        # hand the learnings + auto-applied actions off to the downstream layers so
        # the loop closes (L3/L4 pick them up next cycle, L5 applies bounded budget
        # moves). A pending_review block waits for the human first, so we don't
        # publish it.
        if not (valid and client_id and obj is not None):
            return
        if obj.get("gate_status") == "auto_approved":
            actions = obj.get("optimization_actions", [])
            auto_actions = [a for a in actions if a.get("auto_apply")]
            clients.publish(settings.handoff_topic, {
                "client_id": client_id,
                "from_agent": self.agent_id,
                "block": self.memory_block,
                "cycle_month": obj.get("cycle_month"),
                "auto_applied_actions": auto_actions,
                "learnings": obj.get("learnings", []),
            })


AGENT = Agent63(
    agent_id="6.3",
    prompt_asset="agents/layer6/prompts/optimization_engine_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="content_learnings",
    memory_block="content_learnings",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks performance_history (6.1) and content_learnings (6.3, prior) injected
    by the orchestrator under their block names; optional kpi_contracts /
    active_strategy / campaign_registry / client_profile context; optional
    cycle_month and `now` (run timestamp)."""
    return AGENT.run(payload)
