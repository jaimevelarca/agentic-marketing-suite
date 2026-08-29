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
| IaC | **Pulumi (Python), state on a GCS bucket** (`pulumi login gs://…`); stack `dev` → project `agentic-marketing-suite`, stack `prod` → **its own project** `agentic-marketing-suite-prod` (decided 2026-08-19, see Phase 6b) | Whole stack covered by `pulumi-gcp` v9 incl. Agent Runtime (`gcp.vertex.AiReasoningEngine`); OSS backend keeps it free. Two stacks in one project collide: Firestore `(default)` is per-project, and the service/instance/secret names are unprefixed. A second project keeps the program unchanged and separates the blast radius for ≈ USD 10–12/mo. |
| Contract to preserve | prompt asset + JSON Schema + fixture per agent; **207 offline tests keep passing at every phase** | The offline contract is the product's crown jewel; every migration step is gated on it. |

## Phases

### Phase 0 — Repo hygiene & truth (unblocks everything) ✅ 2026-08-19
Strip real client data (`suite/inputs/alonso-y-cia.json` → vault), delete stale
Drive-path build scripts (`workflows/*.js`), rewrite CLAUDE.md/AGENTS.md/README for
the new repo + project, pin Python 3.12, drop unused deps, flip config defaults to
safe (`fixture`/`memory`; prod is explicit opt-in), add `logging` scaffold.
**Exit:** clean generic repo, 207 tests green, docs true.

### Phase 1 — Pulumi foundation (IaC before app) ✅ 2026-08-19 (see infra/README.md)
`infra/` Pulumi program: state bucket (bootstrapped once by hand), API enablement,
Artifact Registry, **Firestore database**, Secret Manager, service accounts + minimal
IAM, Pub/Sub topics, budget alerts, Cloud Build/GitHub Actions trigger wiring.
`pulumi up` on stack `dev`.
**Exit:** entire project state reproducible from `infra/`; nothing created by hand
except the state bucket and the project itself (import both).

### Phase 2 — Firestore data layer ✅ 2026-08-19 (smoke run: 20 blocks + audit in (default) db)
Replace the `gcp` backend in `suite/infra/clients.py`: memory blocks, client
profiles, review queue, run ledger as Firestore collections
(`clients/{id}`, `runs/{id}`, `runs/{id}/blocks/{block}`, `review_queue/{id}`).
Typed Pydantic models; delete psycopg/migrations; keep `memory` backend for tests.
Gate status becomes a real state machine on the block doc (`pending_review →
approved/returned/blocked`), with audit subcollection.
**Exit:** live smoke run persists a full 19-agent run to Firestore in `dev`.

### Phase 3 — Gemini provider ✅ 2026-08-19 (golden run 19/19, ~$0.77/run)
New `gemini` provider in `clients.py` via `google-genai` (Vertex backend): structured
output with `response_format` + schema (from the existing JSON Schemas), retries with
backoff on transport errors, per-call token/cost logging, three-tier model routing
from config. Golden-run comparison: fixture outputs vs Gemini outputs
schema-validated across all 19 agents.
**Exit:** `SUITE_LLM_PROVIDER=gemini` full run green in `dev`; cost per run measured.

### Phase 4 — ADK 2.x orchestration ✅ 2026-08-19 (live pause/resume across processes; Cloud Run containerization → Phase 6)
Port `pipeline.py`'s DAG to an ADK graph `Workflow` (one node per agent; router
functions where gates branch; `NodeInterruptedError` pauses at human gates; resume on
approval). Session/state backed by Firestore (custom `BaseSessionService` — the
official Firestore session service is Java-only) or `DatabaseSessionService` on the
Django Cloud SQL instance if the custom service isn't worth it. Deploy as Cloud Run
Job (`adk deploy cloud_run` or own Dockerfile). Retire `deploy/workflows/*.yaml`.
**Exit:** a gated run pauses on Firestore gate docs and resumes on approval, no
sleep-loop, end to end in `dev`.

### Phase 5 — Django review & ops UI ✅ 2026-08-19 (browser flow proven vs dev Firestore; Cloud SQL+IAP land in Phase 6)
Django 5.x on Cloud Run: review queue (approve/return/block with diff view of the
block JSON), run browser, client onboarding form (writes
`suite/inputs`-shaped doc to Firestore), cost dashboard. Cloud SQL Postgres
(smallest tier) for auth/admin/sessions; IAP in front; es-MX UI (client-facing rule:
español profesional, sin anglicismos). Approval writes flip the gate doc → resumes
the paused ADK workflow.
**Exit:** a human runs and approves an entire client pipeline from the browser.

### Phase 6 — CI/CD & prod stack — 6a ✅ 2026-08-19, 6b ✅ 2026-08-21
GitHub Actions: tests → build images → `pulumi up` preview/apply → deploy Jobs +
Services; `prod` stack promoted from `dev`; secrets in Secret Manager only; smoke-run
gate on deploy.
**Exit:** merge to `main` ships to `dev` automatically; tagged release ships `prod`.

