export const meta = {
  name: 'build-all-agents',
  description: 'Build all 18 remaining Digital Marketing AI Suite product agents (prompt asset + JSON schema + code on base.py + offline fixture + tests + spec + DEL wrapper), each adversarially reviewed. Offline-runnable, collision-free.',
  whenToUse: 'Session 4 breadth build: turn the 6-layer/19-agent architecture into coded, offline-runnable agents on suite/agents/base.py.',
  phases: [
    { title: 'Author', detail: 'one builder per agent writes 7 artifacts following the validated Agent-1.1 pattern' },
    { title: 'Review', detail: 'independent adversarial reviewer per agent: schema valid, fixture matches schema+markers, code correct vs base.py, tests offline, no retired stack' },
  ],
}

const ROOT = "/Users/jaimesalcedovelarca/Library/CloudStorage/GoogleDrive-jaimevelarca@gmail.com/My Drive/Jaime/Work/QueHueva/Operaciones/Clientes/AcmeCo"

// Canonical, pre-assigned identifiers so 18 parallel builders never collide.
// model_var: model_primary=Sonnet, model_routing=Haiku, model_deep=Opus (per AGENT_COST_MODEL.md).
const AGENTS = [
  { id: "1.2", cls: "Agent12", slug: "audience_intelligence", layer: "layer1", phase: "01-foundation", del: "DEL-11", model_var: "model_primary", max_tokens: 8000, gate: "review", block: "audience_segments", name: "Audience Intelligence", reads: ["client_profile"], raw: ["crm_data","ga4_data","social_analysis","survey_data","persona_docs"], note: "Its full system prompt ALREADY EXISTS at phases/01-foundation/deliverables/DEL-11_agent_1_2_system_prompt.md §2 — ADAPT it into the .txt asset; do NOT rewrite from scratch. DEL-11 already exists so do NOT create a new DEL file; instead update DEL-11 status. Convert DEL-11's bare ARRAY of segments into an OBJECT for OUTPUT-1: {client_id, created_at, gate_status, segments:[...]} so base.py object-routing works." },
  { id: "1.3", cls: "Agent13", slug: "competitive_intelligence", layer: "layer1", phase: "01-foundation", del: "DEL-19", model_var: "model_primary", max_tokens: 8000, gate: "review-only", block: "competitive_map", name: "Competitive Intelligence", reads: ["client_profile"], raw: ["competitor_list","positioning_notes","industry_benchmarks","scraper_output"], note: "Confidence-tier metadata like Agent 1.1/1.2. Identify 3-5 competitors, positioning, content gaps, SWOT, benchmarks. Review-only gate." },
  { id: "1.4", cls: "Agent14", slug: "trend_radar", layer: "layer1", phase: "01-foundation", del: "DEL-20", model_var: "model_routing", max_tokens: 4000, gate: "autonomous", block: "trend_signals", name: "Trend Radar", reads: ["client_profile"], raw: ["rss_feeds","hashtags","seasonal_themes"], note: "Haiku, fully AUTONOMOUS (no human gate): set gate_status='auto_approved'. Time-indexed signals with relevance/velocity/ttl/estimated_peak_date." },
  { id: "2.1", cls: "Agent21", slug: "strategy_orchestrator", layer: "layer2", phase: "02-strategy-planning", del: "DEL-21", model_var: "model_deep", max_tokens: 8000, gate: "binding", block: "active_strategy", name: "Strategy Orchestrator", reads: ["client_profile","audience_segments","competitive_map","trend_signals"], raw: [], note: "OPUS — the ONLY binding-decision agent; justify Opus in the spec. OUTPUT-1 active_strategy MUST embed a nested 'kpi_contracts' object (objectives→KPI targets) since 2.1 writes both blocks. Binding human gate: gate_status defaults to 'pending_review' and must be approved before Layer 3 reads it." },
  { id: "2.2", cls: "Agent22", slug: "campaign_planner", layer: "layer2", phase: "02-strategy-planning", del: "DEL-22", model_var: "model_primary", max_tokens: 8000, gate: "review", block: "campaign_registry", name: "Campaign Planner", reads: ["active_strategy","client_profile","audience_segments"], raw: [], note: "Campaign themes, messaging pillars, timing, per-campaign budget split. Reads approved active_strategy." },
  { id: "3.1", cls: "Agent31", slug: "monthly_marketing_deck", layer: "layer3", phase: "02-strategy-planning", del: "DEL-23", model_var: "model_primary", max_tokens: 12000, gate: "review", block: "content_plan", name: "Monthly Marketing Deck", reads: ["campaign_registry","audience_segments","active_strategy","trend_signals"], raw: [], note: "Topics/formats/CTAs per campaign per week → content_plan (feeds content_calendar). Editorial review gate." },
  { id: "3.2", cls: "Agent32", slug: "content_scheduler", layer: "layer3", phase: "02-strategy-planning", del: "DEL-24", model_var: "model_primary", max_tokens: 8000, gate: "review", block: "content_calendar", name: "Content Scheduler", reads: ["content_plan","campaign_registry"], raw: ["platform_rules"], note: "Cadence, platform, day/time, format rules → content_calendar. Calendar review gate." },
  { id: "3.3", cls: "Agent33", slug: "approval_workflow", layer: "layer3", phase: "02-strategy-planning", del: "DEL-25", model_var: "model_routing", max_tokens: 3000, gate: "queue-mgr", block: "approval_log", name: "Approval Workflow", reads: ["content_calendar"], raw: [], note: "Haiku queue manager. Routes items for review, tracks status, alerts. OUTPUT-1 = approval_log entries (routing decisions). gate_status='auto_approved'." },
  { id: "4.1", cls: "Agent41", slug: "copy_prompt_engine", layer: "layer4", phase: "03-production-distribution", del: "DEL-26", model_var: "model_primary", max_tokens: 8000, gate: "risk-tiered", block: "copy_assets", name: "Copy + Prompt Engine", reads: ["content_calendar","audience_segments","competitive_map","client_profile"], raw: [], note: "Captions, hooks, CTAs + image-gen prompts. CLIENT-FACING copy VALUES in Español (MX) per brand/acme/guidelines/formatting-guide.md; the prompt/spec themselves stay English. Respect client_profile.constraints + brand_voice_tokens." },
  { id: "4.2", cls: "Agent42", slug: "visual_creative", layer: "layer4", phase: "03-production-distribution", del: "DEL-27", model_var: "model_primary", max_tokens: 8000, gate: "batch-review", block: "visual_assets", name: "Visual Creative", reads: ["content_calendar","copy_assets","client_profile"], raw: [], note: "Produces image/video GENERATION PROMPTS + asset metadata (not pixels) for Flux 2 Pro / Ideogram 3.0 / Kling 2.5 via fal.ai (ADR-04). Batch review gate." },
  { id: "4.3", cls: "Agent43", slug: "web_landing_pages", layer: "layer4", phase: "03-production-distribution", del: "DEL-28", model_var: "model_primary", max_tokens: 12000, gate: "full-review", block: "page_assets", name: "Web + Landing Pages", reads: ["campaign_registry","audience_segments","copy_assets"], raw: [], note: "Landing page copy + structure + A/B variants → page_assets. Full review gate. ES-MX page copy values." },
  { id: "4.4", cls: "Agent44", slug: "email_whatsapp", layer: "layer4", phase: "03-production-distribution", del: "DEL-29", model_var: "model_primary", max_tokens: 8000, gate: "first-deploy", block: "message_flows", name: "Email / WhatsApp", reads: ["audience_segments","content_calendar"], raw: [], note: "Email + WhatsApp nurture sequences → message_flows. Resend (email) + Twilio WhatsApp Business API (ADR-04). First-deploy gate. ES-MX message values." },
  { id: "5.1", cls: "Agent51", slug: "campaign_launcher", layer: "layer5", phase: "03-production-distribution", del: "DEL-30", model_var: "model_primary", max_tokens: 8000, gate: "financial-auth", block: "ad_campaign_log", name: "Campaign Launcher", reads: ["campaign_registry","copy_assets","page_assets","active_strategy"], raw: [], note: "Builds Meta/Google/TikTok Ads campaign SETUP SPEC (budgets, targeting, ad sets) → ad_campaign_log. FINANCIAL-AUTH gate: gate_status='pending_review', must be human-authorized before any spend. NEVER auto-launch." },
  { id: "5.2", cls: "Agent52", slug: "social_publisher", layer: "layer5", phase: "03-production-distribution", del: "DEL-31", model_var: "model_routing", max_tokens: 3000, gate: "autonomous", block: "publish_log", name: "Social Publisher", reads: ["content_calendar","copy_assets","visual_assets"], raw: [], note: "Haiku, AUTONOMOUS. Platform-specific formatting + publish via Ayrshare (Buffer fallback) (ADR-04) → publish_log. gate_status='auto_approved'." },
  { id: "5.3", cls: "Agent53", slug: "lead_capture_nurture", layer: "layer5", phase: "03-production-distribution", del: "DEL-32", model_var: "model_routing", max_tokens: 4000, gate: "conditional", block: "lead_register", name: "Lead Capture + Nurture", reads: ["audience_segments","message_flows"], raw: ["inbound_leads"], note: "Haiku. Scores leads; hot→human, warm/cold→automated nurture. CRM sync HubSpot (ADR-04) → lead_register. CONDITIONAL gate: gate_status='auto_approved' but flag hot leads for human." },
  { id: "6.1", cls: "Agent61", slug: "performance_analytics", layer: "layer6", phase: "04-analytics-scale", del: "DEL-33", model_var: "model_primary", max_tokens: 8000, gate: "auto+alert", block: "performance_history", name: "Performance Analytics", reads: ["ad_campaign_log","publish_log","lead_register","active_strategy"], raw: [], note: "ROAS/CPL/CAC/CTR vs kpi_contracts (nested in active_strategy). → performance_history. Auto + alert triggers; gate_status='auto_approved', escalate on KPI breach." },
  { id: "6.2", cls: "Agent62", slug: "client_reporting", layer: "layer6", phase: "04-analytics-scale", del: "DEL-34", model_var: "model_primary", max_tokens: 12000, gate: "pre-client", block: "client_health_score", name: "Client Reporting", reads: ["performance_history","active_strategy","client_profile"], raw: [], note: "Monthly narrative ROI report (ES-MX, client-facing, per formatting-guide; NO COGS/margins) + client_health_score block. Pre-client-delivery gate: gate_status='pending_review'." },
  { id: "6.3", cls: "Agent63", slug: "optimization_engine", layer: "layer6", phase: "04-analytics-scale", del: "DEL-35", model_var: "model_primary", max_tokens: 8000, gate: "bounded-auto", block: "content_learnings", name: "Optimization Engine", reads: ["performance_history","content_learnings"], raw: [], note: "A/B auto; budget reallocation >20% requires human. Writes content_learnings (feedback loop → L3/L4). gate_status='auto_approved' for bounded actions, 'pending_review' for >20% reallocation." },
]

