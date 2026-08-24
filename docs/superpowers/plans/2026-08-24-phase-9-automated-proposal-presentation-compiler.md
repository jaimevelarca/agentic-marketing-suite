# Phase 9 — Automated Proposal & Presentation Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the automated **Deliverables & Presentation Rendering Engine** (`suite/rendering/`) to compile Firestore Native memory blocks into an interactive, responsive, standalone **9-Act HTML Presentation Deck** and an executive **Detail / PDF Report Annex**, complete with theme injection (`theme.toml`), visual asset rendering specs, and one-click integration across the Django review console and Vertex AI Reasoning Engine.

---

## Architectural Context & Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Storytelling Structure** | **9-Act Presentation Deck** (`presentation_compiler.py`) | Proven structure from client proposals (`alonsoycia-plan`, `ceneval-plan`, `u-storage-plan`): Act 0 Portada/Cifras, Act 1 El Cliente, Act 2 Audiencias (ICPs), Act 3 Posicionamiento Competitivo (2x2), Act 4 Estrategia & Presupuesto, Act 5 Calendario & Campañas, Act 6 Piezas Reales (Copy/Visual/Email), Act 7 Qué falta revisar (Compuertas), Act 8 Decisión & Cierre. |
| **Document Delivery** | **Single Standalone HTML** (Zero external runtime dependencies) | Standalone distribution without external script/font CDNs: inlined CSS custom properties, responsive grid, reveal-on-scroll animations (`IntersectionObserver`), dynamic counters, keyboard paging (`ArrowRight`/`ArrowLeft`), and embedded base64 SVG/PNG brand assets. |
| **Executive Annex** | **Executive Detail / PDF Report** (`detail_compiler.py`) | Comprehensive multi-section dossier with `@media print` styling for browser viewing and direct PDF generation (full ICP cards, competitive matrix, campaign registry, all 4-week calendar slots, complete copy asset register, visual creative prompts/engine routing, and email nurture flows). |
| **Theming System** | **`theme.toml` & Dynamic Profile Theme** (`theme.py`) | Strict QHHE palette guidelines: `--primary` brand color, `--accent` fixed to `#1ebe82` (strictly reserved for human gate and operator approvals), `--accent-soft`, `--gray`, `--bg-alt`, `--ink`, `--danger`, typography tokens, logo handling, and provenance tagging (`[confirmado]`, `[propuesto]`, `[inferido]`). |
| **Image Engine Routing** | **Flash vs. Pro Tier Routing** (`engines.py` & `prompts.py`) | Text-heavy assets / carousels routed to Pro image models (`gemini-3.1-pro-preview` / Nano Banana Pro); photoreal images without text routed to Flash (`gemini-3.1-flash-image` / Nano Banana). Includes `StubRenderer` for zero-cost offline generation and `VertexRenderer` for live generation. |
| **Console & Reasoning Engine Integration** | **One-Click Endpoints & Reasoning Engine Tool** | Integrated into Django review console (`/propuestas/<client_id>/<doc_type>/` and `/propuestas/<client_id>/generar/`) and Vertex AI Reasoning Engine (`compile_client_proposal` tool). |
| **Testing Contract** | **289 existing tests remain 100% green** + new rendering tests | All generation, compilation, theming, and endpoint tests run 100% offline without live GCP or API keys. |

---

## Tasks Breakdown

### Task 1: Rendering Core & Theming System (`suite/rendering/`)

**Files:**
- Create: `suite/rendering/__init__.py`
- Create: `suite/rendering/theme.py`
- Create: `suite/rendering/engines.py`
- Create: `suite/rendering/prompts.py`
- Create: `suite/rendering/vertex.py`
- Create: `suite/rendering/renderer.py`
- Create: `suite/rendering/service.py`

**Objective:**
Establish the core rendering framework: theme parsing and validation (`theme.toml`), brand color injection, model routing (Flash/Pro image tiers), prompt compilation with Spanish in-image text rules, and renderer strategies (safe offline `StubRenderer` + live `VertexRenderer`).

