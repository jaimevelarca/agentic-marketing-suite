"""Agent 5.3 — Lead Capture + Nurture (Layer 5 — Distribution).

Built on `suite/agents/base.py`. Scores a batch of inbound leads, routes each
(hot → human follow-up; warm/cold → automated nurture), syncs them to the CRM
(HubSpot, ADR-04), and writes the `lead_register` memory block. Warm/cold leads
are enrolled into the approved nurture flows that Agent 4.4 wrote to
`message_flows` — referenced by `flow_id`; this agent never authors flow copy.

Human gate: **conditional**. The routine batch action is autonomous, so the
block defaults to `gate_status: "auto_approved"`; hot leads are *flagged* for a
human (in `hot_leads_for_human` + OUTPUT 3) without blocking the warm/cold
automation. `pending_review` only on CRM-sync failure / unreliable scoring /
missing `message_flows`; `blocked` only on empty input.

Reads (memory blocks injected by the orchestrator under their block-name keys):
  audience_segments (1.2) — for segment-fit scoring + enrolled-flow targeting;
  message_flows (4.4) — the approved flows warm/cold leads are enrolled into.
  Raw batch arrives under `inbound_leads`. Optional: client_profile,
  scoring_rules, crm_context, operator_notes.
Writes: lead_register (live, CRM-synced). Read downstream by Layer 6 (6.1).

The production system prompt is the versioned asset
`suite/agents/layer5/prompts/lead_capture_nurture_system.txt` (the machine
source of truth; DEL-32 is its human-readable wrapper).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 5.3) and
`agents/5.3-lead_capture_nurture.md`. Model = Haiku (`settings.model_routing`) —
lead scoring + dispatch is classification, not generation; system prompt cached;
bursty + cheap ($0.006/run).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads, injected under these exact keys.
_CONTEXT_BLOCKS = ("audience_segments", "message_flows")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent53(BaseAgent):
    """Lead Capture + Nurture — produces the `lead_register` block (scored,
    routed, CRM-synced leads + hot-lead flags) from an inbound-lead batch, the
    audience segments, and the approved message flows. Conditional gate."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## LEAD CAPTURE + NURTURE REQUEST — AGENT 5.3\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("batch_window"):
            parts.append(f"batch_window: {payload['batch_window']}\n")

        # Required: the inbound-lead batch.
        leads = payload.get("inbound_leads")
        if leads:
            parts.append(_block("inbound_leads (RAW BATCH)", leads))

        # Context memory blocks (used for scoring + enrollment targeting).
        present_context = []
        for name in _CONTEXT_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present_context.append(name)

        # Optional context.
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))
        if payload.get("scoring_rules"):
            parts.append(_block("scoring_rules (operator overrides)", payload["scoring_rules"]))
        if payload.get("crm_context"):
            parts.append(_block("crm_context (existing HubSpot ids/owners)", payload["crm_context"]))
        if payload.get("operator_notes"):
            parts.append(f"### OPERATOR NOTES\n{payload['operator_notes']}\n")

        # Degraded-mode instructions: the prompt defines exactly how to respond.
        if not leads:
            parts.append(
                "### NO INBOUND LEADS\n"
                "inbound_leads is missing/empty. Per the prompt rules, emit a minimal "
                "valid lead_register with leads=[], gate_status='blocked', and explain "
                "in routing_notes / OUTPUT 3.\n"
            )
        elif "message_flows" not in present_context:
            parts.append(
                "### MESSAGE_FLOWS NOT PROVIDED\n"
                "No approved message_flows were injected. Score and route normally, but "
                "warm/cold leads cannot be auto-enrolled: route them to human_followup, "
                "set gate_status='pending_review', and explain in routing_notes / OUTPUT 3.\n"
            )

        parts.append(
            "\n---\nProcess the batch per the system prompt: normalize + dedupe, score "
            "each lead 0-100 with a score_breakdown, set temperature + routing (hot → "
            "human_followup + flag in hot_leads_for_human; warm/cold → nurture enrolled "
            "into an approved message_flows flow_id), choose the HubSpot crm_action/"
            "crm_status, foot the summary to the leads, set the conditional gate "
            "(auto_approved by default), and produce the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent53(
    agent_id="5.3",
    prompt_asset="agents/layer5/prompts/lead_capture_nurture_system.txt",
    model=settings.model_routing,
    max_tokens=16000,
    schema_name="lead_register",
    memory_block="lead_register",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; inbound_leads
    (required, the raw batch); the upstream memory blocks audience_segments (1.2)
    and message_flows (4.4) injected by the orchestrator under their block names;
    optional client_profile, scoring_rules, crm_context, batch_window,
    operator_notes."""
    return AGENT.run(payload)
