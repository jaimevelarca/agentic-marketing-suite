# Cloud SQL migrations

Plain `.sql` files applied in numeric order to the Cloud SQL Postgres
(`ai-mkt-pg` / database `suite`). Idempotent (`CREATE ... IF NOT EXISTS`).

## How to apply

Run via the local Cloud SQL Auth Proxy (not `gcloud sql connect` — it eats stdin
heredocs as the password prompt; see `LEARNINGS.md`):

```bash
cloud-sql-proxy ai-mkt-suite:us-central1:ai-mkt-pg &   # background
PGPASSWORD="$(gcloud secrets versions access latest --secret=db-app-password)" \
  psql -h 127.0.0.1 -p 5432 -U suite_app -d suite -f suite/migrations/001_client_profiles.sql
```

## Log

| # | File | Status | Notes |
|---|---|---|---|
| 001 | `001_client_profiles.sql` | applied 2026-04-19 (S1-T11) | `client_profiles` + `client_embeddings` (HNSW ANN index). |
| 002 | `002_memory_blocks.sql` | **pending apply** (authored 2026-05-29, S4) | Generic `memory_blocks` table for the other 19 structured blocks the 18 product agents write. Apply before the first live multi-layer run. |

## ⚠️ Open: embedding dimension

`client_embeddings.embedding` is declared `vector(1536)`. **This must match the
chosen Vertex embedding model before any embeddings are written.** Vertex
`text-embedding-005` produces **768-dim** vectors. No embeddings exist yet
(2026-05-28), so confirm the model, then either (a) ship `002_*.sql` to
`ALTER TABLE client_embeddings ALTER COLUMN embedding TYPE vector(768)` and
recreate the HNSW index, or (b) keep 1536 if using a 1536-dim model. Decide
before the first embedding write.
