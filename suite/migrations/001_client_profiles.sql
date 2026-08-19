-- Cloud SQL schema: Layer 1 memory tables.
-- Apply after CREATE EXTENSION vector; (already done in S1-T11 smoke 10.b).

CREATE TABLE IF NOT EXISTS client_profiles (
    client_id    TEXT PRIMARY KEY,
    profile      JSONB NOT NULL,
    gate_status  TEXT NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS client_profiles_gate_status_idx
    ON client_profiles (gate_status);

-- Embeddings live beside profiles so Layer 3 / Layer 4 can do similarity joins
-- without cross-database traffic.
CREATE TABLE IF NOT EXISTS client_embeddings (
    id           BIGSERIAL PRIMARY KEY,
    client_id    TEXT NOT NULL REFERENCES client_profiles(client_id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,              -- 'brand_voice_sample' | 'audience' | 'competitor' | ...
    content      TEXT NOT NULL,
    embedding    vector(1536) NOT NULL,      -- ⚠️ dimension must match the chosen Vertex embedding model
                                             --    BEFORE any rows are written. Vertex text-embedding-005
                                             --    is 768-dim, not 1536 — ship a 002 migration to ALTER if
                                             --    that's the model. No embeddings written yet (2026-05-28),
                                             --    so this is a pre-write decision. See migrations/README.md.
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS client_embeddings_ann_idx
    ON client_embeddings USING hnsw (embedding vector_cosine_ops);
