"""Agent 6.1 — Performance Analytics (Layer 6 — Analytics & Feedback).

Built on `suite/agents/base.py`. The production system prompt lives as a
versioned asset at `suite/agents/layer6/prompts/performance_analytics_system.txt`
(kept in sync with DEL-33 — DEL-33 is the human-readable deliverable, the .txt
is the machine source of truth loaded at runtime).

Job (per ARCHITECTURE.md, L6 · 6.1): close the loop. For one reporting window,
join the live distribution actuals — `ad_campaign_log` (5.1, paid),
`publish_log` (5.2, organic), `lead_register` (5.3, lead→customer) — compute the
canonical funnel metrics (ROAS / CPL / CAC / CTR + reach/leads/conversion), and
reconcile each against the binding KPI contracts nested in `active_strategy`
(2.1, `kpi_contracts`). Writes the `performance_history` block read by Layer 1
(diagnostics re-baselining) and Layer 2 (next-cycle strategy).

Human gate: AUTO + ALERT. A normal reconciliation runs autonomously and commits
`gate_status="auto_approved"`; the agent never blocks the pipeline. Its
escalation lever is the `escalated` flag + the `alerts` array: on a KPI breach it
sets `escalated=true`, raises a critical alert, fans the alert out on Pub/Sub,
and bumps the review-queue priority to `urgent` so the single operator is paged —
WITHOUT changing the (always `auto_approved`) gate_status. That two-track design
is why this agent overrides `route()`.

Reads (upstream memory blocks the orchestrator injects under their block-name
keys): ad_campaign_log, publish_log, lead_register, active_strategy. Writes:
performance_history.

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 6.1) and the
agent spec `agents/6.1-performance_analytics.md`. Model = Sonnet (primary
generation/reasoning — multi-source numeric reconciliation against the binding
contract; not deep enough for Opus, too much for Haiku); system prompt cached.
~$0.074/run.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra import clients
from infra.config import settings

# Upstream memory blocks this agent reads, in the order they are presented in the
# user turn. active_strategy carries the nested kpi_contracts that everything is
# reconciled against, so it is presented last (the frame the actuals are judged by).
UPSTREAM_BLOCKS = ("ad_campaign_log", "publish_log", "lead_register", "active_strategy")

# Truncate any single injected JSON blob so a large/hourly log can't blow the
# user turn (and the Sonnet input-token cost) out of proportion (cost discipline;
# see AGENT_COST_MODEL.md).
_MAX_BLOCK_CHARS = 24000


def _block(title: str, obj) -> str:
    """Render one injected block as a labelled, size-capped JSON section."""
    try:
        body = json.dumps(obj, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        body = str(obj)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {title}\n{body}\n"


class Agent61(BaseAgent):
    """Performance Analytics — reconciles a window's actuals against the binding
    KPI contracts and writes the `performance_history` block. Auto + alert."""

    _LABELS = {
        "ad_campaign_log": "ad_campaign_log (Agent 5.1 — paid spend/results: spend_usd, impressions, clicks, reach, conversions, channel)",
        "publish_log": "publish_log (Agent 5.2 — organic publish results: posts, organic reach/impressions, engagement)",
        "lead_register": "lead_register (Agent 5.3 — leads, lead source/channel, status, customers closed, deal value_usd)",
        "active_strategy": "active_strategy (Agent 2.1 — BINDING; carries kpi_contracts: targets + threshold_floors + review_cadence + cycle + budget_allocation)",
    }

    def build_user_turn(self, payload: dict) -> str:
        parts = [
            "## PERFORMANCE RECONCILIATION REQUEST — AGENT 6.1\n",
            f"client_id: {payload.get('client_id', 'UNKNOWN')}",
        ]
        if payload.get("cycle_label"):
            parts.append(f"cycle_label: {payload['cycle_label']}")
        now = payload.get("now") or payload.get("as_of_date")
        parts.append(f"run_timestamp (now): {now or 'not provided — use the current date'}")
        if payload.get("window"):
            parts.append(
                "requested window: "
                + json.dumps(payload["window"], ensure_ascii=False)
            )
        parts.append("\n### UPSTREAM MEMORY BLOCKS\n")

        present = []
        for name in UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(self._LABELS[name], val))
                present.append(name)
            else:
                parts.append(
                    f"### MEMORY BLOCK: {name}\nNot provided for this window. "
                    "Treat dependent metrics as no_data, lower confidence, and flag "
                    "the gap — do not invent actuals.\n"
                )

        if not any(b in present for b in ("ad_campaign_log", "publish_log", "lead_register")):
            parts.append(
                "### NO MEASURABLE ACTUALS\n"
                "None of ad_campaign_log / publish_log / lead_register was provided. "
                "Emit a minimal valid performance_history: empty metrics, a missing_input "
                "alert, kpi_reconciliation entries set to 'no_data', escalated=false, "
                "gate_status='auto_approved', recommended_action='MONITOR', and explain "
                "in notes.\n"
            )
        if "active_strategy" not in present:
            parts.append(
                "### NO BINDING CONTRACT\n"
                "active_strategy / kpi_contracts is absent. Enter LEARNING MODE: report "
                "the measured metrics as kpi_reconciliation entries with status "
                "'no_contract', escalated=false, recommended_action='MONITOR'.\n"
            )

        if payload.get("operator_notes"):
            parts.append(f"### OPERATOR NOTES (steering)\n{payload['operator_notes']}\n")

        parts.append(
            "\n---\nEstablish the window, compute the funnel actuals (USD), reconcile "
            "each contracted KPI, raise alerts on breach/at-risk/data-gap, set "
            "escalated and recommended_action, and produce the three required outputs "
            "in order. gate_status is always 'auto_approved'."
        )
        return "\n".join(parts)

    def route(self, client_id, obj, outputs, valid, err) -> None:
        """Auto + alert routing.

        Default base routing already (a) writes the validated block to Cloud SQL
        and (b) logs to the Firestore review queue (urgent only when invalid). We
        keep that, then add the alert track: when this run escalated (a KPI
        breach), publish a Pub/Sub alert AND drop an urgent operator review doc —
        without ever changing gate_status (it stays 'auto_approved', so a clean
        window writes the block and logs at normal priority, no human needed)."""
        super().route(client_id, obj, outputs, valid, err)

        escalated = bool((obj or {}).get("escalated")) if valid else False
        if not (valid and client_id and escalated):
            return

        alerts = (obj or {}).get("alerts", []) or []
        # Surface the breach to the operator: Pub/Sub fan-out for the alerting
        # path, plus an explicit urgent review doc so it lands at the top of the
        # single reviewer's queue even though the agent's own gate is auto-approved.
        clients.publish(settings.review_topic, {
            "client_id": client_id,
            "agent": self.agent_id,
            "event": "kpi_breach",
            "headline": (obj or {}).get("summary", {}).get("headline", ""),
            "alerts": alerts,
        })
        clients.add_review_doc(self.review_collection, {
            "client_id": client_id,
            "agent": self.agent_id,
            "valid": True,
            "error": None,
            "gate_summary": outputs.get("output_3", ""),
            "raw_preview": (outputs.get("output_1", "") or "")[:2000],
            "priority": "urgent",
            "alert": "kpi_breach",
        })


AGENT = Agent61(
    agent_id="6.1",
    prompt_asset="agents/layer6/prompts/performance_analytics_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="performance_history",
    memory_block="performance_history",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks ad_campaign_log (5.1), publish_log (5.2), lead_register (5.3) and
    active_strategy (2.1, carrying kpi_contracts) injected by the orchestrator
    under their block names; optional window, now/as_of_date, cycle_label,
    operator_notes. Returns an AgentResult; routing (Cloud SQL memory block +
    Firestore review doc, plus a Pub/Sub alert on breach) happens inside
    AGENT.run via base.py + this agent's route() override."""
    return AGENT.run(payload)
