# Phase 3 — Gemini Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `SUITE_LLM_PROVIDER=gemini` runs the full 19-agent pipeline on Vertex Gemini via `google-genai`, with tier-based model routing, transport retries with backoff, and per-call token/cost logging — validated by a live golden run.

**Architecture:** The BaseAgent text contract is untouched: agents keep emitting `## OUTPUT 1/2/3` + fenced JSON (the schema skeleton is already embedded in every system prompt), so the Gemini path is text-mode generation with `system_instruction` — NOT `response_schema` JSON mode, which would break outputs 2/3. Agent modules keep declaring Claude model ids; `llm_complete` maps id → tier → Gemini model when the provider is `gemini`.

**Tech Stack:** `google-genai` (Vertex backend, ADC), tenacity-style manual backoff (no new dep).

**Spec:** `ROADMAP.md` Phase 3.

## Global Constraints

- Never Gemini 2.5 (retires Oct 2026). Tiers: primary `gemini-3.7-flash`, routing `gemini-3.5-flash-lite`, deep `gemini-3.1-pro-preview` (env-overridable).
- All SDK imports lazy; 214 offline tests keep passing; new tests are offline (fake genai client).
- Retry only transient transport errors (429/5xx/connection), max 3 attempts, exponential backoff; schema-failure retry stays BaseAgent's job.

---

### Task 1: config + provider (test-first)

**Files:**
- Create: `tests/infra/test_gemini_provider.py`
- Modify: `suite/infra/config.py` (gemini tier models, `vertex_gemini_location`), `suite/infra/clients.py` (`_genai_client()`, `_gemini_model_for()`, gemini branch in `llm_complete` with `_gemini_generate()` retry loop + usage logging), `pyproject.toml` (+`google-genai>=1.0`)

**Interfaces:**
- Produces: `settings.gemini_model_primary|routing|deep` (env `GEMINI_MODEL_*`), `settings.vertex_gemini_location` (env `VERTEX_GEMINI_LOCATION`, default `global`); `clients._gemini_model_for(claude_model_id) -> str`; gemini branch returns `response.text` and logs `usage_metadata` token counts at INFO.

- [x] Step 1: Failing tests — tier mapping (primary/routing/deep/unknown→primary); fake client receives `system_instruction` + `max_output_tokens`; transient 429 then success → retried; non-transient error raises immediately; usage logged.
- [x] Step 2: Implement; `uv sync`; suite green (214 + new).
- [x] Step 3: Commit.

### Task 2: Live golden run (exit criterion)

- [x] Step 1: Single-agent live check (agent 1.1) with `SUITE_LLM_PROVIDER=gemini SUITE_BACKEND=memory`.
- [x] Step 2: Full pipeline live golden run; record agents-valid count and total tokens/cost estimate in the plan.
- [x] Step 3: ROADMAP Phase 3 ✅ + commit + push.

## Golden run result (2026-08-19)

Live `gemini` provider, memory backend, AUTO_APPROVE: **19/19 agents valid**, all
20 blocks produced. 23 LLM calls (4 feedback retries, all recovered — zero final
invalid outputs; the pre-fix run died on enum drift at agent 1.1).
Tokens: 388,659 in / 126,910 out ≈ **$0.77/run** at gemini-3.7-flash intro pricing.
