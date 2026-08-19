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
    # llm_provider: "vertex" = Claude on Vertex (production); "anthropic" = Claude
    #   on Anthropic's first-party API (ANTHROPIC_API_KEY; live demo while Vertex
    #   quota is pending); "fixture" = canned per-agent responses from
    #   suite/fixtures/<agent_id>.txt (offline dev/demo).
    # backend: "gcp" = Cloud SQL/Firestore/Pub-Sub; "memory" = in-process store
    #   (offline dev/demo + tests). The two switches are independent.
    llm_provider: str = os.getenv("SUITE_LLM_PROVIDER", "vertex")
    backend: str = os.getenv("SUITE_BACKEND", "gcp")

    # --- Cloud SQL (reached via local cloud-sql-proxy on 127.0.0.1) ---
    sql_instance: str = os.getenv("SQL_INSTANCE", "ai-mkt-pg")
    db_name: str = os.getenv("SQL_DATABASE", "suite")
    db_user: str = os.getenv("SQL_USER", "suite_app")
    sql_password_secret: str = os.getenv("SQL_PASSWORD_SECRET", "db-app-password")
    # cloud-sql-proxy listen address. Override the port when 5432 is taken by a
    # local Postgres (e.g. SQL_PROXY_PORT=5433 in local dev).
    db_host: str = os.getenv("SQL_PROXY_HOST", "127.0.0.1")
    db_port: str = os.getenv("SQL_PROXY_PORT", "5432")

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
    def sql_instance_connection_name(self) -> str:
        return f"{self.project_id}:{self.region}:{self.sql_instance}"

    @property
    def fixtures_dir(self) -> Path:
        """Per-agent canned responses for the offline ('fixture') LLM provider."""
        return Path(__file__).resolve().parents[1] / "fixtures"


settings = Settings()
CONFIG = settings  # backward-compatible alias