**6b completed (2026-08-21, see [docs/superpowers/plans/2026-08-21-phase-6b-cicd-prod.md](docs/superpowers/plans/2026-08-21-phase-6b-cicd-prod.md)):**
`prod` isolated in GCP project `agentic-marketing-suite-prod` (QHHE folder `274831265727`);
GitHub Actions with Workload Identity Federation (WIF) with zero secrets stored in GitHub;
promotion via git tag `v*` redeploying the identical immutable digest tested in `dev`;
Direct Cloud Run IAP enabled on `console` (`js@qhhe.net`) keeping Django login behind it;
`scripts/smoke_check.py` automated smoke gate with fixture job execution + 302 IAP redirect check
and automatic rollback on prod failure.

**Production Release v0.1.0 ✅ 2026-08-22 (see [docs/superpowers/plans/2026-08-22-prod-bootstrap-and-release-v0.1.0.md](docs/superpowers/plans/2026-08-22-prod-bootstrap-and-release-v0.1.0.md)):**
GCP project `agentic-marketing-suite-prod` (Project Number `198112926147`) bootstrapped and linked to billing `01624A-839C44-1DB4D6`;
Pulumi `prod` stack provisioned; GitHub Actions release pipeline verified live via git tag `v0.1.0` (Run 32621989376);
Direct IAP console active at `https://console-m6hls6q6ua-uc.a.run.app`; zero-cost fixture orchestrator job verified (19/19 agents).


### Phase 7 — Gemini Enterprise Agent Platform surface ✅ 2026-08-23 (see [docs/superpowers/plans/2026-08-23-phase-7-gemini-enterprise-reasoning-engine.md](docs/superpowers/plans/2026-08-23-phase-7-gemini-enterprise-reasoning-engine.md))
Vertex AI Reasoning Engine runtime (`suite/reasoning_engine/`) with Gemini 3.7 Flash (`gemini-3.7-flash`);
typed domain query tools over Firestore Native (`get_client_summary`, `get_audience_and_competition`,
`get_marketing_strategy`, `get_content_and_campaigns`, `get_creative_deliverables`, `get_run_execution_status`);
A2A agent card manifest (`deploy/a2a/marketing_suite_agent_card.json`) and OpenAPI discovery spec (`deploy/a2a/openapi_spec.yaml`)
for Google Gemini Enterprise registration (Pay-as-you-go edition); 271 offline tests green.
**Exit:** agents discoverable/chattable in Gemini Enterprise for QHHE users.


### Phase 8 — Real distribution integrations ✅ 2026-08-23 (see [docs/superpowers/plans/2026-08-23-phase-8-real-distribution-integrations.md](docs/superpowers/plans/2026-08-23-phase-8-real-distribution-integrations.md))
Meta Marketing API adapter (`suite/distribution/meta_ads.py`) and Resend Email API adapter (`suite/distribution/resend_email.py`);
Human Financial Authorization Gate (`suite/distribution/financial_gate.py`) enforcing `#1ebe82` sign-off, gate status `approved`,
and client budget ceiling validation before any spend or dispatch; FastMCP `platform_apis` server tools (`suite/mcp_servers/server.py`);
zero-risk `dry_run` simulation mode by default; 289 offline tests green.
**Exit:** real multi-channel execution (Meta Ads & Email) fully wired and guarded.


### Phase 9 — Automated Proposal & Presentation Compiler ✅ 2026-08-24 (see [docs/superpowers/plans/2026-08-24-phase-9-automated-proposal-presentation-compiler.md](docs/superpowers/plans/2026-08-24-phase-9-automated-proposal-presentation-compiler.md))
Deliverables and Presentation Rendering Engine (`suite/rendering/`);
Interactive, standalone, responsive **9-Act HTML Presentation Deck** (`presentation_compiler.py`) with metric counters, 2x2 competitive positioning quadrants, real copy artifacts, and `#1ebe82` human gate checklist;
Comprehensive **Executive Detail / PDF Report Annex** (`detail_compiler.py`) with complete ICP breakdowns, 4-week calendar slot matrices, creative registers, and `@media print` layout;
Theme loader and validation (`theme.toml` & dynamic profile derivation in `theme.py`);
Visual creative engine routing (`gemini-3.1-flash-image` vs `gemini-3.1-pro-preview` with safe offline `StubRenderer`);
Django review console endpoints (`/propuestas/<client_id>/<doc_type>/` and `/propuestas/<client_id>/generar/`) and Vertex AI Reasoning Engine tool (`compile_client_proposal`);
313 offline tests green (24 new tests added).
**Exit:** one-click standalone client presentation decks and executive PDF dossiers compiled from Firestore pipeline memory blocks.

