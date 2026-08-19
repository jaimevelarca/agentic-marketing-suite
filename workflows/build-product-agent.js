export const meta = {
  name: 'build-product-agent',
  description: 'Build one Digital Marketing AI Suite product agent: contract → system prompt → spec+cost profile → code stub on base.py → tests → adversarial review',
  whenToUse: 'When building the next product agent (1.2, 1.3, …). Pass args = { agent_id, layer, slug } e.g. {"agent_id":"1.2","layer":"layer1","slug":"audience_intelligence"}.',
  phases: [
    { title: 'Contract', detail: 'extract the agent contract from ARCHITECTURE + layer data design' },
    { title: 'Author', detail: 'system prompt + agent spec (with cost profile) + code stub + tests, in parallel' },
    { title: 'Review', detail: 'adversarial quality + cost + stack-currency review; synthesize a verdict' },
  ],
}

const ROOT = "/Users/jaimesalcedovelarca/Library/CloudStorage/GoogleDrive-jaimevelarca@gmail.com/My Drive/Jaime/Work/QueHueva/Operaciones/Clientes/AcmeCo"

const A = (args && args.agent_id) || "1.2"
const LAYER = (args && args.layer) || "layer1"
const SLUG = (args && args.slug) || "audience_intelligence"

const COMMON = `
You are working in the Acme Co. BU repo at ROOT:
${ROOT}
Stack is single-vendor GCP (ADR-04) — never the retired n8n/Supabase/CrewAI stack. Read the briefs/specs you need with the file tools.
Target product agent: ${A} (layer ${LAYER}, slug ${SLUG}).
Authoritative contract: project/specs/ARCHITECTURE.md (this agent's row: job, human-gate tier, memory blocks read/written).
Build standard: agents/product-agent-builder.md. Code base: suite/agents/base.py (reference: suite/agents/layer1/agent_1_1.py). Cost rules: project/specs/AGENT_COST_MODEL.md + agents/_TEMPLATE_agent-spec.md (mandatory Cost & Runtime Profile, D-07).
`

phase('Contract')
const contract = await agent(
  `${COMMON}\nExtract and return the COMPLETE build contract for agent ${A}: its one-line job, inputs, outputs, the memory block(s) it writes, downstream consumers, human-gate tier, and the recommended model tier (Haiku/Sonnet/Opus) with a one-sentence cost rationale. Read ARCHITECTURE.md and the layer data-design file. Do not write files yet.`,
  { label: `contract:${A}`, phase: 'Contract' }
)

phase('Author')
const [promptRes, specRes, codeRes] = await parallel([
  () => agent(
    `${COMMON}\nContract:\n${contract}\n\nWRITE the system-prompt deliverable for agent ${A} following the DEL-10 structure (role · inputs · processing rules · outputs · critical rules · output format) with project YAML front-matter, to phases/${LAYER === 'layer1' ? '01-foundation' : 'NN'}/deliverables/ using the next free DEL number. ALSO write the versioned prompt asset to suite/agents/${LAYER}/prompts/${SLUG}_system.txt (the machine source of truth). Return the paths written.`,
    { label: `prompt:${A}`, phase: 'Author' }
  ),
  () => agent(
    `${COMMON}\nContract:\n${contract}\n\nWRITE the agent spec agents/${A}-${SLUG}.md from agents/_TEMPLATE_agent-spec.md — fill EVERY section, especially §2 Cost & Runtime Profile (model tier + rationale, token budgets, run cadence per tier, caching, revision factor, est. cost). Then add this agent's parameter row to project/specs/agent_cost_model.py and note the new per-tier totals. Return the spec path + the agent's modeled $/run.`,
    { label: `spec+cost:${A}`, phase: 'Author' }
  ),
  () => agent(
    `${COMMON}\nContract:\n${contract}\n\nWRITE the code stub suite/agents/${LAYER}/${SLUG}.py subclassing BaseAgent (implement build_user_turn; set agent_id/prompt_asset/model/schema_name; override route() only if needed) — target ~40-60 lines, reuse base.py, do not re-implement parsing/validation/routing. ALSO write tests/agents/test_${SLUG}.py mirroring tests/agents/test_base_agent.py (parsers, schema valid/invalid, mocked run()). Return the paths and confirm the test file is self-contained/offline.`,
    { label: `code+tests:${A}`, phase: 'Author' }
  ),
])

phase('Review')
const REVIEW_SCHEMA = {
  type: "object", additionalProperties: false,
  properties: {
    verdict: { type: "string", enum: ["ship", "ship-with-fixes", "rework"] },
    must_fix: { type: "array", items: { type: "string" } },
    should_fix: { type: "array", items: { type: "string" } },
    cost_ok: { type: "boolean" },
    stack_currency_ok: { type: "boolean" },
    tests_runnable: { type: "boolean" },
    notes: { type: "string" }
  },
  required: ["verdict", "must_fix", "should_fix", "cost_ok", "stack_currency_ok", "tests_runnable", "notes"]
}
const review = await agent(
  `${COMMON}\nYou are the Deliverable Reviewer (agents/deliverable-reviewer.md). Adversarially review the just-built agent ${A}. Open the files written: the DEL prompt + prompt asset, the agent spec, the code stub, the tests. Check the review dimensions — especially: (a) contract fit vs ARCHITECTURE, (b) the §2 Cost & Runtime Profile is present + consistent with AGENT_COST_MODEL.md and uses Opus ONLY if binding, (c) NO retired-stack terms, (d) tests are offline/self-contained and would plausibly pass. Authoring outputs:\nPROMPT: ${promptRes}\nSPEC+COST: ${specRes}\nCODE+TESTS: ${codeRes}\nReturn a structured verdict.`,
  { label: `review:${A}`, phase: 'Review', schema: REVIEW_SCHEMA }
)

return { agent: A, contract, authored: { promptRes, specRes, codeRes }, review }
