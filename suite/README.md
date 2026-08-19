# `suite/` — Digital Marketing AI Suite (implementation)

The runnable product: 19 agents across 6 layers on a shared runner, an orchestrator
that chains them through the human-gate map, and infra that talks to Google Cloud
(ADR-04) **or** runs fully offline for dev/demo.

## Layout

```
suite/
├── agents/
│   ├── base.py            # BaseAgent: prompt-load + cache + parse + schema-validate + route
│   ├── adk_wrapper.py     # wrap an agent as a Vertex Agent Engine (google-adk) LlmAgent
│   ├── layer1..layer6/    # one module per product agent (+ prompts/<slug>_system.txt assets)
│   └── layerN/prompts/    # versioned system-prompt assets (machine source of truth)
├── orchestration/
│   ├── pipeline.py        # the 6-layer/19-agent DAG + run_pipeline() (source of truth)
│   ├── demo.py            # offline end-to-end runner
│   └── job_entrypoint.py  # Cloud Run Job entry (one agent, or the whole pipeline)
├── infra/
│   ├── config.py          # settings: GCP names + model routing + runtime switches
│   └── clients.py         # LLM provider (vertex|fixture) + memory/review/pubsub + schema loader
├── mcp/server.py          # per-domain MCP servers (brand_core/audience_map/campaign_registry/platform_apis)
├── fixtures/<id>.txt      # canned, schema-valid per-agent outputs for offline runs
└── migrations/*.sql       # Cloud SQL schema (client_profiles + generic memory_blocks)
```

Per-block JSON Schemas live at `../project/resources/schemas/<block>.json`; each
agent's `schema_name` / `memory_block` is its block name. Each agent's system
prompt is a versioned asset at `agents/layer{N}/prompts/<slug>_system.txt`. The
loadable per-agent bundle (prompt + schema + config) is generated into
`../exports/` by `scripts.export_agents` — see `../LOADING.md`.

## Run it offline (no GCP, no API key)

Two independent switches make the whole thing runnable locally:
`SUITE_LLM_PROVIDER=fixture` (canned per-agent outputs) and `SUITE_BACKEND=memory`
(in-process store). The demo sets both for you:

```bash
python -m venv .venv && . .venv/bin/activate
pip install pytest jsonschema           # offline tests/demo need only these
PYTHONPATH=suite python -m orchestration.demo            # full pipeline
PYTHONPATH=suite python -m orchestration.demo --stop-after L1   # Phase-1 milestone
PYTHONPATH=suite python -m orchestration.demo --no-approve      # halt at first gate
```

## Test

```bash
pip install -e '.[dev]'    # or: pip install pytest jsonschema
pytest -q                  # unit (base + per-agent) + tests/test_pipeline.py (offline e2e)
```

## Production

Model backbone `SUITE_LLM_PROVIDER=anthropic` (Claude via the Anthropic API, key
from Secret Manager) + `SUITE_BACKEND=gcp`. Agents run as Cloud Run Jobs chained by
Cloud Workflows + Pub/Sub; blocks persist to Cloud SQL; gates queue to Firestore for
the Firebase review UI. Vertex Claude is a one-env-var flip (`=vertex`) once quota is
granted. Full first-deploy checklist in `../deploy/README.md`; loading individual
agents into Claude Console / Vertex Agent Engine in `../LOADING.md`.
