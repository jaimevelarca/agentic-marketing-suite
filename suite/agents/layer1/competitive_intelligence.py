"""Agent 1.3 — Competitive Intelligence (Layer 1).

Built on `suite/agents/base.py`. Maps a client's competitive landscape into the
`competitive_map` memory block (3-5 competitors, positioning landscape, content
gaps, relative SWOT, LATAM benchmarks). Read downstream by Layer 2 (Strategy),
Layer 3 (Content Planning), and Layer 4 (Production).

The production system prompt lives as a versioned asset at
`suite/agents/layer1/prompts/competitive_intelligence_system.txt` (kept in sync
with DEL-19, the human-readable deliverable; the .txt is the machine source of
truth loaded at runtime).

Two-stage execution (ADR-04):
  - dev/test: this module, direct AnthropicVertex via BaseAgent.call
  - prod: wrap `AGENT.run` in a google-adk LlmAgent on Vertex Agent Engine

Human gate: REVIEW-ONLY (ARCHITECTURE.md) — the agent never blocks; it routes
the map to the review queue so a human can confirm the competitor set. Cost &
Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (1.3) + the agent spec.
Model = Sonnet (primary generation/reasoning); system prompt cached.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings


class Agent13(BaseAgent):
    """Competitive Intelligence — produces competitive_map + competitive brief +
    human-gate summary from the client_profile (upstream) plus the client's
    competitor list, positioning notes, industry benchmarks, and scraper output."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## CLIENT DATA — AGENT 1.3 COMPETITIVE INTELLIGENCE REQUEST\n"]
        parts.append(f"### CLIENT ID\n{payload.get('client_id', 'UNKNOWN')}\n")

        # UPSTREAM memory block (anchor): injected by the orchestrator under its
        # block-name key. Truncate large JSON to keep the input tier sane.
        client_profile = payload.get("client_profile")
        if client_profile:
            blob = json.dumps(client_profile, indent=2, ensure_ascii=False)[:24000]
            parts.append(f"### UPSTREAM: client_profile (Agent 1.1) — ANCHOR\n{blob}\n")
        else:
            parts.append(
                "### UPSTREAM: client_profile (Agent 1.1) — ANCHOR\n"
                "MISSING — no client_profile injected. Fall back to the raw inputs "
                "below for industry/market signal and lower your confidence.\n"
            )

        # Raw onboarding / enrichment inputs (all optional).
        if payload.get("competitor_list"):
            blob = json.dumps(payload["competitor_list"], indent=2, ensure_ascii=False)[:24000]
            parts.append(f"### SOURCE: Client-named competitors (onboarding)\n{blob}\n")
        if payload.get("positioning_notes"):
            notes = payload["positioning_notes"]
            if not isinstance(notes, str):
                notes = json.dumps(notes, indent=2, ensure_ascii=False)
            parts.append(f"### SOURCE: Client positioning notes\n{notes[:24000]}\n")
        if payload.get("industry_benchmarks"):
            blob = json.dumps(payload["industry_benchmarks"], indent=2, ensure_ascii=False)[:24000]
            parts.append(f"### SOURCE: Industry benchmarks (DEL-07 / client)\n{blob}\n")
        if payload.get("scraper_output"):
            blob = json.dumps(payload["scraper_output"], indent=2, ensure_ascii=False)[:24000]
            parts.append(f"### SOURCE: Web/social/ad-library scrape (DEL-05)\n{blob}\n")

        parts.append(
            "\n---\nProcess all available data and produce the three required "
            "outputs. Anchor every competitor to the client's industry and target "
            "markets. Default gate_status to 'pending_review' (review-only gate)."
        )
        return "\n".join(parts)


AGENT = Agent13(
    agent_id="1.3",
    prompt_asset="agents/layer1/prompts/competitive_intelligence_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="competitive_map",
    memory_block="competitive_map",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id?, client_profile?
    (upstream), competitor_list?, positioning_notes?, industry_benchmarks?,
    scraper_output?."""
    return AGENT.run(payload)