const COMMON = `You are a Product Agent Builder for the Acme Co. BU "Digital Marketing AI Suite".
Repo ROOT (use absolute paths with the file tools; the path has spaces — that is fine):
${ROOT}

STACK = single-vendor Google Cloud (ADR-04). NEVER reference the retired stack: n8n, CrewAI, Supabase, Pinecone/Weaviate/Qdrant, DALL-E/Midjourney/Pika, SendGrid-primary, Buffer-primary, consumer Claude Pro/Max. Use: Claude on Vertex AI, Cloud SQL+pgvector, Firestore, Pub/Sub, Cloud Run, fal.ai (Flux 2 Pro/Ideogram 3.0/Kling 2.5/Runway), Ayrshare, Resend, Twilio WhatsApp, HubSpot, Meta/Google/TikTok Ads.

READ THESE FIRST (they are the contract + the validated worked example you must mirror):
- project/specs/ARCHITECTURE.md — your agent's row: layer, job, human-gate tier, memory block read/written.
- project/specs/AGENT_COST_MODEL.md §2 + project/specs/agent_cost_model.py — your agent's cost row (READ ONLY — every one of the 19 rows already exists; transcribe the numbers into the spec, do NOT edit the model).
- suite/agents/base.py — the runner you build on (dataclass fields + run()/route()/split_outputs/extract_json/validate). DO NOT re-implement any of it.
- suite/agents/layer1/agent_1_1.py — reference CODE.
- suite/fixtures/1.1.txt — reference FIXTURE (canonical 3-output format; OUTPUT-1 is a JSON object in a triple-backtick json fence that is schema-valid). Mirror this format EXACTLY.
- phases/01-foundation/deliverables/DEL-17_client_profile_schema.json — reference SCHEMA (draft-07, confidence-metadata pattern).
- tests/agents/test_base_agent.py — reference TEST style (offline; inserts suite/ on sys.path).
- agents/_TEMPLATE_agent-spec.md — the spec format (§2 Cost & Runtime Profile is MANDATORY, decision D-07).
- For Layer 1 agents: phases/01-foundation/plan/layer1-data-requirements.md (the data design).
- For client-facing-content agents: brand/acme/guidelines/formatting-guide.md.

UNIVERSAL CONVENTIONS (every agent must obey — the orchestrator depends on them):
1. OUTPUT FORMAT: the system prompt instructs the model to emit EXACTLY three sections with the literal markers "## OUTPUT 1", "## OUTPUT 2", "## OUTPUT 3".
   - OUTPUT 1 = the structured memory-block payload, inside ONE triple-backtick json fence (open: three backticks + json + newline; close: newline + three backticks), and it MUST be a JSON OBJECT (never a bare array) with AT LEAST these top-level keys: "client_id" (string), "created_at" (ISO-8601 string), "gate_status" (string). Arrays go INSIDE the object (e.g. "segments": [...]).
   - OUTPUT 2 = human-readable narrative/brief for the operator or downstream creator.
   - OUTPUT 3 = ops / human-gate summary; for gated agents include the recommended action; the gate_status in OUTPUT-1 must match.
2. gate_status values: review-gated/binding/financial-auth/pre-client agents default to "pending_review"; autonomous/queue-mgr/bounded-auto routine actions use "auto_approved". (Schema enum should allow: pending_review, approved, returned, blocked, auto_approved.)
3. PAYLOAD CONTRACT for build_user_turn(payload): payload always has "client_id". The orchestrator injects each UPSTREAM memory block this agent READS under its block-name key (e.g. payload["client_profile"], payload["audience_segments"]). Raw onboarding inputs arrive under descriptive keys. Read everything with payload.get(...) and tolerate missing optional inputs. Truncate very large injected JSON (e.g. [:6000] chars) in the user turn.
4. The code module exposes a module-level AGENT instance and a def run(payload): return AGENT.run(payload). Set agent_id, prompt_asset, model, max_tokens, schema_name (== the block name), memory_block (== the block name). prompt_asset path is relative to suite/, i.e. "agents/<layer>/prompts/<slug>_system.txt". model = settings.<model_var>. Override route() ONLY if the agent needs extra routing beyond base (most do not).
5. SCHEMA: draft-07 JSON Schema at project/resources/schemas/<block>.json. Require client_id, created_at, gate_status + the 3-6 core domain fields with correct types. Keep it satisfiable (lenient on optional/nested fields; additionalProperties may be true). It MUST be a valid JSON Schema and MUST validate the fixture you write.
6. FIXTURE: suite/fixtures/<agent_id>.txt — a realistic, SCHEMA-VALID sample output for the Acme Co. pilot (client_id "acme-co", pre-launch GenAI BU selling the Suite to private-education SMBs in Mexico). Exact 3-output format from suite/fixtures/1.1.txt.
7. TESTS: tests/agents/test_<slug>.py — offline, self-contained (insert suite/ on sys.path exactly like test_base_agent.py). MUST include: (a) split_outputs(fixture) yields 3 sections; (b) extract_json(OUTPUT-1) is a dict with client_id; (c) the fixture's OUTPUT-1 validates against clients.load_schema("<block>") via jsonschema; (d) the schema itself passes jsonschema check_schema; (e) a mocked run(): monkeypatch AGENT.call to return the fixture and monkeypatch clients.write_memory_block / clients.add_review_doc / clients.publish, assert res.valid and the routed block name == "<block>". Use only pytest + jsonschema (both installed). Do NOT mutate global settings.
8. Language: English for prompt/spec/code/tests. Client-facing VALUES the agent emits follow ES-MX where the agent is client-facing (note it in the prompt).

You build ONE agent fully. Be concrete and production-grade — these prompts are the product IP. Do not leave TODOs in the prompt or code.`

