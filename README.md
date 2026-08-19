# AI Marketing Suite (`ai-mkt-suite`)

A reusable, six-layer / **19-agent** system that automates the digital-marketing
lifecycle — intelligence → strategy → content planning → production → distribution
→ analytics + feedback — for any SMB client.

This is the **product engine only**, genericized from its original pilot. There is
no client-confidential material here (no COGS/margins, no client branding). Drop in
a client by editing `suite/inputs/<client>.json`; the sample client is **Acme Co.**
(`suite/inputs/acme.json`).

> **Want to load the agents into Claude Console or Google's agent platform?**
> See **[LOADING.md](LOADING.md)** — it explains both paths and uses the ready-made
> per-agent bundle in [`exports/`](exports/).

---

## Layout

| Path | What |
|---|---|
| `suite/agents/layer{1..6}/` | The 19 product agents on a shared `BaseAgent` (`suite/agents/base.py`). Each agent = a versioned system-prompt asset (`prompts/*_system.txt`) + a JSON output schema + ~40 lines of contract code. |
| `suite/orchestration/pipeline.py` | The authoritative DAG: agent order, what each reads/writes, and the human-gate map. `demo.py` runs it offline. |
| `suite/infra/` | Config (`config.py`), client/LLM/DB adapters (`clients.py`), schema-skeleton helper. |
| `project/resources/schemas/` | The JSON Schema for every memory block an agent produces (one per output). |
| `suite/fixtures/` | Canned per-agent outputs so the whole suite runs **offline** (no GCP, no API key). |
| `suite/inputs/` | Sample client onboarding payloads (`acme.json`, `acme_test.json`). |
| `exports/` | **Platform-neutral export bundle** — per-agent system prompt + output schema + config + a roster `manifest.json`. Regenerate with `scripts.export_agents`. |
| `deploy/` | GCP deployment scaffolding (Dockerfile, Cloud Build, Cloud Workflows). |
| `tests/` | 207 tests, all offline. |

## Runtime switches (independent)

Set via env (`suite/infra/config.py`):

- `SUITE_LLM_PROVIDER` — `fixture` (offline canned outputs) · `anthropic` (Claude
  first-party API, needs `ANTHROPIC_API_KEY`) · `vertex` (Claude on Vertex Model Garden).
- `SUITE_BACKEND` — `memory` (in-process, for dev/tests) · `gcp` (Cloud SQL / Firestore / Pub-Sub).

## Quickstart

> **This folder lives on Google Drive — keep the virtualenv OUT of it.** Never run a
> bare `uv venv` here (it would create `.venv/` in the synced folder). Put the venv on
> local disk, outside Drive (e.g. `~/.venvs/`), as shown below.

```bash
# 1. Environment (uv; Python 3.12) — venv lives OFF Drive
uv venv ~/.venvs/ai-mkt-suite --python 3.12
source ~/.venvs/ai-mkt-suite/bin/activate
uv pip install -e ".[dev]"          # add ,adk and/or ,mcp extras when deploying

# Optional: also keep bytecode / pytest caches off Drive
export PYTHONPYCACHEPREFIX=~/.cache/ai-mkt-suite/pycache

# 2. Run the whole suite OFFLINE (fixtures + in-memory backend) — no GCP, no key
PYTHONPATH=suite SUITE_LLM_PROVIDER=fixture SUITE_BACKEND=memory \
  python -m orchestration.demo       # → 19/19 agents valid

# 3. Tests
python -m pytest -q                  # → 207 passed

# 4. (Re)generate the loadable export bundle in exports/
PYTHONPATH=suite python -m scripts.export_agents
```

## Going live

- **Claude / Google agent platforms:** see **[LOADING.md](LOADING.md)**.
- **Full GCP deployment** (Cloud Run Jobs + Pub/Sub + Cloud Workflows): see
  [`deploy/README.md`](deploy/README.md).

## Onboard a new client

1. Copy `suite/inputs/acme.json` → `suite/inputs/<client>.json` and fill it in.
2. Point a run at it: `INPUT_FILE=suite/inputs/<client>.json` (used by `suite/scripts/*`).
3. The client name lives only in that input file — nothing else is client-specific.
