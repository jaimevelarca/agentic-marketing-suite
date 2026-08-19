"""Agent 2.1 — Strategy Orchestrator (Layer 2).

Built on `suite/agents/base.py`. The production system prompt lives as a
versioned asset at `suite/agents/layer2/prompts/strategy_orchestrator_system.txt`
(kept in sync with DEL-21, the human-readable deliverable; the .txt is the
machine source of truth loaded at runtime).

This is the Suite's ONLY binding-decision agent and the ONLY agent on Opus
(model_deep) — see project/specs/AGENT_COST_MODEL.md (2.1) and the spec. It reads
the four Layer-1 intelligence blocks and synthesizes one immutable-per-cycle
strategy. It writes TWO coupled memory blocks: `active_strategy` (the block in
`memory_block`/`schema_name`) and `kpi_contracts`, which the model embeds as a
nested object inside OUTPUT-1; route() splits that out into its own block so
Layer 6 can read it directly.

Binding human gate: gate_status defaults to "pending_review" and MUST be flipped
to "approved" by a human reviewer before any Layer 3+ agent reads active_strategy.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra import clients
from infra.config import settings

# Upstream memory blocks this agent reads (ARCHITECTURE.md memory map). The
# orchestrator injects each under its block-name key in the payload.
UPSTREAM_BLOCKS = ("client_profile", "audience_segments", "competitive_map", "trend_signals")

# Per-block truncation budget (chars) so a large injected block can't blow the
# user turn; the system prompt + reasoning headroom matter more than raw context.
_MAX_BLOCK_CHARS = 24000


class Agent21(BaseAgent):
    """Strategy Orchestrator — synthesizes active_strategy + embedded
    kpi_contracts from the four Layer-1 intelligence blocks. Binding gate."""

    def build_user_turn(self, payload: dict) -> str:
        client_id = payload.get("client_id", "unknown")
        parts = [
            "## STRATEGY SYNTHESIS REQUEST — AGENT 2.1\n",
            f"client_id: {client_id}\n",
            "Synthesize the binding marketing strategy for this client's current "
            "cycle from the upstream Layer-1 intelligence below. Produce the three "
            "required outputs. Some upstream blocks may be missing — degrade "
            "gracefully and lower confidence accordingly.\n",
        ]
        for block in UPSTREAM_BLOCKS:
            data = payload.get(block)
            if data:
                blob = json.dumps(data, ensure_ascii=False, indent=2)[:_MAX_BLOCK_CHARS]
                parts.append(f"### UPSTREAM MEMORY BLOCK: {block}\n{blob}\n")
            else:
                parts.append(f"### UPSTREAM MEMORY BLOCK: {block}\n(not provided — note in upstream_provenance and lower confidence)\n")

        if payload.get("operator_notes"):
            parts.append(f"### OPERATOR NOTES\n{payload['operator_notes']}\n")

        parts.append("\n---\nProduce OUTPUT 1 (active_strategy JSON, with embedded kpi_contracts), "
                     "OUTPUT 2 (ES-MX strategy brief), and OUTPUT 3 (English binding gate summary).")
        return "\n".join(parts)

    def route(self, client_id, obj, outputs, valid, err) -> None:
        # Default routing: persist active_strategy to its memory block (Cloud SQL
        # in prod / in-process offline) + open a review-queue doc. The binding
        # gate makes any non-"approved" status worth a reviewer's attention; the
        # base class already escalates invalid output / "blocked" to urgent.
        super().route(client_id, obj, outputs, valid, err)

        # Agent-2.1-specific: split the embedded kpi_contracts out into its own
        # memory block so Layer 6 (6.1) can read it without parsing the strategy.
        if valid and client_id and obj is not None:
            gate = obj.get("gate_status", "pending_review")
            kpi = obj.get("kpi_contracts")
            if kpi is not None:
                clients.write_memory_block(client_id, "kpi_contracts", kpi, gate)
            # Signal the binding handoff so the orchestration layer knows a human
            # gate is pending before Layer 3 may consume the strategy.
            clients.publish(settings.handoff_topic, {
                "client_id": client_id,
                "agent": self.agent_id,
                "block": self.memory_block,
                "gate_status": gate,
                "binding": True,
            })


AGENT = Agent21(
    agent_id="2.1",
    prompt_asset="agents/layer2/prompts/strategy_orchestrator_system.txt",
    model=settings.model_deep,   # Opus — binding deep reasoning ONLY (cost model 2.1)
    max_tokens=16000,
    schema_name="active_strategy",
    memory_block="active_strategy",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id, and the injected
    upstream blocks client_profile / audience_segments / competitive_map /
    trend_signals (any may be absent), optional operator_notes."""
    return AGENT.run(payload)
