# Workflows — reusable multi-agent orchestration

Deterministic, multi-agent pipelines for this project's recurring heavy work.
Run with the **Workflow** tool: `Workflow({ scriptPath: "workflows/<file>.js", args: {...} })`.
They spawn subagents that read the relevant briefs/specs and write files — so they
encode the *process*, while the agent briefs in `agents/` encode the *role*.

| Workflow | What it does | Args |
|---|---|---|
| `build-product-agent.js` | Builds **one** product agent end-to-end: contract (from ARCHITECTURE) → system prompt + spec w/ cost profile + code stub on `base.py` + tests (parallel) → adversarial review. | `{ agent_id, layer, slug }` e.g. `{"agent_id":"1.2","layer":"layer1","slug":"audience_intelligence"}` |
| `build-all-agents.js` | Builds **all 18 remaining** agents in one fan-out (pipeline: author 7 artifacts per agent → independent adversarial review). Uses a pre-assigned, collision-free identifier table (slugs, DEL numbers, schema/block names, model tiers) so the parallel builders never clash. Produces: prompt asset + JSON schema + code on `base.py` + offline fixture + tests + spec + DEL wrapper, per agent. Ran in Session 4. | none (table is inline) |

## Related, not workflows

- **`/wrap`** — session-end protocol. It's an *agent brief* (`agents/session-wrapper.md`), run inline, not a Workflow script (it's sequential bookkeeping, not fan-out).
- **`tools/check_stack_currency.sh`** — fast deterministic gate (no agents); run in review + at wrap.
- **`agents/researcher.md` + the `deep-research` skill** — for S1-T6 competitor scan; the skill already provides the fan-out/verify/synthesize harness, so no separate workflow script is needed.

## Conventions

- Keep `meta` a pure literal (name/description/phases). Read files inside subagents with the file tools; don't assume state.
- Prefer `pipeline()` for multi-stage per-item work; `parallel()` only when you need all results together (as in the Author phase here).
- After a workflow writes agent files, the human/PM still runs `pytest -q` and the Deliverable Reviewer gate before shipping.
