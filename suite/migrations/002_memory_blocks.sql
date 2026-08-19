-- Cloud SQL schema: generic structured memory blocks for Layers 1-6.
-- Apply after 001_client_profiles.sql. Idempotent.
--
-- `client_profile` keeps its dedicated table (001) for backward compatibility and
-- gate-status indexing; every OTHER structured memory block written by the 18
-- product agents (audience_segments, competitive_map, trend_signals,
-- active_strategy, kpi_contracts, campaign_registry, content_plan,
-- content_calendar, approval_log, copy_assets, visual_assets, page_assets,
-- message_flows, ad_campaign_log, publish_log, lead_register,
-- performance_history, client_health_score, content_learnings) lands here.
-- One row per (client_id, block); JSONB payload validated against its schema in
-- project/resources/schemas/<block>.json before the write (suite/agents/base.py).

CREATE TABLE IF NOT EXISTS memory_blocks (
    client_id    TEXT NOT NULL,
    block        TEXT NOT NULL,              -- e.g. 'audience_segments', 'active_strategy'
    payload      JSONB NOT NULL,
    gate_status  TEXT NOT NULL DEFAULT 'pending_review',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ,
    PRIMARY KEY (client_id, block)
);

CREATE INDEX IF NOT EXISTS memory_blocks_gate_status_idx
    ON memory_blocks (gate_status);

-- Lets a layer query "all approved blocks for this client" cheaply.
CREATE INDEX IF NOT EXISTS memory_blocks_client_idx
    ON memory_blocks (client_id);

-- Vector blocks (audience_segments, competitive_map, copy_assets, visual_assets)
-- store their embeddings in client_embeddings (001). Embedding generation is a
-- Phase-3 concern; resolve the embedding dimension (see migrations/README.md
-- "Open: embedding dimension") before the first embedding write. No embeddings
-- are written by the offline MVP.
