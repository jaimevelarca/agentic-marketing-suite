"""Central config — environment + GCP resource names + model routing. No secrets inline.

Exposes a single frozen `settings` object. The names here are the contract the
agent code (base.py, agent_1_1.py, clients.py) depends on; keep them stable.
`CONFIG` is retained as a backward-compatible alias.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # --- GCP project / region ---
    project_id: str = os.getenv("GCP_PROJECT_ID", "ai-mkt-suite")
    region: str = os.getenv("GCP_REGION", "us-central1")  # GCP resources (Cloud SQL etc.)
    # Vertex endpoint region for Claude. "global" = no 10% regional premium + max
    # availability (Anthropic-recommended). Set to e.g. "us-central1" for data
    # residency. Independent of `region` (which pins the GCP resources).
    vertex_region: str = os.getenv("VERTEX_REGION", "global")

    # --- Runtime mode (lets the suite run end-to-end offline, no GCP/EULA) ---
    # llm_provider: "fixture" = canned per-agent responses from
    #   suite/fixtures/<agent_id>.txt (offline dev/demo, DEFAULT); "anthropic" =
    #   Claude first-party API (ANTHROPIC_API_KEY); "vertex" = Claude on Vertex.
    #   A "gemini" provider (google-genai) arrives in roadmap Phase 3.
    # backend: "gcp" = Firestore/Pub-Sub; "memory" = in-process store
    #   (offline dev/demo + tests). The two switches are independent.
    # SAFE-OFFLINE DEFAULTS: a bare import must never reach real GCP/LLM APIs.
    # Production is an explicit opt-in (Dockerfile / run_live.sh export these).
    llm_provider: str = os.getenv("SUITE_LLM_PROVIDER", "fixture")
    backend: str = os.getenv("SUITE_BACKEND", "memory")

    # --- Pub/Sub topics ---
    interview_topic: str = os.getenv("TOPIC_INTERVIEW", "client-interview-questions")
    review_topic: str = os.getenv("TOPIC_REVIEW", "review-queue-events")
    handoff_topic: str = os.getenv("TOPIC_HANDOFF", "layer-handoff")

    # --- Firestore ---
    review_collection: str = os.getenv("FIRESTORE_REVIEW_COLLECTION", "review_queue")

    # --- Claude on Vertex (model routing — see AGENT_COST_MODEL.md) ---
    # Vertex API model IDs (verified 2026-06-08 against the Anthropic Vertex docs):
    # the current 4.6+ models take NO dated suffix; only Haiku 4.5 is dated.
    # Override via env if Google bumps a pinned date.
    model_primary: str = os.getenv("CLAUDE_MODEL_SONNET", "claude-sonnet-4-6")           # primary generation/reasoning
    model_routing: str = os.getenv("CLAUDE_MODEL_HAIKU", "claude-haiku-4-5@20251001")    # routing/classification
    model_deep: str = os.getenv("CLAUDE_MODEL_OPUS", "claude-opus-4-7")                  # binding deep reasoning ONLY

    @property
    def fixtures_dir(self) -> Path:
        """Per-agent canned responses for the offline ('fixture') LLM provider."""
        return Path(__file__).resolve().parents[1] / "fixtures"


settings = Settings()
CONFIG = settings  # backward-compatible alias