- [x] **Step 1.1:** Implement `suite/rendering/theme.py`:
  - `Theme` dataclass / dictionary validator:
    - Required metadata: `name`, `tagline`, `footer_text`, `logo`.
    - Required colors: `primary`, `accent` (enforces `#1ebe82` reserved for human gate), `accent_soft`, `gray`, `bg_alt`, `ink`, `danger`.
    - Font configuration: `family`, `regular_woff2`, `bold_woff2`.
  - `load_theme(path_or_dict)`: loads and validates `theme.toml` or generates default theme from `client_profile` / brand tokens.
  - `theme_css(theme: dict)`: generates CSS variables `:root { ... }` and font styles.
- [x] **Step 1.2:** Implement `suite/rendering/engines.py`:
  - Model constants: `FLASH_MODEL`, `PRO_MODEL`, `PRICE` estimates.
  - `tier_for(asset: dict) -> str`: routes assets with `in_image_text` or `carousel` to Pro; otherwise Flash.
  - `label_for_model(model: str) -> str` & `engine_label(asset: dict) -> str` (es-MX labels).
  - `estimate(assets: list[dict]) -> float`: calculates estimated render cost in USD.
- [x] **Step 1.3:** Implement `suite/rendering/prompts.py`:
  - `build_prompt(asset: dict) -> str`: compiles English prompt, Spanish in-image text directive, negative exclusions, aspect ratio, and full-bleed directives.
  - `build_slide_prompt(asset: dict, slide: dict) -> str`: compiles single-slide carousel prompts.
- [x] **Step 1.4:** Implement `suite/rendering/vertex.py`:
  - Lazy `google.genai` Vertex AI caller with fallback configuration attempts (`types.GenerateContentConfig` variants) and image byte extractor.
- [x] **Step 1.5:** Implement `suite/rendering/renderer.py`:
  - `Renderer` protocol contract.
  - `StubRenderer`: offline image generator creating lightweight SVG/PNG placeholder data with zero cost or network.
  - `VertexRenderer`: Vertex AI Nano Banana generator.
  - `get_renderer(provider=None)`: safe default to `StubRenderer` when offline.
- [x] **Step 1.6:** Implement `suite/rendering/service.py`:
  - `RenderResult` dataclass.
  - `render_asset(asset, renderer=None) -> RenderResult`.
  - `render_slide(asset, slide, renderer=None) -> RenderResult`.

---

### Task 2: Presentation Deck Compiler — 9-Act Structure (`suite/rendering/presentation_compiler.py`)

**Files:**
- Create: `suite/rendering/presentation_compiler.py`

**Objective:**
Compile Firestore memory blocks into a standalone, interactive, responsive HTML presentation deck implementing the 9-act storytelling arc with bundled CSS and JS.

- [x] **Step 2.1:** Implement memory block ingestion and normalization helper:
  - Ingests `client_profile`, `audience_segments`, `competitive_map`, `active_strategy`, `campaign_registry`, `content_calendar`, `copy_assets`, `visual_assets`, `message_flows`, `approval_log`.
  - Gracefully handles missing blocks or draft states with sensible defaults and `[propuesto]` / `[inferido]` provenance tags.
