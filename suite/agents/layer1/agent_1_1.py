"""Agent 1.1 — Business Diagnostics (Layer 1).

Built on `suite/agents/base.py`. The production system prompt lives as a
versioned asset at `suite/agents/layer1/prompts/agent_1_1_system.txt` (kept in
sync with DEL-10 §2 — DEL-10 is the human-readable deliverable, the .txt is the
machine source of truth loaded at runtime).

Two-stage execution (DEL-10 §3 / ADR-04):
  - dev/test: this module, direct AnthropicVertex via BaseAgent.call
  - prod: wrap `AGENT.run` in a google-adk LlmAgent on Vertex Agent Engine

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (1.1) and the
agent spec. Model = Sonnet (primary generation); system prompt cached.
"""
from __future__ import annotations

import json
import os

from agents.base import BaseAgent
from infra import clients
from infra.config import settings


class Agent11(BaseAgent):
    """Business Diagnostics — produces client_profile + interview questions +
    human-gate summary from onboarding + scraper + enrichment data."""

    def build_user_turn(self, payload: dict) -> str:
        parts = [
            "## CLIENT DATA — AGENT 1.1 PROCESSING REQUEST\n",
            f"### SOURCE: Quick Start Form\n{json.dumps(payload.get('quick_start_form', {}), indent=2)}\n",
            f"### SOURCE: Website Scraper Output (DEL-05)\n{json.dumps(payload.get('scraper_output', {}), indent=2)}\n",
        ]
        if payload.get("enrichment_data"):
            parts.append(f"### SOURCE: Enrichment Dashboard (DEL-02)\n{json.dumps(payload['enrichment_data'], indent=2)}\n")
        if payload.get("social_profile_data"):
            parts.append(f"### SOURCE: Social Profile Analyzer (DEL-06)\n{json.dumps(payload['social_profile_data'], indent=2)}\n")
        if payload.get("operator_notes"):
            parts.append(f"### SOURCE: Manual Notes\n{payload['operator_notes']}\n")
        parts.append("\n---\nProcess all available data and produce the three required outputs.")
        return "\n".join(parts)

    def route(self, client_id, obj, outputs, valid, err) -> None:
        # Default routing (Cloud SQL upsert + Firestore review doc) ...
        super().route(client_id, obj, outputs, valid, err)
        # ... plus Agent-1.1-specific: route interview questions to client comms.
        interview = outputs.get("output_2", "")
        if valid and client_id and interview and "None required" not in interview:
            clients.publish(settings.interview_topic,
                            {"client_id": client_id, "questions": interview})


AGENT = Agent11(
    agent_id="1.1",
    prompt_asset="agents/layer1/prompts/agent_1_1_system.txt",
    model=settings.model_primary,
    # The full DEL-17 client_profile (per-field provenance metadata) + OUTPUT 2/3
    # exceeds 8k tokens on real data — raised to avoid truncating the JSON block.
    # max_tokens is a ceiling, not billed spend. Override via env if needed.
    max_tokens=int(os.getenv("AGENT_1_1_MAX_TOKENS", "16000")),
    schema_name="DEL-17",
    memory_block="client_profile",
    inject_client_id=True,   # DEL-17 requires top-level client_id; stamp the orchestrator's id
    append_schema_skeleton=False,  # prompt already embeds a tuned skeleton + semantic rules
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: quick_start_form, scraper_output,
    enrichment_data?, social_profile_data?, operator_notes?, client_id?."""
    return AGENT.run(payload)
