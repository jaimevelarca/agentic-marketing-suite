"""Agent 3.2 — Content Scheduler (Layer 3 — Content Planning).

Built on `suite/agents/base.py`. Turns an approved editorial `content_plan`
(Agent 3.1) into a dated, timed, platform-assigned `content_calendar`: every
planned item becomes exactly one slot with a concrete publish date/time (in the
local market timezone), the resolved per-platform cadence rules, and a
production due date (publish minus channel lead time) so the Layer 4 production
agents know each asset's deadline. Layer 5 (5.1 Campaign Launcher, 5.2 Social
Publisher) reads the calendar to know when/where to publish; Layer 6 (6.1
Performance Analytics) reads it for slot-level attribution.

The production system prompt is the versioned asset
`suite/agents/layer3/prompts/content_scheduler_system.txt` (the machine source
of truth; DEL-24 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  content_plan (3.1, primary), campaign_registry (2.2, campaign timing/priority);
  optionally the raw onboarding input platform_rules (per-platform cadence
  overrides) and client_profile (blackout dates / locations / constraints).
Writes: content_calendar. Human gate: calendar review (default pending_review).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 3.2) and
`agents/3.2-content_scheduler.md`. Model = Sonnet (primary generation; the
date/time/cadence reasoning is judgment-heavy but not a binding spend decision);
system prompt cached; monthly singleton (one run per client cycle).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
_UPSTREAM_BLOCKS = ("content_plan", "campaign_registry")

# Raw onboarding inputs (not memory blocks) this agent may consume.
_RAW_INPUTS = ("platform_rules",)

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent32(BaseAgent):
    """Content Scheduler — produces a dated content_calendar from the approved
    content_plan + campaign_registry, applying per-platform cadence/timing rules
    (overridable by platform_rules) and client blackout windows."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## CONTENT SCHEDULING REQUEST — AGENT 3.2\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        # Optional raw onboarding overrides (per-platform cadence/timing rules).
        for name in _RAW_INPUTS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))

        # Optional client_profile context (blackout dates / locations / constraints).
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))

        if "content_plan" not in present:
            parts.append(
                "### MISSING REQUIRED INPUT\n"
                "content_plan not provided. Per the prompt rules, emit a minimal valid "
                "content_calendar with gate_status='blocked' and explain in "
                "scheduling_notes / OUTPUT 3. Do not invent content items.\n"
            )

        parts.append(
            "\n---\nBuild the content_calendar per the system prompt: assign every "
            "content_plan item to exactly one dated, timed, platform-assigned slot "
            "(local market time), apply the resolved per-platform cadence rules and "
            "blackout windows, compute each slot's production_due_date, keep the summary "
            "footing to the slots, and produce the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent32(
    agent_id="3.2",
    prompt_asset="agents/layer3/prompts/content_scheduler_system.txt",
    model=settings.model_primary,
    max_tokens=32000,   # content_calendar (plan x weeks x items) is large; 16000 truncated the JSON mid-block on real client data — match 3.1's ceiling
    schema_name="content_calendar",
    memory_block="content_calendar",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks content_plan (3.1) / campaign_registry (2.2) injected by the
    orchestrator under their block names; optional raw platform_rules and
    optional client_profile."""
    return AGENT.run(payload)
