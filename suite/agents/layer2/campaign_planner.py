"""Agent 2.2 — Campaign Planner (Layer 2).

Built on `suite/agents/base.py`. The production system prompt lives as a
versioned asset at `suite/agents/layer2/prompts/campaign_planner_system.txt`
(kept in sync with DEL-22 — DEL-22 is the human-readable deliverable, the .txt
is the machine source of truth loaded at runtime).

Job: decompose an approved `active_strategy` into a `campaign_registry` memory
block — campaign themes, messaging pillars, timing, per-campaign budget split,
and success metrics — for Layers 3-6. Human gate: review (gate_status defaults
to "pending_review"; the human approves before Layer 3 reads the block).

Reads (upstream memory blocks the orchestrator injects): active_strategy
(binding frame), client_profile, audience_segments. Writes: campaign_registry.

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (2.2) and the
agent spec `agents/2.2-campaign_planner.md`. Model = Sonnet (primary
generation); system prompt cached. ~$0.095/run.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings


class Agent22(BaseAgent):
    """Campaign Planner — turns the approved strategy + profile + segments into
    a draft campaign_registry for human review."""

    # The upstream memory blocks this agent reads. The orchestrator injects each
    # one under its block-name key in the payload.
    UPSTREAM_BLOCKS = ("active_strategy", "client_profile", "audience_segments")

    @staticmethod
    def _section(title: str, obj, *, limit: int = 6000) -> str:
        """Render one injected block as a labelled, size-capped JSON section.
        Very large blocks are truncated so the user turn stays inside the model
        context budget (cost discipline; see AGENT_COST_MODEL.md)."""
        try:
            blob = json.dumps(obj, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            blob = str(obj)
        if len(blob) > limit:
            blob = blob[:limit] + "\n... [truncated]"
        return f"### {title}\n{blob}\n"

    def build_user_turn(self, payload: dict) -> str:
        cycle = payload.get("cycle_label") or "current-cycle"
        parts = [
            "## CAMPAIGN PLANNING REQUEST — AGENT 2.2\n",
            f"Client ID: {payload.get('client_id', 'unknown')}",
            f"Cycle label: {cycle}\n",
            "### UPSTREAM MEMORY BLOCKS\n",
        ]
        # active_strategy is the binding frame; always present it (even if empty,
        # so the model can apply the BLOCKED-frame rule from the prompt).
        parts.append(self._section(
            "active_strategy (Agent 2.1 — BINDING; budget + KPIs + channel mix)",
            payload.get("active_strategy", {}),
        ))
        if payload.get("client_profile"):
            parts.append(self._section(
                "client_profile (Agent 1.1 — industry, USP, voice, constraints, seasonality)",
                payload["client_profile"],
            ))
        if payload.get("audience_segments"):
            parts.append(self._section(
                "audience_segments (Agent 1.2 — segment ids, ICPs, pain points)",
                payload["audience_segments"],
            ))
        if payload.get("operator_notes"):
            parts.append(f"### OPERATOR NOTES (steering)\n{payload['operator_notes']}\n")
        parts.append(
            "\n---\nPlan the campaign_registry for this cycle. Validate the strategy "
            "frame first, then produce the three required outputs in order."
        )
        return "\n".join(parts)


AGENT = Agent22(
    agent_id="2.2",
    prompt_asset="agents/layer2/prompts/campaign_planner_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="campaign_registry",
    memory_block="campaign_registry",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id, active_strategy
    (required upstream block), client_profile?, audience_segments?, cycle_label?,
    operator_notes?. Returns an AgentResult; routing (Cloud SQL memory block +
    Firestore review doc) happens inside AGENT.run via base.py."""
    return AGENT.run(payload)
