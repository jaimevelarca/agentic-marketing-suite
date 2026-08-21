# Sesión 2026-08-21 — Fase 6b: CI/CD, Direct Cloud Run IAP y Stack Prod

**Objetivo:** Implementar la Fase 6b completa de acuerdo con las decisiones de arquitectura del log `2026-08-19_fase-6b-diseno.md`:
1. Workload Identity Federation (WIF) para GitHub Actions con cero secretos en GitHub.
2. Direct Cloud Run IAP frente a la consola (`js@qhhe.net`), conservando el login de Django como segundo factor y proveedor de sesión/auditoría.
3. Aislamiento de `prod` en proyecto dedicado `agentic-marketing-suite-prod` (folder QHHE `274831265727`).
4. Pipeline de promoción inmutable: tags git `v*` promueven el mismo digest probado en `dev`.
5. Compuerta de humo automatizada (`scripts/smoke_check.py`) con rollback de Pulumi en fallo.

---

## Resultados y Cambios Implementados

1. **Infraestructura (`infra/`):**
   - Refactorizado [`infra/__main__.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/infra/__main__.py) para soportar stacks multi-proyecto (`dev` y `prod`).
   - Habilitado Direct Cloud Run IAP (`iap_enabled=True`) sobre el servicio `console`. Retirado el invoker `allUsers` y vinculado `serviceAccount:service-{PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com` como `roles/run.invoker` y `user:js@qhhe.net` como `roles/iap.httpsResourceAccessor`.
   - Creado Workload Identity Pool `github-actions` y Provider OIDC con restricción de repositorio en `dev` y repositorio + tag `refs/tags/v*` en `prod`.
   - Creada Service Account `pulumi-deployer` con IAM de despliegue y acceso al bucket de estado `gs://agentic-marketing-suite-pulumi-state`.
   - Contenedor de secreto `pulumi-passphrase` en Secret Manager administrado por Pulumi (la versión se siembra fuera de banda desde el vault).
   - Creado [`infra/Pulumi.prod.yaml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/infra/Pulumi.prod.yaml) y actualizado [`infra/Pulumi.dev.yaml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/infra/Pulumi.dev.yaml).

2. **Imágenes y Cloud Build:**
   - Retirado el tag `:latest` de [`deploy/cloudbuild.yaml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/deploy/cloudbuild.yaml) y [`web/cloudbuild.yaml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/web/cloudbuild.yaml); se fijan por SHA corto y se promueven por digest `sha256:...`.

3. **Compuerta de Humo (`scripts/`):**
   - Creado [`scripts/smoke_check.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/scripts/smoke_check.py) verificando:
     (a) Redirección HTTP 302 a `accounts.google.com` (valida liveness + IAP activo).
     (b) Corrida de Job `suite-orchestrator` con `SUITE_LLM_PROVIDER=fixture` (19/19 agentes, salida 0, cero costo Gemini).
     (c) Comparación de digest de imágenes desplegadas.

4. **Workflows GitHub Actions (`.github/workflows/`):**
   - [`.github/workflows/pr-check.yml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/.github/workflows/pr-check.yml): Tests offline + `pulumi preview` en `dev`.
   - [`.github/workflows/ci-dev.yml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/.github/workflows/ci-dev.yml): Push a `main` corre tests, construye imágenes con commit SHA, actualiza `dev` con `pulumi up` y corre `smoke_check.py`.
   - [`.github/workflows/promote-prod.yml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/.github/workflows/promote-prod.yml): Tag `v*` resuelve digests probados en `dev`, ejecuta `pulumi up --stack prod`, corre `smoke_check.py` y aplica rollback atómico en caso de fallo.

5. **Pruebas Offline:**
   - Creado [`tests/scripts/test_smoke_check.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/scripts/test_smoke_check.py) (16 tests).
   - Creado [`tests/infra/test_workflow_security.py`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/tests/infra/test_workflow_security.py) (7 tests).
   - **Total de pruebas en verde: 257** (todas offline vía `uv run pytest -q`).

6. **Documentación:**
   - Actualizado [`ROADMAP.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/ROADMAP.md) (Fase 6b ✅).
   - Actualizado [`AGENTS.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/AGENTS.md).
   - Actualizado [`infra/README.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/infra/README.md).
   - Actualizado [`docs/superpowers/plans/2026-08-21-phase-6b-cicd-prod.md`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/docs/superpowers/plans/2026-08-21-phase-6b-cicd-prod.md).
