"""Agent 1.4 — Trend Radar (Layer 1).

Built on `suite/agents/base.py`. The production system prompt lives as a
versioned asset at `suite/agents/layer1/prompts/trend_radar_system.txt`
(kept in sync with DEL-20 — DEL-20 is the human-readable deliverable, the .txt
is the machine source of truth loaded at runtime).

Contract (per ARCHITECTURE.md):
  - Reads: client_profile (injected by the orchestrator under its block key)
           + raw onboarding inputs rss_feeds / hashtags / seasonal_themes.
  - Writes: trend_signals memory block (time-indexed JSON; read by Layer 2 & 3).
  - Human gate: NONE — fully autonomous. Normal runs commit gate_status
    "auto_approved"; the prompt escalates to "pending_review" only on a genuine
    anomaly (no anchorable profile, constraint collision, or empty inputs).

The default BaseAgent.route() is correct here: a valid object with
gate_status="auto_approved" is written straight to the trend_signals block and
logged to the review queue at normal priority (an autonomous-run audit trail);
an invalid run or an escalation is surfaced for a human. No override needed.

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (1.4) and the
agent spec. Model = Haiku (routing/classification tier — high-volume, cached,
autonomous); system prompt cached.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings


def _fmt(value) -> str:
    """Compact JSON for injected inputs; truncate very large blobs."""
    text = json.dumps(value, indent=2, ensure_ascii=False)
    return text[:24000]


class Agent14(BaseAgent):
    """Trend Radar — produces a time-indexed trend_signals block from the
    approved client_profile plus the client's RSS feeds, tracked hashtags, and
    seasonal themes. Fully autonomous."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## CLIENT DATA — AGENT 1.4 (TREND RADAR) PROCESSING REQUEST\n"]

        as_of = payload.get("as_of_date")
        parts.append(f"### RUN DATE (as_of_date)\n{as_of or 'not provided — use the current date'}\n")

        profile = payload.get("client_profile")
        if profile:
            parts.append(
                "### SOURCE: Approved client_profile (from Agent 1.1)\n"
                f"{_fmt(profile)}\n"
            )
        else:
            parts.append(
                "### SOURCE: client_profile\n"
                "Not available or not approved. Anchor only on any inferable "
                "industry/target_markets and flag the gap in Output 3.\n"
            )

        parts.append(
            "### SOURCE: RSS Feeds / Newsletters (client reading list)\n"
            f"{_fmt(payload.get('rss_feeds', []))}\n"
        )
        parts.append(
            "### SOURCE: Tracked Hashtags / Topics\n"
            f"{_fmt(payload.get('hashtags', []))}\n"
        )
        parts.append(
            "### SOURCE: Seasonal Content Themes (business calendar)\n"
            f"{_fmt(payload.get('seasonal_themes', []))}\n"
        )

        if payload.get("operator_notes"):
            parts.append(f"### SOURCE: Operator Notes\n{payload['operator_notes']}\n")

        parts.append(
            "\n---\nAssess the available sources and produce the three required "
            "outputs. Set gate_status to 'auto_approved' for a normal run; "
            "escalate to 'pending_review' only on a genuine anomaly per the "
            "critical rules."
        )
        return "\n".join(parts)


AGENT = Agent14(
    agent_id="1.4",
    prompt_asset="agents/layer1/prompts/trend_radar_system.txt",
    model=settings.model_routing,
    max_tokens=16000,
    schema_name="trend_signals",
    memory_block="trend_signals",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id?, client_profile?,
    rss_feeds?, hashtags?, seasonal_themes?, operator_notes?, as_of_date?."""
    return AGENT.run(payload)
