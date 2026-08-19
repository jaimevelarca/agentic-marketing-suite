"""Agent 6.2 — Client Reporting (Layer 6 — Analytics & Feedback).

Built on `suite/agents/base.py`. Once per client per marketing cycle it turns the
month's measured performance into two artifacts: a client-facing monthly narrative
ROI report in es-MX (OUTPUT 2) and an internal, machine-readable
`client_health_score` memory block (OUTPUT 1) used by account management for
renewal / upsell / churn triage. It is the client's monthly "here is what your
money did" moment — honest, ROI-grounded, and free of any Acme Co. internal
economics (no COGS / margins / cost-to-serve / bonus figures ever).

The production system prompt is the versioned asset
`suite/agents/layer6/prompts/client_reporting_system.txt` (the machine source of
truth; DEL-34 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  performance_history (6.1, REQUIRED — the measured ground truth),
  active_strategy (2.1, REQUIRED — objective + embedded kpi_contracts to reconcile
  against), client_profile (1.1 — identity, lifecycle_stage, language, brand voice,
  constraints). Optionally prior_report / prior_health_score (trend), cycle_month,
  operator_notes.
Writes: client_health_score. Human gate: pre-client (default pending_review — the
operator must approve before the report is delivered to the client).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 6.2) and
`agents/6.2-client_reporting.md`. Model = Sonnet (primary generation); system
prompt cached; monthly singleton (one isolated call/cycle → cache write each run).
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads, injected under these exact keys.
_REQUIRED_BLOCKS = ("performance_history", "active_strategy")
_OPTIONAL_BLOCKS = ("client_profile",)

# Truncate any single injected JSON blob so a large memory block (e.g. an hourly
# performance time series) can't blow the user turn — and the input-token cost —
# out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent62(BaseAgent):
    """Client Reporting — produces the internal `client_health_score` block plus a
    client-facing es-MX monthly ROI report from the period's performance_history
    reconciled against the active_strategy/kpi_contracts. Pre-client gate."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## MONTHLY CLIENT REPORT REQUEST — AGENT 6.2\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("cycle_month"):
            parts.append(f"cycle_month (requested period): {payload['cycle_month']}\n")

        present = []
        for name in _REQUIRED_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)

        for name in _OPTIONAL_BLOCKS:
            if payload.get(name):
                parts.append(_block(name, payload[name]))

        # Prior period (either key) for trend / delta context.
        prior = payload.get("prior_health_score") or payload.get("prior_report")
        if prior:
            parts.append(_block("prior_health_score (last period — for trend)", prior))

        if payload.get("operator_notes"):
            parts.append(f"### OPERATOR NOTES\n{payload['operator_notes']}\n")

        missing = [b for b in _REQUIRED_BLOCKS if b not in present]
        if missing:
            parts.append(
                "### MISSING REQUIRED INPUTS\n"
                f"{', '.join(missing)} not provided. Per the prompt rules, do NOT "
                "fabricate metrics: produce a minimal valid client_health_score with "
                "honest low-confidence scores, recommendation.action='hold', "
                "gate_status='pending_review', and explain the gap in OUTPUT 3.\n"
            )

        parts.append(
            "\n---\nProduce the three required outputs per the system prompt: the "
            "internal client_health_score JSON (OUTPUT 1), the client-facing es-MX "
            "monthly ROI report (OUTPUT 2), and the pre-client gate summary "
            "(OUTPUT 3). Reconcile every KPI in active_strategy.kpi_contracts against "
            "performance_history actuals, never invent numbers, keep all Acme Co. "
            "internal economics out of both client-facing outputs, and set the "
            "pre-client gate (gate_status='pending_review')."
        )
        return "\n".join(parts)


AGENT = Agent62(
    agent_id="6.2",
    prompt_asset="agents/layer6/prompts/client_reporting_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="client_health_score",
    memory_block="client_health_score",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory blocks
    performance_history (required) and active_strategy (required), injected by the
    orchestrator under their block names; optional client_profile, cycle_month,
    prior_health_score / prior_report, operator_notes."""
    return AGENT.run(payload)
