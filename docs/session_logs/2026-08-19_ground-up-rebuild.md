# Sesión 2026-08-19 — Ground-up rebuild: fases 0–6a, app en vivo

**Objetivo:** revisar el baseline `ai-marketing-suite`, trazar el roadmap a
producción (Pulumi + ADK + Gemini + Firestore + Django) y desplegar una app real
en el nuevo project GCP — todo autorizado por Jaime para ejecución autónoma.

## Resultados

- **Review + roadmap** — `docs/REVIEW-2026-08-19.md` + `ROADMAP.md` (decisiones de
  stack verificadas contra docs de agosto 2026); artefacto publicado:
  https://claude.ai/code/artifact/7a55382c-0bef-4fe4-9371-a9e88df21a66
- **Infra fuera del repo:** project GCP `agentic-marketing-suite` creado en el
  folder QHHE (274831265727), billing `01624A-839C44-1DB4D6` enlazado; project
  `ai-mkt-suite` borrado (recuperable ~30 días). Repo privado
  `jaimevelarca/agentic-marketing-suite` creado desde el baseline `a65f48e`.
- **Fases ejecutadas (commits `3e27c95..bf9d1e7`, exit proofs en
  `docs/superpowers/plans/`):**
  - F0 higiene (`3e27c95`) · F1 Pulumi ~50 recursos (`25c1193`) ·
    F2 Firestore + máquina de compuertas (`61c9c62..940e1a7`) ·
    F3 proveedor Gemini, corrida dorada 19/19 ≈ USD 0.77 (`c5973fa..6207d2b`) ·
    F4 workflow ADK 2.7.1 con pausa/reanudación entre procesos (`adafbed..399ac5d`) ·
    F5 consola Django probada de punta a punta (`af4c47b..9359a4a`) ·
    F6a despliegue real (`73bb80b..bf9d1e7`).
- **App en vivo:** https://console-54069477296.us-central1.run.app (usuario
  `jaime`; contraseña en Secret Manager `django-admin-password`). Job
  `suite-orchestrator` corrió el workflow completo en GCP (19/19).
- **Bugs reales encontrados y corregidos por las pruebas en vivo:** deriva de
  enums de Gemini → reintento con retroalimentación del error (`e1603ac`);
  secuestro de client_id por el JSON de entrada (`5982730`); doble reanudación
  por pausa detectada de estado viejo (mismo commit); `.gcloudignore` sin
  anclar excluyó `suite/infra` de la imagen (`73bb80b`).
- Pruebas: **234 en verde** (207 del baseline + 27 nuevas), todas fuera de línea.

## Archivos tocados (por área)

- `suite/`: `infra/{clients,config,log,adk_sessions}.py`,
  `orchestration/{adk_workflow,adk_entrypoint,pipeline}.py`, `agents/base.py`
- `web/`: proyecto Django completo (core, console, templates, Dockerfile)
- `infra/`: programa Pulumi completo (stack `dev`, estado en GCS)
- `deploy/`: Dockerfile + cloudbuild reescritos; Cloud Workflows legado borrado
- `tests/`: `infra/`, `orchestration/`, `web/` nuevos
- Docs: `ROADMAP.md`, `docs/REVIEW-2026-08-19.md`, planes por fase, READMEs

## Pendientes conocidos

1. **F6b** — GitHub Actions (WIF) build+deploy, stack `prod`, IAP frente a la
   consola, tags de imagen fijados por commit en Pulumi (hoy `:latest` + roll
   manual). Sin decisiones pendientes de Jaime.
2. **F7** — registro en Gemini Enterprise: **decisión de Jaime** (edición;
   pay-as-you-go propuesta).
3. **F8** — integraciones reales de canal: **decisión de Jaime** (orden;
   Meta Ads + Resend propuesto).
4. Menores: costo fijo nuevo (Cloud SQL micro ≈ USD 9/mes); recarga necesaria
   tras reanudar en la consola (pausa/estado en dos escrituras); corridas
   largas de Gemini desde la consola pueden morir por escalado a cero —
   preferir el Job.

## Punto de entrada de la siguiente sesión

Leer `ROADMAP.md` (fases ✅ hasta 6a) y arrancar **F6b** con un plan en
`docs/superpowers/plans/` — no se necesita input humano para 6b.
