"""Agent 4.1 — Copy + Prompt Engine (Layer 4 — Production).

Built on `suite/agents/base.py`. Turns the editorial content plan/calendar into
finished, on-brand, client-facing copy (hooks, captions, CTAs, A/B variants,
hashtags) AND the fal.ai image-generation prompts (flux-2-pro / ideogram-3.0)
that Agent 4.2 (Visual Creative) renders. Writes the `copy_assets` memory block,
read by Layer 5 (distribution) and Layer 6 (analytics).

The production system prompt is the versioned asset
`suite/agents/layer4/prompts/copy_prompt_engine_system.txt` (the machine source
of truth; DEL-26 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  content_calendar (L3) — required driver (content_plan accepted as a fallback
  key for the 3.1 deck output); audience_segments (1.2); competitive_map (1.3);
  client_profile (1.1) for constraints / brand voice / visual identity.
Writes: copy_assets. Human gate: risk-tiered — default pending_review; the model
emits auto_approved only when every asset is low-risk (rollup in the prompt).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 4.1) and
`agents/4.1-copy_prompt_engine.md`. Model = Sonnet (primary generation); system
prompt cached; bursty/high-volume agent → high warm-cache hit fraction.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
# content_calendar is the required driver; content_plan (the 3.1 deck output) is
# accepted as a fallback key so the agent works whether it is fed the dated
# calendar (3.2) or the editorial plan (3.1).
_UPSTREAM_BLOCKS = ("content_calendar", "content_plan", "audience_segments", "competitive_map", "client_profile")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent41(BaseAgent):
    """Copy + Prompt Engine — produces per-item client-facing copy (ES-MX) plus
    image-gen prompts (flux-2-pro / ideogram-3.0) from the content plan/calendar,
    audience segments, competitive map and client profile; risk-tiers each asset."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## COPY + PROMPT PRODUCTION REQUEST — AGENT 4.1\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        # The driver is the content plan/calendar (either key satisfies it).
        if "content_calendar" not in present and "content_plan" not in present:
            parts.append(
                "### MISSING REQUIRED INPUT\n"
                "Neither content_calendar nor content_plan was provided. Per the prompt "
                "rules, emit a minimal valid copy_assets object with assets=[], a footing "
                "zero summary, gate_status='blocked', and explain in production_notes / "
                "OUTPUT 3. Do NOT invent content items.\n"
            )

        parts.append(
            "\n---\nProduce the copy_assets per the system prompt: for each briefed content "
            "item write the hook, primary_caption (ES-MX), cta, A/B variants and hashtags, "
            "author the fal.ai image-gen prompt(s) (flux-2-pro / ideogram-3.0), risk-tier each "
            "asset, respect client_profile.constraints + brand_voice_tokens, foot the summary, "
            "and produce the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent41(
    agent_id="4.1",
    prompt_asset="agents/layer4/prompts/copy_prompt_engine_system.txt",
    model=settings.model_primary,
    max_tokens=32000,   # raised from 16000 — large copy batches truncated the JSON mid-block on real client data
    schema_name="copy_assets",
    memory_block="copy_assets",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks content_calendar (or content_plan) / audience_segments /
    competitive_map / client_profile (injected by the orchestrator under their
    block names); optional cycle_month."""
    return AGENT.run(payload)
