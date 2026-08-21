# agentic-marketing-suite — orientación para agentes

**Qué es:** el motor de marketing de QHHE (6 capas / 19 agentes,
`suite/orchestration/pipeline.py`), en reconstrucción ground-up hacia producción:
**Pulumi IaC · ADK 2.x + Gemini · Cloud Run · Firestore · Django (UI de revisión)**.
Sucesor de `ai-marketing-suite` (baseline importado en `a65f48e`; aquel repo queda
como archivo de referencia en `~/dev/qhhe/ai-marketing-suite`).

## Estado y mapa
- **Plan estratégico:** `ROADMAP.md` (fases 0–8, decisiones de stack verificadas
  2026-08-19). **Review del baseline:** `docs/REVIEW-2026-08-19.md`.
- **Planes por fase:** `docs/superpowers/plans/` (uno por fase al arrancarla).
- Al cerrar sesión que cambie el estado del proyecto: actualizar ROADMAP (marcar
  fase/exit) y dejar nota de sesión en `docs/session_logs/AAAA-MM-DD_<tema>.md`.

## GCP / identidad
- Projects: **`agentic-marketing-suite`** (`dev`) and **`agentic-marketing-suite-prod`** (`prod`), both under folder QHHE `274831265727`, billing `01624A-839C44-1DB4D6`. Identidad: `dispatcher switch qhhe` (js@qhhe.net).
- IaC con **Pulumi (Python)** en `infra/` (stacks `dev` and `prod`, state bucket `gs://agentic-marketing-suite-pulumi-state`, documented in `infra/README.md`).

## Convenciones duras
- **uv + Python 3.12**, venv del proyecto (`uv sync`); repo vive en `~/dev`
  (NUNCA en Drive). Tests offline siempre verdes: `python -m pytest -q` (207).
- **Secretos:** local → vault `~/.agent_dispatcher/`; nube → Secret Manager.
  Jamás en el repo ni en `.env` dentro del repo.
- **Datos de cliente:** jamás commiteados (el baseline traía
  `alonso-y-cia.json`; se retiró en Fase 0 — el archivo vive en el repo baseline).
- **Compuerta humana sagrada:** nada se publica ni gasta sin aprobación; verde
  `#1ebe82` reservado a compuertas humanas en cualquier UI.
- **Cliente-facing:** español es-MX profesional, sin anglicismos.
- Defaults de runtime **offline** (`fixture`/`memory`); producción es opt-in
  explícito por env.
