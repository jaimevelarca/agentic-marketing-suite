"""Agent 3.1 — Monthly Marketing Deck (Layer 3 — Content Planning).

Built on `suite/agents/base.py`. Turns an approved monthly strategy into a
week-by-week editorial `content_plan`: topics, formats, channels, CTAs and
funnel stages per campaign. That plan feeds Agent 3.2 (Content Scheduler →
content_calendar) and is read by the Layer 4 production agents.

The production system prompt is the versioned asset
`suite/agents/layer3/prompts/monthly_marketing_deck_system.txt` (the machine
source of truth; DEL-23 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  active_strategy (2.1), campaign_registry (2.2), audience_segments (1.2),
  trend_signals (1.4); optionally client_profile for constraints/voice.
Writes: content_plan. Human gate: editorial review (default pending_review).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 3.1) and
`agents/3.1-monthly_marketing_deck.md`. Model = Sonnet (primary generation);
system prompt cached; monthly singleton (one run per client cycle).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
_UPSTREAM_BLOCKS = ("active_strategy", "campaign_registry", "audience_segments", "trend_signals")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent31(BaseAgent):
    """Monthly Marketing Deck — produces a per-campaign, per-week content_plan
    (editorial blueprint) from the approved strategy + campaign registry +
    audience segments + trend signals."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## CONTENT PLANNING REQUEST — AGENT 3.1\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)
        # Optional client_profile context (constraints / brand voice / blackout).
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))

        missing_required = [b for b in ("active_strategy", "campaign_registry") if b not in present]
        if missing_required:
            parts.append(
                "### MISSING REQUIRED INPUTS\n"
                f"{', '.join(missing_required)} not provided. Per the prompt rules, "
                "emit a minimal valid content_plan with gate_status='blocked' and "
                "explain in planning_notes / OUTPUT 3.\n"
            )

        parts.append(
            "\n---\nBuild the monthly content_plan per the system prompt: plan content "
            "per campaign, per week (topic · format · channel · CTA · funnel_stage), keep the "
            "summary footing to the items, and produce the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent31(
    agent_id="3.1",
    prompt_asset="agents/layer3/prompts/monthly_marketing_deck_system.txt",
    model=settings.model_primary,
    max_tokens=32000,   # content_plan = campaigns x weeks x items; a full monthly plan is large
    schema_name="content_plan",
    memory_block="content_plan",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks active_strategy / campaign_registry / audience_segments /
    trend_signals (injected by the orchestrator under their block names);
    optional client_profile and cycle_month."""
    return AGENT.run(payload)
