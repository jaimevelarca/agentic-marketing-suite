"""Agent 5.2 — Social Publisher (Layer 5 — Distribution).

Built on `suite/agents/base.py`. The autonomous organic-social publishing
executor: it takes a cycle's scheduled `content_calendar` slots, attaches the
finished `copy_assets` and `visual_assets`, formats each post to its target
platform's requirements, dispatches it through Ayrshare (Buffer fallback,
ADR-04), and writes the `publish_log` ledger that Layer 6 (6.1 Performance
Analytics) reads for slot-level attribution. It does NOT author copy, design
visuals, or touch paid ad spend (that is Agent 5.1 — Campaign Launcher); it only
publishes already-approved, already-produced, unflagged ORGANIC content.

The production system prompt is the versioned asset
`suite/agents/layer5/prompts/social_publisher_system.txt` (the machine source of
truth; DEL-31 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  content_calendar (3.2, primary — the dated/timed slots), copy_assets (4.1,
  the finished captions), visual_assets (4.2, the finished media). Optional `now`
  run-timestamp drives publish_now vs schedule.
Writes: publish_log. Human gate: autonomous — this agent's own gate_status is
always 'auto_approved'; per-item posture lives in entries[].status.

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 5.2) and
`agents/5.2-social_publisher.md`. Model = Haiku (routing/formatting/dispatch
tier — deterministic platform formatting, no generation); system prompt cached;
bursty (fires per cycle over many small slots) so cache hit is high (~$0.003/run).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
# content_calendar (3.2) is the canonical scheduled list of slots; copy_assets
# (4.1) and visual_assets (4.2) supply the finished body and media to attach.
_UPSTREAM_BLOCKS = ("content_calendar", "copy_assets", "visual_assets")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the Haiku input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent52(BaseAgent):
    """Social Publisher — formats and publishes a cycle's organic-social slots
    through Ayrshare and emits the `publish_log` dispatch ledger. Autonomous:
    own gate_status is always 'auto_approved'; risk-flagged/unready items are
    held for a human, never published."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## SOCIAL PUBLISHING REQUEST — AGENT 5.2\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")
        if payload.get("now"):
            # Optional explicit run timestamp for the publish_now-vs-schedule
            # decision; otherwise the model uses the created_at it stamps.
            parts.append(f"run_timestamp (now): {payload['now']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        if "content_calendar" not in present:
            parts.append(
                "### NO ROUTABLE INPUT\n"
                "content_calendar was not provided (no slots to publish). Per the prompt "
                "rules, emit a minimal valid publish_log with an empty entries array, "
                "gate_status='auto_approved', source_block='none', explain in notes, and "
                "recommend MONITOR in OUTPUT 3.\n"
            )
        else:
            parts.append("### SOURCE BLOCK FOR PUBLISHING: content_calendar\n")

        parts.append(
            "\n---\nPublish every eligible organic-social slot through Ayrshare per the "
            "system prompt: classify scope, match copy (content_ref <-> copy_assets."
            "content_item_ref) and media (content_ref <-> visual_assets.content_item_id), "
            "run the eligibility checks in order, apply mechanical platform formatting, "
            "decide publish_now vs schedule from the resolved time, keep your own "
            "gate_status='auto_approved', foot the summary to the entries, and produce the "
            "three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent52(
    agent_id="5.2",
    prompt_asset="agents/layer5/prompts/social_publisher_system.txt",
    model=settings.model_routing,   # Haiku — routing / formatting / dispatch tier
    max_tokens=16000,
    schema_name="publish_log",
    memory_block="publish_log",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks content_calendar (3.2), copy_assets (4.1), visual_assets (4.2)
    injected by the orchestrator under their block names; optional cycle_month
    and `now` (run timestamp for the publish_now-vs-schedule decision)."""
    return AGENT.run(payload)
