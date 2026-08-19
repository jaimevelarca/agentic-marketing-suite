# Agentic Marketing Suite — Ground-Up Roadmap

> From the imported `ai-marketing-suite` baseline (see
> [docs/REVIEW-2026-08-19.md](docs/REVIEW-2026-08-19.md)) to a production app on GCP
> project **`agentic-marketing-suite`** (QHHE folder 274831265727, billing
> `01624A-839C44-1DB4D6`): Pulumi IaC, ADK 2.x + Gemini on the Gemini Enterprise
> Agent Platform, Cloud Run, Firestore, Django review UI.
>
> Each phase gets its own detailed implementation plan in
> `docs/superpowers/plans/` when it starts. This file is the strategic map.

## Architecture decisions (2026-08-19, stack verified against current docs)

| Decision | Choice | Rationale |
|---|---|---|
| Orchestration | **ADK 2.x graph `Workflow`** (pin exact version) | 2.0 (May 2026, stable) made the graph DAG the native primitive: explicit edges, conditional routing, native retries, HITL pause via `NodeInterruptedError` — exactly our 19-node DAG + human gates. |
| Genkit | **Skip for core** (experimental lane only) | Genkit Python is still Alpha (0.9.0); redundant with ADK for a DAG-of-agents. JS maturity doesn't transfer. |
| Antigravity SDK | **Experimental lane only** | `google-antigravity` exists (I/O 2026) but is Research Preview, no SLA. Use it for dev-tooling experiments (agent-assisted ops, browser QA), never on the client-serving path. |
| Model access | **Vertex surface via `google-genai`** (`vertexai=True`, ADC/service accounts) | Production controls (IAM, quotas, VPC-SC, audit, SLA). AI Studio keys only for local prototyping. `google-generativeai` is dead (EOL Nov 2025). |
| Models | primary **`gemini-3.7-flash`** (GA) · routing **`gemini-3.5-flash-lite`** · deep **`gemini-3.1-pro-preview`** (only tier where Preview is tolerated; agent 2.1 only) · images **`gemini-3.1-flash-image`** (Nano Banana 2) | Flash line is the 2026 flagship; **never 2.5** (retires as early as Oct 2026). Keep the three-tier routing concept from the baseline. Batch API (−50%) for non-interactive stages. |
| Persistence | **Firestore Standard** for all pipeline data (clients, runs, memory blocks, review queue, audit) — Pydantic models via `firedantic` or thin `google-cloud-firestore` wrappers | Kills the Cloud SQL split-brain, the password-wiring bug class, migrations, and the proxy. Document-shaped data (JSON memory blocks) is Firestore-native. |
| Django's own DB | **Small Cloud SQL Postgres for `django.contrib` only** (auth, admin, sessions) | There is no Google-maintained Firestore ORM backend; Django-on-Firestore breaks admin/auth. Domain data stays in Firestore; Django reads/writes it through the suite's Firestore layer. |
| Hosting | **Cloud Run** — Jobs for pipeline execution, Service for Django, Service for MCP/A2A | Batch-style DAG fits Jobs; container control, commodity pricing. |
| Gemini Enterprise | **Agent Runtime deploy + registration as a later phase** | A2A registration of Cloud-Run agents went GA Aug 17, 2026; Pay-as-you-go edition (GA Aug 2026) avoids seat commitments. Not needed to run the product. |
| IaC | **Pulumi (Python), state on a GCS bucket** (`pulumi login gs://…`), stacks `dev`/`prod` in the one project | Whole stack covered by `pulumi-gcp` v9 incl. Agent Runtime (`gcp.vertex.AiReasoningEngine`); OSS backend keeps it free. |
| Contract to preserve | prompt asset + JSON Schema + fixture per agent; **207 offline tests keep passing at every phase** | The offline contract is the product's crown jewel; every migration step is gated on it. |

## Phases

### Phase 0 — Repo hygiene & truth (unblocks everything)
Strip real client data (`suite/inputs/alonso-y-cia.json` → vault), delete stale
Drive-path build scripts (`workflows/*.js`), rewrite CLAUDE.md/AGENTS.md/README for
the new repo + project, pin Python 3.12, drop unused deps, flip config defaults to
safe (`fixture`/`memory`; prod is explicit opt-in), add `logging` scaffold.
**Exit:** clean generic repo, 207 tests green, docs true.