- [x] **Step 2.2:** Build the 9-Act HTML Generator:
  - **Acto 0 (Portada):** Headline, lead subtitle, dynamic metric counters (agentes en cadena, entregables, publicaciones, campañas, días de ciclo).
  - **Acto 1 (El Cliente):** Business synthesis, corporate quote (USP), cycle objectives, prioritized target markets.
  - **Acto 2 (Audiencias / ICPs):** 3 ICP segment cards (role, pain points, motivations, preferred channels).
  - **Acto 3 (Posicionamiento Competitivo):** 2x2 competitive quadrant matrix (axes, 4 styled quadrants, quadrant legend, client differentiator quote).
  - **Acto 4 (La Estrategia):** Strategic thesis, prioritized channel mix (1..N badges), 4 messaging pillars, monthly and 90-day budget breakdown.
  - **Acto 5 (El Calendario):** Cycle overview, active campaigns grid, sample schedule table (week, channel, piece, CTA).
  - **Acto 6 (Las Piezas Reales):** Produced copy artifacts (LinkedIn/Google/Meta), image prompt specification snippet, email nurture sequence flow card.
  - **Acto 7 (Qué Falta Revisar):** 6-point checklist of human decisions with status badges (`confirmar`, `unificar`, `validar`, `entregar marca`), highlighting that `#1ebe82` human gate approval is required before publication.
  - **Acto 8 (La Decisión & Cierre):** 3 concrete launch decisions, human review sign-off footer.
- [x] **Step 2.3:** Build standalone bundler:
  - Inlines CSS with CSS custom properties, responsive layout, dark/light contrast rules, and reduced motion queries.
  - Inlines JS for scroll progress bar, reveal-on-scroll `IntersectionObserver`, animated number counters, and keyboard navigation (`ArrowRight`/`ArrowLeft`/`PageDown`/`PageUp`).
  - Bundles logo and SVG icons.

---

### Task 3: Executive Detail / PDF Report Compiler (`suite/rendering/detail_compiler.py`)

**Files:**
- Create: `suite/rendering/detail_compiler.py`

**Objective:**
Compile comprehensive client memory blocks into an executive detail annex formatted for web viewing and `@media print` PDF generation.

- [x] **Step 3.1:** Implement `compile_detail_report(client_id, blocks=None, theme=None) -> str`:
  - Document header with client metadata, timestamp, confidentiality notice, and human gate status.
  - **Sección 1:** Diagnóstico Empresarial & Perfil de Cliente (lines of service, value props, target geographies, budget).
  - **Sección 2:** Segmentación de Audiencias & ICPs (detailed cards with demographics, firmographics, buying dynamics, pain points, objection handling, conversion likelihood).
  - **Sección 3:** Mapa Competitivo & Posicionamiento (competitor profiles, content gaps, 2x2 matrix, strategic differentiator).
  - **Sección 4:** Estrategia de Marketing & Contratos de KPI (thesis, channel allocation, budget breakdown, primary/secondary KPI metrics).
  - **Sección 5:** Registro de Campañas & Calendario de Contenidos (all campaigns and complete 4-week slot matrix).
  - **Sección 6:** Catálogo Completo de Entregables Creativos:
    - Copy assets (channel, format, headline/hook, body text, CTA).
    - Visual assets specifications (aspect ratio, engine label, prompt in English, Spanish translation, in-image text, negative prompt).
    - Email & messaging sequences (triggers, step-by-step emails with subjects, timing delays, and goals).
  - **Sección 7:** Bitácora de Compuertas Humanas & Gobernanza (block approval states, audit trail, sign-off status).
- [x] **Step 3.2:** Build high-level compilation facade in `suite/rendering/compiler.py`:
  - `compile_proposal(client_id, theme=None, out_dir=None) -> dict[str, Path | str]`: builds both the deck and detail report and optionally writes to `exports/proposals/<client_id>/`.

---

### Task 4: Console & Reasoning Engine Integration

**Files:**
- Modify: `web/console/services.py`
- Modify: `web/console/views.py`
- Modify: `web/console/urls.py`
- Modify: `web/templates/sesion.html`
- Modify: `web/templates/panel.html`
- Modify: `suite/reasoning_engine/tools.py`
- Modify: `suite/reasoning_engine/engine.py`

**Objective:**
Connect the presentation and detail compilers into the Django review console for one-click browser preview and download, and expose the compiler as a structured tool in the Vertex AI Reasoning Engine.

