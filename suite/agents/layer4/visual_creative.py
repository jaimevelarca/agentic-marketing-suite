"""Agent 4.2 — Visual Creative (Layer 4 — Production).

Built on `suite/agents/base.py`. Turns an approved, scheduled editorial calendar
plus finished copy into a batch of GENERATION SPECS (image/video prompts + asset
metadata, NOT rendered pixels) for the fal.ai engines Flux 2 Pro / Ideogram 3.0
/ Kling 2.5 / Runway Gen-4.5 (ADR-04). Writes the `visual_assets` memory block,
which Layer 5 (5.2 Social Publisher) reads to match each rendered file to its
scheduled slot.

The production system prompt is the versioned asset
`suite/agents/layer4/prompts/visual_creative_system.txt` (the machine source of
truth; DEL-27 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  content_calendar (Layer 3; a content_plan is accepted as a fallback),
  copy_assets (4.1), client_profile (1.1).
Writes: visual_assets. Human gate: batch review (default pending_review).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 4.2) and
`agents/4.2-visual_creative.md`. Model = Sonnet (primary generation); system
prompt cached; bursty/high-volume per cycle (one spec per visual-bearing item).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
# content_calendar is the dated Layer-3 block; a 'content_plan' is accepted as a
# fallback work queue when only the un-dated editorial plan is available.
_UPSTREAM_BLOCKS = ("content_calendar", "content_plan", "copy_assets", "client_profile")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent42(BaseAgent):
    """Visual Creative — produces a batch of fal.ai generation specs
    (image/video prompts + asset metadata) for each visual-bearing item in the
    content calendar, aligned to the finished copy and brand visual identity."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## VISUAL PRODUCTION REQUEST — AGENT 4.2\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        # The work queue is the dated calendar; fall back to a content_plan.
        has_queue = "content_calendar" in present or "content_plan" in present
        if not has_queue:
            parts.append(
                "### MISSING REQUIRED INPUT\n"
                "Neither content_calendar nor content_plan was provided. Per the prompt "
                "rules, emit a minimal valid visual_assets object with an empty assets "
                "array, gate_status='blocked', and explain in production_notes / OUTPUT 3.\n"
            )

        parts.append(
            "\n---\nProduce the visual_assets batch per the system prompt: one generation "
            "spec per visual-bearing calendar item (pick engine + aspect_ratio, write the "
            "English prompt + negative_prompt, attach exact ES-MX in-image text from the "
            "copy, honor brand colors and constraints), foot the summary to the assets, and "
            "emit the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent42(
    agent_id="4.2",
    prompt_asset="agents/layer4/prompts/visual_creative_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="visual_assets",
    memory_block="visual_assets",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks content_calendar (or content_plan), copy_assets, client_profile
    (injected by the orchestrator under their block names); optional cycle_month.
    """
    return AGENT.run(payload)
