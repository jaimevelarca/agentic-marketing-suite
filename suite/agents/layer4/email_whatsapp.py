"""Agent 4.4 — Email / WhatsApp (Layer 4 — Production).

Built on `suite/agents/base.py`. Turns the approved audience map and content
calendar into complete, ready-to-deploy lifecycle/nurture sequences — email
drips (Resend) and WhatsApp flows (Twilio WhatsApp Business API, ADR-04) — and
writes them to the `message_flows` memory block. Layer 5 (Agent 5.3 Lead
Capture + Nurture) executes the approved flows; Layer 6 (6.1) attributes their
opens/clicks/replies.

The production system prompt is the versioned asset
`suite/agents/layer4/prompts/email_whatsapp_system.txt` (the machine source of
truth; DEL-29 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  audience_segments (1.2, REQUIRED), content_calendar (L3, REQUIRED — may arrive
  as `content_calendar` or the editorial `content_plan` it derives from);
  optionally client_profile for constraints / brand voice / blackout dates.
Writes: message_flows. Human gate: first-deploy (default pending_review).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 4.4) and
`agents/4.4-email_whatsapp.md`. Model = Sonnet (primary generation); system
prompt cached; bursty (only runs for T3 clients, 8 runs/cycle).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads, injected under these exact keys.
# content_calendar is the canonical block name (ARCHITECTURE.md); Layer 3 may
# inject the editorial content_plan it was derived from under that key too, so
# we also accept "content_plan" as an alias.
_REQUIRED_BLOCKS = ("audience_segments",)
_CALENDAR_KEYS = ("content_calendar", "content_plan")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent44(BaseAgent):
    """Email / WhatsApp — produces the `message_flows` block (email drips +
    WhatsApp nurture flows) from the approved audience_segments + content
    calendar. First-deploy human gate."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## MESSAGE-FLOW PRODUCTION REQUEST — AGENT 4.4\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested): {payload['cycle_month']}\n")

        present = []
        # Required: audience_segments.
        for name in _REQUIRED_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        # Required: a content calendar/plan (accept either key).
        calendar_present = False
        for key in _CALENDAR_KEYS:
            val = payload.get(key)
            if val:
                parts.append(_block(key, val))
                calendar_present = True
                break

        # Optional context.
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))
        if payload.get("existing_flows"):
            parts.append(_block("existing_flows (already deployed/approved)",
                                payload["existing_flows"]))
        if payload.get("operator_notes"):
            parts.append(f"### OPERATOR NOTES\n{payload['operator_notes']}\n")

        missing = [b for b in _REQUIRED_BLOCKS if b not in present]
        if not calendar_present:
            missing.append("content_calendar")
        if missing:
            parts.append(
                "### MISSING REQUIRED INPUTS\n"
                f"{', '.join(missing)} not provided. Per the prompt rules, emit a "
                "minimal valid message_flows with flows=[], gate_status='blocked', "
                "and explain in planning_notes / OUTPUT 3.\n"
            )

        parts.append(
            "\n---\nBuild the message_flows per the system prompt: 2-4 lifecycle/"
            "nurture flows (email via Resend, WhatsApp via Twilio), ES-MX copy "
            "grounded in the segments and aligned to the calendar, with triggers, "
            "delays, exits, goals and an honest compliance pass. Keep the summary "
            "footing to the flows/messages, set the first-deploy gate, and produce "
            "the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent44(
    agent_id="4.4",
    prompt_asset="agents/layer4/prompts/email_whatsapp_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="message_flows",
    memory_block="message_flows",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks audience_segments (required) and content_calendar/content_plan
    (required), injected by the orchestrator under their block names; optional
    client_profile, cycle_month, existing_flows, operator_notes."""
    return AGENT.run(payload)