- [x] **Step 4.1:** Add proposal services to `web/console/services.py`:
  - `get_client_proposal_html(client_id: str, doc_type: str = "deck") -> str`
  - `export_client_proposal(client_id: str) -> dict[str, str]`
- [x] **Step 4.2:** Add proposal views and URL routes in `web/console/views.py` & `web/console/urls.py`:
  - `proposal_view(request, client_id, doc_type="deck"|"detail")`: render full-page standalone HTML in browser.
  - `proposal_download(request, client_id, doc_type="deck"|"detail")`: return attachment response for file download.
  - `proposal_generate(request, client_id)`: trigger generation action from console.
- [x] **Step 4.3:** Update Django templates (`web/templates/sesion.html` and `web/templates/panel.html`):
  - Add action buttons: "Ver Presentación Interactiva", "Ver Anexo de Detalle", "Descargar HTML".
- [x] **Step 4.4:** Wire tool into `suite/reasoning_engine/tools.py` & `suite/reasoning_engine/engine.py`:
  - Implement `compile_client_proposal(client_id: str, format: str = "both") -> dict[str, Any]` tool in `tools.py`.
  - Register `compile_client_proposal` in `TOOLS` array.
  - Update system prompt instructions in `engine.py` to support proposal compilation queries.

---

### Task 5: Comprehensive Offline Unit Tests (`tests/rendering/`, `tests/web/`, `tests/reasoning_engine/`)

**Files:**
- Create: `tests/rendering/__init__.py`
- Create: `tests/rendering/test_theme.py`
- Create: `tests/rendering/test_engines.py`
- Create: `tests/rendering/test_prompts.py`
- Create: `tests/rendering/test_presentation_compiler.py`
- Create: `tests/rendering/test_detail_compiler.py`
- Create: `tests/rendering/test_compiler.py`
- Create: `tests/web/test_console_proposals.py`
- Create: `tests/reasoning_engine/test_proposal_tool.py`

**Objective:**
Author exhaustive offline tests covering theme validation, engine routing, prompt assembly, 9-act presentation compilation, detail report compilation, Django console views/downloads, and reasoning engine tool execution.

- [x] **Step 5.1:** Author `test_theme.py` (validates theme parsing, missing field checks, CSS variable generation).
- [x] **Step 5.2:** Author `test_engines.py` & `test_prompts.py` (validates Flash/Pro routing, prompt formatting, pricing estimates).
- [x] **Step 5.3:** Author `test_presentation_compiler.py` (tests 9-act generation against fixture memory blocks, verifying all acts, metric counts, positioning quadrant, copy snippets, and checklist).
- [x] **Step 5.4:** Author `test_detail_compiler.py` (tests executive detail generation, section tables, copy registers, visual specifications, print CSS).
- [x] **Step 5.5:** Author `test_compiler.py` (tests full export workflow and file writing).
- [x] **Step 5.6:** Author `test_console_proposals.py` (tests Django proposal preview, download, and generation endpoints).
- [x] **Step 5.7:** Author `test_proposal_tool.py` (tests reasoning engine tool execution and response structure).
- [x] **Step 5.8:** Run `uv run --all-extras pytest -q` ensuring all 289 existing tests + all new tests pass 100% green.

---

### Task 6: Documentation & Roadmap Closeout

**Files:**
- Modify: `ROADMAP.md`
- Modify: `AGENTS.md`
- Create: `docs/session_logs/2026-08-24_phase-9-automated-proposal-and-presentation-compiler.md`

**Objective:**
Document Phase 9 deliverables, update the strategic roadmap, and log the session.

- [x] **Step 6.1:** Update `ROADMAP.md` marking Phase 9 complete.
- [x] **Step 6.2:** Update `AGENTS.md` with final test count and rendering capabilities.
- [x] **Step 6.3:** Author session log `docs/session_logs/2026-08-24_phase-9-automated-proposal-and-presentation-compiler.md`.
- [x] **Step 6.4:** Run final test verification (`uv run --all-extras pytest -q`).