phase('Author')

const AUTHORED = await pipeline(
  AGENTS,
  // Stage A — author all artifacts for one agent
  (a) => agent(
    `${COMMON}

=== YOUR AGENT: ${a.id} — ${a.name} (layer ${a.layer}, phase ${a.phase}) ===
Job (confirm against ARCHITECTURE.md): ${a.name}.
Human-gate tier: ${a.gate}. Memory block written: ${a.block}. Schema name + memory_block attr = "${a.block}".
Model: settings.${a.model_var}. max_tokens=${a.max_tokens}. Class name: ${a.cls}.
Upstream memory blocks it READS (orchestrator injects these under their block-name keys): ${JSON.stringify(a.reads)}.
Likely raw onboarding input keys: ${JSON.stringify(a.raw)}.
AGENT-SPECIFIC NOTE: ${a.note}

WRITE these files (absolute paths under ROOT). Use the file tools; create parent dirs as needed:
1. PROMPT ASSET: suite/agents/${a.layer}/prompts/${a.slug}_system.txt
   — the full production system prompt: role · context (4-market LATAM: MX/CO/DR/PR) · inputs · processing rules/steps · the three OUTPUTS · critical rules · exact output format. Concrete and detailed (Layer-1 intelligence agents ~200-400 lines like DEL-10/DEL-11; action/log agents can be shorter but complete).
2. SCHEMA: project/resources/schemas/${a.block}.json
3. CODE: suite/agents/${a.layer}/${a.slug}.py  (subclass BaseAgent; implement build_user_turn; module-level AGENT + run()).
4. FIXTURE: suite/fixtures/${a.id}.txt  (schema-valid, Acme Co. pilot, exact 3-output format).
5. TESTS: tests/agents/test_${a.slug}.py
6. SPEC: agents/${a.id}-${a.slug}.md  (from agents/_TEMPLATE_agent-spec.md; fill §2 Cost & Runtime Profile from AGENT_COST_MODEL.md row ${a.id}; Opus only if binding — justify).
7. DEL: phases/${a.phase}/deliverables/${a.del}_${a.slug}_system_prompt.md  — human-readable wrapper with project YAML front-matter (title/agent_id/date 2026-05-28/status draft/layer/audience internal/language en), the contract (reads/writes/gate), a pointer that the production prompt source-of-truth is the .txt asset, the OUTPUT-1 schema summary, and the critical rules. ${a.id === "1.2" ? "EXCEPTION for 1.2: DEL-11 already exists — UPDATE it (note the asset path + object-wrapper) rather than creating a new DEL file." : ""}

After writing, re-open each file you wrote and self-check: schema is valid JSON; fixture OUTPUT-1 parses and has client_id/created_at/gate_status and validates against the schema; code matches base.py's API; test imports resolve offline. Return STRICT JSON only: {"agent":"${a.id}","files":[...paths...],"block":"${a.block}","output1_top_keys":[...],"self_check":"pass|issues: ..."}`,
    { label: `author:${a.id}`, phase: 'Author' }
  ),
  // Stage B — independent adversarial review of that agent
  (authoredJson, a) => agent(
    `${COMMON}

You are the independent Deliverable Reviewer (agents/deliverable-reviewer.md) for agent ${a.id} — ${a.name}. The builder reported:
${authoredJson}

ADVERSARIALLY review by OPENING the actual files:
- suite/agents/${a.layer}/prompts/${a.slug}_system.txt
- project/resources/schemas/${a.block}.json
- suite/agents/${a.layer}/${a.slug}.py
- suite/fixtures/${a.id}.txt
- tests/agents/test_${a.slug}.py
- agents/${a.id}-${a.slug}.md
Checklist: (a) CONTRACT FIT vs ARCHITECTURE.md (right job, gate tier ${a.gate}, writes ${a.block}); (b) the schema is a valid draft-07 schema AND the fixture's OUTPUT-1 actually validates against it (mentally trace required fields/types — be strict); (c) OUTPUT-1 is a JSON OBJECT with client_id/created_at/gate_status and uses the three "## OUTPUT n" markers and a single triple-backtick json fence; (d) CODE correctly subclasses BaseAgent (schema_name==memory_block=="${a.block}", model=settings.${a.model_var}, exposes AGENT+run()), re-implements NOTHING from base.py; (e) TEST is offline/self-contained and would plausibly pass (incl. the fixture-validates-against-schema test); (f) §2 Cost & Runtime Profile present and consistent with AGENT_COST_MODEL.md (Opus only for 2.1); (g) NO retired-stack terms. If you find a fixable defect, FIX IT directly in the file (you have edit tools), then report it. Return the structured verdict.`,
    { label: `review:${a.id}`, phase: 'Review', schema: {
      type: "object", additionalProperties: false,
      properties: {
        agent: { type: "string" },
        verdict: { type: "string", enum: ["ship", "ship-with-fixes", "rework"] },
        fixed: { type: "array", items: { type: "string" } },
        must_fix: { type: "array", items: { type: "string" } },
        schema_valid: { type: "boolean" },
        fixture_validates: { type: "boolean" },
        code_correct: { type: "boolean" },
        tests_offline: { type: "boolean" },
        cost_profile_ok: { type: "boolean" },
        stack_currency_ok: { type: "boolean" },
        notes: { type: "string" }
      },
      required: ["agent","verdict","fixed","must_fix","schema_valid","fixture_validates","code_correct","tests_offline","cost_profile_ok","stack_currency_ok","notes"]
    } }
  )
)

return {
  built: AGENTS.length,
  reviews: AUTHORED.filter(Boolean),
}