### Phase 1 — Pulumi foundation (IaC before app)
`infra/` Pulumi program: state bucket (bootstrapped once by hand), API enablement,
Artifact Registry, **Firestore database**, Secret Manager, service accounts + minimal
IAM, Pub/Sub topics, budget alerts, Cloud Build/GitHub Actions trigger wiring.
`pulumi up` on stack `dev`.
**Exit:** entire project state reproducible from `infra/`; nothing created by hand
except the state bucket and the project itself (import both).

### Phase 2 — Firestore data layer
Replace the `gcp` backend in `suite/infra/clients.py`: memory blocks, client
profiles, review queue, run ledger as Firestore collections
(`clients/{id}`, `runs/{id}`, `runs/{id}/blocks/{block}`, `review_queue/{id}`).
Typed Pydantic models; delete psycopg/migrations; keep `memory` backend for tests.
Gate status becomes a real state machine on the block doc (`pending_review →
approved/returned/blocked`), with audit subcollection.
**Exit:** live smoke run persists a full 19-agent run to Firestore in `dev`.

### Phase 3 — Gemini provider
New `gemini` provider in `clients.py` via `google-genai` (Vertex backend): structured
output with `response_format` + schema (from the existing JSON Schemas), retries with
backoff on transport errors, per-call token/cost logging, three-tier model routing
from config. Golden-run comparison: fixture outputs vs Gemini outputs
schema-validated across all 19 agents.
**Exit:** `SUITE_LLM_PROVIDER=gemini` full run green in `dev`; cost per run measured.

### Phase 4 — ADK 2.x orchestration on Cloud Run
Port `pipeline.py`'s DAG to an ADK graph `Workflow` (one node per agent; router
functions where gates branch; `NodeInterruptedError` pauses at human gates; resume on
approval). Session/state backed by Firestore (custom `BaseSessionService` — the
official Firestore session service is Java-only) or `DatabaseSessionService` on the
Django Cloud SQL instance if the custom service isn't worth it. Deploy as Cloud Run
Job (`adk deploy cloud_run` or own Dockerfile). Retire `deploy/workflows/*.yaml`.
**Exit:** a gated run pauses on Firestore gate docs and resumes on approval, no
sleep-loop, end to end in `dev`.

### Phase 5 — Django review & ops UI (the missing product surface)
Django 5.x on Cloud Run: review queue (approve/return/block with diff view of the
block JSON), run browser, client onboarding form (writes
`suite/inputs`-shaped doc to Firestore), cost dashboard. Cloud SQL Postgres
(smallest tier) for auth/admin/sessions; IAP in front; es-MX UI (client-facing rule:
español profesional, sin anglicismos). Approval writes flip the gate doc → resumes
the paused ADK workflow.
**Exit:** a human runs and approves an entire client pipeline from the browser.

### Phase 6 — CI/CD & prod stack
GitHub Actions: tests → build images → `pulumi up` preview/apply → deploy Jobs +
Services; `prod` stack promoted from `dev`; secrets in Secret Manager only; smoke-run
gate on deploy.
**Exit:** merge to `main` ships to `dev` automatically; tagged release ships `prod`.

### Phase 7 — Gemini Enterprise Agent Platform surface (optional, when wanted)
Deploy the root agent to **Agent Runtime** (via Pulumi `gcp.vertex.AiReasoningEngine`
or the `agent_engines` SDK) and/or register the Cloud Run agents into **Gemini
Enterprise** via A2A agent cards (Pay-as-you-go edition). Managed sessions/Memory
Bank evaluated here (note: new billing from Sept 1, 2026).
**Exit:** agents discoverable/chattable in Gemini Enterprise for QHHE users.

### Phase 8 — Real distribution integrations (post-MVP backlog)
Layer 4/5 stop being spec-only: pick per-channel order (likely Meta Ads + Resend
first), implement real clients behind the MCP `platform_apis` domain, human
financial-authorization gate before any spend. Embeddings/pgvector idea from the
baseline is dropped unless a concrete retrieval need appears (then: Vertex embeddings
+ Firestore vector search).

## Standing rules

- Human gate is sacred: nothing publishes or spends without explicit approval;
  `#1ebe82` reserved for human-gate UI.
- Secrets: local via `~/.agent_dispatcher/` vault; cloud via Secret Manager. Never in
  repo/env files.
- Client-facing output: español es-MX profesional, sin anglicismos.
- Every phase keeps the 207-test offline suite green and adds its own tests.
