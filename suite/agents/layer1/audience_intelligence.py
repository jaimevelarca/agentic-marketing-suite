"""Agent 1.2 — Audience Intelligence (Layer 1).

Built on `suite/agents/base.py`. The production system prompt lives as a
versioned asset at `suite/agents/layer1/prompts/audience_intelligence_system.txt`
(kept in sync with DEL-11 §2 — DEL-11 is the human-readable deliverable, the
.txt is the machine source of truth loaded at runtime).

Reads the approved `client_profile` (from Agent 1.1) plus any available customer
data and writes the `audience_segments` memory block: 3–5 ranked segments, each
with confidence metadata, for Layers 2/3/4/6.

Trigger (DEL-11): runs ONLY after `client_profile.gate_status == "approved"`;
the orchestrator enforces this precondition before invoking. Human gate: review
(rank/add/flag segments before Layer 2 consumes them).

Two-stage execution (ADR-04):
  - dev/test: this module, direct AnthropicVertex via BaseAgent.call (or the
    offline 'fixture' provider against suite/fixtures/1.2.txt)
  - prod: wrap `AGENT.run` in a google-adk LlmAgent on Vertex Agent Engine

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (1.2) and the
agent spec. Model = Sonnet (primary generation); system prompt cached.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra import clients
from infra.config import settings

_MAX_INJECT = 6000  # truncate any single injected JSON blob in the user turn


class Agent12(BaseAgent):
    """Audience Intelligence — produces ranked audience_segments + segment
    narratives + a human-gate summary from the approved client_profile and any
    available CRM / GA4 / social / survey / persona data."""

    def _inject(self, label: str, value) -> str:
        blob = json.dumps(value, indent=2, ensure_ascii=False)
        if len(blob) > _MAX_INJECT:
            blob = blob[:_MAX_INJECT] + "\n… [truncated]"
        return f"### SOURCE: {label}\n{blob}\n"

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## CLIENT DATA — AGENT 1.2 PROCESSING REQUEST\n"]

        # Upstream memory block this agent READS (injected under its block name).
        profile = payload.get("client_profile")
        if profile:
            parts.append(self._inject("Approved client_profile (from Agent 1.1)", profile))
        else:
            parts.append("### SOURCE: Approved client_profile (from Agent 1.1)\nNot available.\n")

        # Raw onboarding inputs — each optional; tolerate missing.
        raw_sources = [
            ("crm_data", "CRM Export"),
            ("ga4_data", "Google Analytics (GA4) Data"),
            ("social_analysis", "Social Media Analytics (DEL-06 Output)"),
            ("survey_data", "Customer Survey / NPS Data"),
            ("persona_docs", "Existing Persona Documents"),
        ]
        for key, label in raw_sources:
            val = payload.get(key)
            if val:
                parts.append(self._inject(label, val))
            else:
                parts.append(f"### SOURCE: {label}\nNot available.\n")

        if payload.get("operator_notes"):
            parts.append(f"### SOURCE: Operator Notes\n{payload['operator_notes']}\n")

        parts.append("\n---\nProcess all available data and produce the three required outputs.")
        return "\n".join(parts)

    def route(self, client_id, obj, outputs, valid, err) -> None:
        # Default routing: valid → audience_segments memory block (Cloud SQL /
        # in-memory offline); narrative + any error → Firestore review queue.
        super().route(client_id, obj, outputs, valid, err)
        # Agent-1.2-specific: on a clean, reviewer-ready result, announce the
        # block on the layer-handoff topic so the orchestrator can advance L1→L2
        # once the human gate clears. (Consumers gate on approval themselves.)
        gate = (obj or {}).get("gate_status", "pending_review")
        if valid and client_id and gate != "blocked":
            n_segments = len((obj or {}).get("segments", []))
            clients.publish(settings.handoff_topic, {
                "client_id": client_id,
                "agent": self.agent_id,
                "block": self.memory_block,
                "gate_status": gate,
                "segment_count": n_segments,
            })


AGENT = Agent12(
    agent_id="1.2",
    prompt_asset="agents/layer1/prompts/audience_intelligence_system.txt",
    model=settings.model_primary,
    max_tokens=48000,   # audience_segments wraps every field of 3-5 segments in full provenance metadata — very large output
    schema_name="audience_segments",
    memory_block="audience_segments",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id, client_profile
    (the approved upstream block), and optional raw inputs crm_data, ga4_data,
    social_analysis, survey_data, persona_docs, operator_notes."""
    return AGENT.run(payload)
