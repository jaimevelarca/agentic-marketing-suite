# Loading the agents into Claude Console or Google's agent platform

The 19 agents are exported in a **platform-neutral bundle** under [`exports/`](exports/)
so you can load them either way without reading the Python. Regenerate the bundle
any time the prompts or schemas change:

```bash
PYTHONPATH=suite python -m scripts.export_agents      # writes exports/
```

### What's in the bundle

```
exports/
  manifest.json                       # roster: id, name, layer, model tier, output block, gate
  agents/<id>_<slug>/
    system_prompt.txt                 # raw, human-editable system prompt
    system_prompt.full.txt            # prompt as sent in production = system_prompt + the
                                      #   required OUTPUT-1 JSON structure appended inline
    output_schema.json                # JSON Schema of the agent's output block
    config.json                       # model, model_tier, max_tokens, memory_block, reads, gate
```

Two ways to use a bundle per platform:
- **Schema-native** — give the platform `system_prompt.txt` *and* `output_schema.json`
  (as a tool/structured-output spec). The platform enforces the shape.
- **Prompt-embedded** — give the platform only `system_prompt.full.txt`. The schema is
  baked into the prompt text, so it works anywhere you can set a system prompt (e.g. the
  Console Workbench), with no separate schema field.

`config.json.model` carries a **Vertex** model id (e.g. `claude-sonnet-4-6`,
`claude-haiku-4-5@20251001`). The three tiers are: **primary** = Sonnet (generation),
**routing** = Haiku (classification), **deep** = Opus (binding reasoning, agent 2.1 only).
Map the id to your platform's naming when loading (see each section below).

---

## Option A — Claude Console / Anthropic API

There are two levels: run the whole suite against Claude, or lift individual agents
into the Console.

### A1. Run the entire suite against the Anthropic API (fastest)

The suite already speaks to Claude's first-party API — no code changes.

```bash
export ANTHROPIC_API_KEY=sk-ant-...           # from console.anthropic.com → API Keys
export SUITE_LLM_PROVIDER=anthropic
export SUITE_BACKEND=memory                    # or gcp once Cloud SQL is up
PYTHONPATH=suite python -m scripts.demo_anthropic    # runs the pipeline live on Claude
```

Anthropic API model ids differ slightly from Vertex's (dated Haiku suffix). Override the
three model env vars if needed:

```bash
export CLAUDE_MODEL_SONNET=claude-sonnet-4-6
export CLAUDE_MODEL_HAIKU=claude-haiku-4-5-20251001   # API uses -YYYYMMDD, not @YYYYMMDD
export CLAUDE_MODEL_OPUS=claude-opus-4-8
```

### A2. Lift one agent into the Console Workbench (no code)

1. Open **console.anthropic.com → Workbench**.
2. Open `exports/agents/<id>_<slug>/system_prompt.full.txt` and paste it as the **System
   prompt** (the `.full` variant already contains the required JSON output structure).
3. Set **Model** and **Max tokens** from that agent's `config.json` (`model_tier`/`max_tokens`).
4. For the user turn, paste the upstream blocks the agent `reads` (from `config.json.reads`)
   as JSON — for layer-1 agents that's just the client onboarding input.
5. Optionally **Save** it as a Console prompt and call it by id from the SDK
   (`anthropic.messages.create(..., system=<that prompt>)`), wiring `output_schema.json`
   as a tool `input_schema` if you prefer schema-native structured output over the embedded one.

> The agents are a **DAG**, not standalone bots: an agent consumes the validated output
> blocks of the agents before it (`config.json.reads`) and most outputs pass a **human
> review gate** (`config.json.gate`/`human_gated`) before the next layer reads them. The
> readable source of that wiring is `suite/orchestration/pipeline.py`. The Console is great
> for iterating on a single agent's prompt; use the suite (A1) to run the chain.

---

## Option B — Google Vertex AI / Agent Engine (ADK)

The suite's **default** provider is Claude on **Vertex AI Model Garden**
(`SUITE_LLM_PROVIDER=vertex`), and `suite/agents/adk_wrapper.py` wraps any agent as a
google-adk `LlmAgent` for **Vertex AI Agent Engine** (managed tracing, versioning, sessions).

### One-time GCP setup

1. Create/choose a project and set `GCP_PROJECT_ID`, `GCP_REGION` (`us-central1`),
   `VERTEX_REGION` (`global` by default — see `suite/infra/config.py`).
2. In **Vertex AI → Model Garden**, enable Claude (Sonnet 4.6 / Haiku 4.5 / Opus) and
   **accept the Anthropic EULA** for each model you'll use.
3. `gcloud auth application-default login` (or attach a runtime service account).

### B1. Run the suite on Vertex

```bash
export SUITE_LLM_PROVIDER=vertex
export GCP_PROJECT_ID=<your-project>
PYTHONPATH=suite python -m orchestration.demo        # now generates via Claude on Vertex
```

### B2. Deploy an agent to Vertex AI Agent Engine (ADK)

```bash
# into your off-Drive venv (see README — never create .venv inside this Drive folder)
uv pip install -e ".[adk]"                            # the google-adk extra
```
```python
from agents.adk_wrapper import to_adk_agent
from agents.layer1.agent_1_1 import AGENT             # any agent module exposes AGENT
root = to_adk_agent(AGENT)
# then deploy `root` with `adk deploy` / vertexai Agent Engine create
```

Each agent's `config.json.model` is already a Vertex model id, so no remapping is needed
on this path. To define an agent by hand in **Agent Builder / Agent Garden** instead, use
`system_prompt.txt` as the instruction and `output_schema.json` as the structured-output
schema.

### B3. Full pipeline on GCP (Cloud Run Jobs + Pub/Sub + Cloud Workflows)

The production topology — one Cloud Run Job per agent, chained by Pub/Sub and Cloud
Workflows with human-gate waits — is scaffolded in [`deploy/`](deploy/). Follow
[`deploy/README.md`](deploy/README.md) (build image → push to Artifact Registry → deploy
the Cloud Workflow). `deploy/workflows/suite-pipeline.yaml` mirrors
`suite/orchestration/pipeline.py`.

---

## Which path?

| You want… | Use |
|---|---|
| Iterate on one agent's prompt, fast | **A2** Console Workbench + `system_prompt.full.txt` |
| Run the whole chain against Claude today, no GCP | **A1** `SUITE_LLM_PROVIDER=anthropic` |
| Managed agents (tracing/versioning/sessions) on Google | **B2** ADK → Agent Engine |
| Production, scheduled, multi-client on GCP | **B3** `deploy/` + Cloud Workflows |
