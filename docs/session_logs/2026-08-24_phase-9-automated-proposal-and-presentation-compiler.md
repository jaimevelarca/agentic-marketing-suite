# Sesión 2026-08-24 — Fase 9: Motor Automatizado de Propuestas y Compilador de Presentaciones

**Objetivo:** Implementar el motor de renderizado de entregables y compilación automatizada de propuestas comerciales (`suite/rendering/`):
1. Compilador de Presentación Interactiva en 9 Actos (`presentation_compiler.py`): genera un documento HTML standalone, responsivo y autocontenido con narrativa de 9 actos, contadores animados (`IntersectionObserver`), matriz 2x2 de posicionamiento competitivo, muestras de copys y especificaciones visuales, y checklist de compuertas humanas.
2. Compilador de Anexo Ejecutivo / Reporte PDF (`detail_compiler.py`): genera un dossier exhaustivo con tablas de los 19 agentes, demografía y firmografía de ICPs, contratos de KPI, catálogo de textos, prompts y flujos de correo, con optimización `@media print`.
3. Sistema de Tematización e Inyección de Marca (`theme.py`): validación estricta de `theme.toml` o derivación dinámica desde `client_profile`, con el color de acento `#1ebe82` estrictamente reservado para decisiones/compuertas humanas.
4. Enrutamiento y Generación Visual (`engines.py`, `prompts.py`, `vertex.py`, `renderer.py`, `service.py`): enrutamiento inteligente entre `gemini-3.1-flash-image` (imágenes fotorrealistas sin texto) y `gemini-3.1-pro-preview` (textos en imagen y carruseles), con `StubRenderer` para ejecución 100% offline sin costo ni dependencias de red.
5. Integración con Django Review Console (`web/console/`): endpoints y vistas `/propuestas/<client_id>/<doc_type>/` para previsualización directa y descarga de archivos HTML autónomos, más acciones en las plantillas de sesión.
6. Integración con Vertex AI Reasoning Engine (`suite/reasoning_engine/`): herramienta `compile_client_proposal` registrada en `TOOLS` y ruteo de lenguaje natural.
7. Pruebas unitarias offline (24 pruebas nuevas, suite completa con 313 pruebas pasando en verde).

---

## 1. Módulos y Cambios Implementados

