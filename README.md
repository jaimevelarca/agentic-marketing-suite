# Agentic Marketing Suite (`agentic-marketing-suite`)

QHHE's reusable six-layer / **19-agent** engine that automates the digital-marketing
lifecycle — intelligence → strategy → content planning → production → distribution →
analytics + feedback — for any SMB client, now being rebuilt ground-up for
production on GCP: **Pulumi IaC · ADK 2.x + Gemini · Cloud Run · Firestore ·
Django review UI**. See **[ROADMAP.md](ROADMAP.md)** and
[docs/REVIEW-2026-08-19.md](docs/REVIEW-2026-08-19.md) for where this is headed and
why.

Successor to `ai-marketing-suite` (imported at `a65f48e`). GCP project:
**`agentic-marketing-suite`** (QHHE folder). No client-confidential material lives
here; a client is seeded with one onboarding JSON in `suite/inputs/<client>.json`
(sample: `acme.json`).

## Layout

| Path | What |
|---|---|
| `suite/agents/layer{1..6}/` | The 19 product agents on a shared `BaseAgent` (`suite/agents/base.py`): versioned system-prompt asset + JSON output schema + ~40 lines of contract code each. |
| `suite/orchestration/pipeline.py` | The authoritative DAG: agent order, reads/writes, human-gate map. `demo.py` runs it offline. |
| `suite/infra/` | Config (`config.py`), LLM/backend adapters (`clients.py`), logging (`log.py`), schema-skeleton helper. |
| `project/resources/schemas/` | JSON Schema for every memory block an agent produces. |
| `suite/fixtures/` | Canned per-agent outputs so the whole suite runs **offline**. |
| `exports/` | Platform-neutral per-agent export bundle (prompt + schema + config + manifest). Regenerate with `scripts.export_agents`. |
| `infra/` | Pulumi IaC (roadmap Phase 1 — arriving). |
| `deploy/` | Legacy GCP scaffolding from the baseline; superseded per the roadmap. |
| `tests/` | 207 tests, all offline. |

## Runtime switches (independent, safe by default)

Set via env (`suite/infra/config.py`); **defaults are offline** (`fixture` +
`memory`) — production is an explicit opt-in:

- `SUITE_LLM_PROVIDER` — `fixture` (default, canned outputs) · `anthropic` ·
  `vertex` · `gemini` (Phase 3).
- `SUITE_BACKEND` — `memory` (default, in-process) · `gcp` (Firestore from Phase 2).

## Quickstart

```bash
uv sync --extra dev                    # project venv, Python 3.12

# Run the whole suite offline — no GCP, no API key
PYTHONPATH=suite .venv/bin/python -m orchestration.demo    # → 19/19 agents valid

.venv/bin/python -m pytest -q          # → 207 passed

# (Re)generate the loadable export bundle
PYTHONPATH=suite .venv/bin/python -m scripts.export_agents
```

## Onboard a new client

1. Copy `suite/inputs/acme.json` → `suite/inputs/<client>.json` and fill it in
   (client-confidential inputs stay out of the repo — vault or Firestore).
2. Point a run at it: `INPUT_FILE=suite/inputs/<client>.json`.
3. The client name lives only in that input file — nothing else is client-specific.