**Production Release v0.2.0 ✅ 2026-08-25:**
Promoted Phases 7, 8 and 9 to `agentic-marketing-suite-prod` (Project Number `198112926147`);
GitHub Actions release pipeline verified live via git tag `v0.2.0` (Run 32797756714);
Direct IAP console active on prod; zero-cost fixture orchestrator job verified with all 19 agents.

**Production Release v0.2.1 ✅ 2026-08-25:**
IAP SSO auto-login (`IAPHeaderAuthMiddleware`) and flexible dual authentication (`EmailOrUsernameModelBackend`);
Interactive 6-step client onboarding wizard (`web/templates/nueva.html`) with smart drag & drop file importer (JSON/CSV/TXT), structured fields and executive validation cards (no raw JSON required);
GitHub Actions release pipeline verified live via git tag `v0.2.1` (Run 32865424742); 316 offline tests green.

**Production Release v0.2.2 ✅ 2026-08-26:**
Enabled request-based serverless billing (`cpu_idle: true`) on Cloud Run `console` service in both Dev and Prod stacks;
Eliminated continuous 24/7 idle compute cost, ensuring $0.00 compute spend when idle;
GitHub Actions release pipeline verified live via git tag `v0.2.2` (Run 33007620897); 316 offline tests green.

**Production Release v0.2.3 ✅ 2026-08-27:**
Interactive, human-friendly deliverable cards (`web/console/block_renderers.py` & `bloque.html`) for client profile, audiences, competitive map, strategy, KPI contracts, 4-week calendar, copy library, visual assets, and landing pages (raw JSON relegated to collapsible dev accordion);
Real-time pipeline visibility and live status banners in `sesion.html` (auto-refreshing every 4s during runs, prominent pause warnings with one-click `#1ebe82` approval buttons);
Complete 19-agent value chain DAG organized by 6 layers with mission, deliverable, and handoff tracking (`pipeline_meta.py`);
319 offline tests green.

**Production Release v0.2.5 ✅ 2026-08-27:**
One-click test session cleaner prominent in dashboard header to reset Firestore state from scratch;
Human-friendly deliverable cards properly unwrap canonical agent schema outputs (DEL-17 `website_url`, `name`, `industry`, `offers`, `usp`, `audience_segments` metadata tags, `active_strategy` thesis/mix, `content_calendar` slots, `copy_assets` hooks/captions, and `visual_assets` creative specs);
Full in-place deliverable editor in `bloque.html` (`block_edit` endpoint) enabling human reviewers to adjust any field or copy and approve with changes;
CI/CD race-condition prevention in `promote-prod.yml` with polling retry loop;
323 offline tests green.

**Production Release v0.2.6 ✅ 2026-08-27:**
Card-based deliverable UI across all stages (`audience_segments`, `competitive_map`, `campaign_registry`, `trend_signals`, `content_plan`, `content_calendar`, `copy_assets`, `visual_assets`), eliminating raw JSON display across the entire pipeline review interface;
Individual card action buttons (`✏️ Editar`, `🗑️ Eliminar`) and addition buttons (`➕ Añadir Nuevo...`) with interactive modal dialogs (no raw JSON required for adding/modifying audience ICPs, competitors, campaigns, content slots, or copy variants);
Human edits automatically persist to Firestore memory blocks and are seamlessly reloaded upon gate promotion (`suite/orchestration/adk_workflow.py`);
Pipeline re-execution mechanism (`restart_run_from` and `session_restart_from` endpoint) to re-run all downstream stages from any corrected previous block onwards;
325 offline tests green.

**Release v0.2.7 (Hackathon Fortified Fleet & Model Armor) ✅ 2026-08-29:**
Auditoría integral y alineación a los 4 pilares de Fortified Enterprise Fleet para el All Things Agentic Hackathon;
Aislamiento de inputs de clientes reales al vault local (`~/.agent_dispatcher/`) y endurecimiento en `.gitignore`;
Gobernanza IAP en Pulumi (`infra/__main__.py`) con acceso para evaluadores (`testing@devpost.com`, `cloudhackathons@google.com`);
Contrato de onboarding corporativo en inglés (`suite/inputs/acme_global.json`);
Módulo Model Armor con Google Gemma (`suite/security/model_armor.py`) para defensa contra prompt injection, sanitización de PII y bloqueo de tool poisoning;
README.md exhaustivo con arquitectura visual Mermaid, matriz de 19 agentes e instrucciones de spin-up paso a paso;
335 offline tests green (10 nuevos tests unitarios de seguridad perimetral).



## Standing rules

- Human gate is sacred: nothing publishes or spends without explicit approval;
  `#1ebe82` reserved for human-gate UI.
- Secrets: local via `~/.agent_dispatcher/` vault; cloud via Secret Manager. Never in
  repo/env files.
- Client-facing output: español es-MX profesional, sin anglicismos.
- Every phase keeps the 207-test offline suite green and adds its own tests.