1. **Núcleo de Renderizado (`suite/rendering/`):**
   - [`suite/rendering/theme.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/theme.py):
     - `Theme` dataclass y validador de `theme.toml`.
     - `derive_theme_from_profile(profile, client_id)`: derivación automática de paleta, tipografías y logo desde el bloque de memoria `client_profile`.
     - `theme_css(theme)`: genera variables CSS `:root` y reglas `@font-face`.
     - Garantía de color: acento `#1ebe82` reservado exclusivamente para compuertas humanas.
   - [`suite/rendering/engines.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/engines.py):
     - `tier_for(asset)`: ruteo automático a Flash vs Pro.
     - `engine_label(asset)` y `label_for_model(model)`: etiquetas en español es-MX (*Nano Banana* / *Nano Banana Pro*).
     - `estimate(assets)`: cálculo estimado de costos en USD.
   - [`suite/rendering/prompts.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/prompts.py):
     - `build_prompt(asset)`: ensamblado de prompt en inglés, exclusiones negativas, relación de aspecto, texto en español en imagen y directiva anti-letterbox *full-bleed*.
     - `build_slide_prompt(asset, slide)`: prompts específicos para diapositivas de carrusel.
   - [`suite/rendering/vertex.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/vertex.py):
     - `generate(client, model, prompt, aspect)`: llamada resiliente a Vertex AI con variantes de configuración y extractor de bytes de imagen.
   - [`suite/rendering/renderer.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/renderer.py):
     - `Renderer` Protocol, `StubRenderer` (placeholder offline seguro) y `VertexRenderer` (Vertex AI en vivo).
   - [`suite/rendering/service.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/service.py):
     - `render_asset(asset)` y `render_slide(asset, slide)` con captura controlada de errores en `RenderResult`.
   - [`suite/rendering/presentation_compiler.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/presentation_compiler.py):
     - `compile_presentation_deck(client_id, memory_blocks, theme)`: compilador interactivo de 9 actos.
   - [`suite/rendering/detail_compiler.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/detail_compiler.py):
     - `compile_detail_report(client_id, memory_blocks, theme)`: compilador del anexo de detalle ejecutivo / reporte imprimible a PDF.
   - [`suite/rendering/compiler.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/rendering/compiler.py):
     - `compile_proposal(client_id, memory_blocks, theme, out_dir)`: fachada de compilación y exportación de archivos a disco.

2. **Consola Django (`web/console/`):**
   - [`web/console/services.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/web/console/services.py):
     - Funciones `get_client_proposal(client_id, doc_type)` y `compile_and_export_proposal(client_id)`.
   - [`web/console/views.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/web/console/views.py) & [`web/console/urls.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/web/console/urls.py):
     - `proposal_view`: renderiza el HTML standalone en el navegador.
     - `proposal_download`: descarga el archivo HTML como adjunto.
     - `proposal_generate`: compila y almacena la propuesta en `exports/proposals/<client_id>/`.
   - [`web/templates/sesion.html`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/web/templates/sesion.html):
     - Botones de acción integrados para ver y descargar la presentación en 9 actos y el anexo de detalle.

3. **Vertex AI Reasoning Engine (`suite/reasoning_engine/`):**
   - [`suite/reasoning_engine/tools.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/reasoning_engine/tools.py):
     - Herramienta `compile_client_proposal(client_id, format)` registrada en `TOOLS`.
   - [`suite/reasoning_engine/engine.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/suite/reasoning_engine/engine.py):
     - Ruteo por palabras clave ("propuesta", "presentación", "deck", "anexo") y síntesis estructurada.

4. **Pruebas Offline:**
   - [`tests/rendering/test_theme.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/rendering/test_theme.py) (6 tests).
   - [`tests/rendering/test_engines.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/rendering/test_engines.py) (6 tests).
   - [`tests/rendering/test_presentation_compiler.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/rendering/test_presentation_compiler.py) (2 tests).
   - [`tests/rendering/test_detail_compiler.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/rendering/test_detail_compiler.py) (2 tests).
   - [`tests/web/test_console_proposals.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/web/test_console_proposals.py) (5 tests).
   - [`tests/reasoning_engine/test_proposal_tool.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/reasoning_engine/test_proposal_tool.py) (2 tests).
   - **Total de pruebas en el repositorio: 313 passed** (0 fallos, 5.53s).

5. **Documentación:**
   - Actualizado [`ROADMAP.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/ROADMAP.md) (Fase 9 ✅).
   - Actualizado [`AGENTS.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/AGENTS.md) (313 tests).
   - Plan [`docs/superpowers/plans/2026-08-24-phase-9-automated-proposal-presentation-compiler.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/docs/superpowers/plans/2026-08-24-phase-9-automated-proposal-presentation-compiler.md) cerrado al 100%.

---

## 2. Estado Estratégico del Proyecto

Todas las fases del roadmap (0 a 9) están **100% completadas y verificadas**:
- **Fase 0:** Repo hygiene & truth ✅
- **Fase 1:** Pulumi foundation ✅
- **Fase 2:** Firestore data layer ✅
- **Fase 3:** Gemini Vertex provider ✅
- **Fase 4:** ADK 2.x orchestration & DAG ✅
- **Fase 5:** Django review & ops UI con Direct IAP ✅
- **Fase 6:** CI/CD & Prod Isolation (`agentic-marketing-suite-prod`) ✅
- **Prod Release:** `v0.1.0` en vivo ✅
- **Fase 7:** Gemini Enterprise Agent Platform Surface & Reasoning Engine ✅
- **Fase 8:** Integraciones reales de distribución (Meta Ads & Resend) con compuerta humana financiera `#1ebe82` ✅
- **Fase 9:** Compilador Automatizado de Propuestas Comerciales (Presentación 9 Actos + Anexo Detalle/PDF) ✅
