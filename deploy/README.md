# Deployment — Digital Marketing AI Suite

How the suite ships to Google Cloud. **Model backbone = Claude on the Anthropic
first-party API** (the validated path); Cloud Run runs the orchestration. Vertex
Claude is a later one-env-var flip (`SUITE_LLM_PROVIDER=vertex`) once Vertex Claude
quota is granted — see "Switching to Vertex later" below. All of this also runs
*offline today* via `python -m orchestration.demo` (no GCP, no API key needed).

## Topology

```
Pub/Sub (per-layer topics)  ──►  Cloud Workflows (suite-pipeline.yaml)
                                        │  one execution per agent, in DAG order
                                        ▼
                                 Cloud Run Job  (deploy/Dockerfile)
                                  └ orchestration.job_entrypoint
                                      AGENT_ID + CLIENT_ID  ──► BaseAgent.run
                                        │ Claude via Anthropic API (cached system prompt)
                                        │ ANTHROPIC_API_KEY ◄─ Secret Manager
                                        ▼
        Cloud SQL (client_profiles + memory_blocks)  ◄─ validated block
        Firestore (review_queue)  ◄─ human-gate doc  ──► Firebase review UI
        MCP servers (Cloud Run)  ──► serve blocks back to downstream agents
```

The readable source of truth for the DAG (order, reads/writes, gates) is
`suite/orchestration/pipeline.py`. `workflows/suite-pipeline.yaml` mirrors it.

## Artifacts

| File | Purpose |
|---|---|
| `Dockerfile` | One image for any agent / the whole pipeline (`orchestration.job_entrypoint`). |
| `.dockerignore` | Keep the image lean (ships `suite/` + schemas only). |
| `cloudbuild.yaml` | Build → push to Artifact Registry → update the Cloud Run Job. |
| `workflows/suite-pipeline.yaml` | Cloud Workflows choreography with human-gate waits. |
| `../suite/agents/adk_wrapper.py` | Wrap an agent as a Vertex Agent Engine (`google-adk`) LlmAgent. |
| `../suite/mcp/server.py` | Per-domain MCP servers (brand_core / audience_map / campaign_registry / platform_apis). |
| `../suite/migrations/*.sql` | Cloud SQL schema (client_profiles + generic memory_blocks). |

## First-deploy checklist (Anthropic-direct backbone)

1. **Anthropic key → Secret Manager.** Get an `ANTHROPIC_API_KEY` from
   console.anthropic.com → API Keys, then:
   `printf '%s' "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-`
   (or `gcloud secrets versions add anthropic-api-key --data-file=-` to rotate).
   Grant the runtime service account `roles/secretmanager.secretAccessor` on it.
2. (Recommended) Set a monthly budget with 50/90/100% alerts in Cloud Billing.
3. `psql … -f suite/migrations/001_client_profiles.sql` then `002_memory_blocks.sql`.
4. `gcloud builds submit --config deploy/cloudbuild.yaml --substitutions=_TAG=$(git rev-parse --short HEAD)`.
5. Prereqs the build expects: an Artifact Registry repo `suite`, a runtime service
   account, the `db-app-password` + `anthropic-api-key` secrets, per-layer Pub/Sub
   topics, and the `suite-agent-job` Cloud Run Job. The build's `deploy-job` step
   wires both secrets and `SUITE_LLM_PROVIDER=anthropic` onto the job.
6. `gcloud workflows deploy suite-pipeline --source=deploy/workflows/suite-pipeline.yaml --location=us-central1`.
7. Smoke-run Agent 1.1 live, then re-baseline the per-agent cost model against real traces.

## Switching to Vertex later

The model backbone is a single switch. Once Vertex Claude quota is granted on the
target project: accept the Anthropic EULAs in Vertex Model Garden, drop the
`ANTHROPIC_API_KEY` secret from the `deploy-job` step, and set
`--set-env-vars=SUITE_LLM_PROVIDER=vertex,SUITE_BACKEND=gcp` in `cloudbuild.yaml`
(and the Dockerfile `ENV`). No agent code changes — same prompts, same model
strings (Vertex re-adds the `@<date>` suffix on Haiku automatically).
