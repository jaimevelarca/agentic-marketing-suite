# Sesión 2026-08-22 — Bootstrap de Prod y Primer Release v0.1.0

**Objetivo:** Bootstrappear el proyecto de producción `agentic-marketing-suite-prod` (folder QHHE `274831265727`, facturación `01624A-839C44-1DB4D6`), inicializar y desplegar el stack Pulumi `prod`, y ejecutar el primer release oficial `v0.1.0` mediante GitHub Actions y Workload Identity Federation (WIF).

---

## 1. Acciones y Resultados

1. **Creación del Proyecto GCP de Producción:**
   - Proyecto creado: `agentic-marketing-suite-prod` (Project Number: `198112926147`) en folder `274831265727`.
   - Facturación vinculada: Cuenta `01624A-839C44-1DB4D6` (MXN).
   - APIs de plataforma habilitadas (`serviceusage`, `cloudresourcemanager`, `secretmanager`, `run`, `firestore`, `pubsub`, `aiplatform`, `sqladmin`, `iap`, `compute`, `iam`, etc.).

2. **Gestión de Secretos y Configuración de Pulumi:**
   - Contenedor de secreto `pulumi-passphrase` creado y sembrado con su versión 1 en Secret Manager de `prod` desde el vault `~/.agent_dispatcher/agentic-marketing-suite-pulumi.env`.
   - Actualizado [`infra/Pulumi.prod.yaml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/infra/Pulumi.prod.yaml) con `projectNumber: "198112926147"` y montos de presupuesto.
   - Stack `prod` inicializado en backend GCS `gs://agentic-marketing-suite-pulumi-state`.

3. **Infraestructura Desplegada en Producción (`infra/__main__.py`):**
   - **Base de Datos Principal:** Firestore Native `(default)` en `us-central1`.
   - **Base de Datos Auth/Admin:** Cloud SQL Postgres `console-pg` (`POSTGRES_16`, tier `db-f1-micro`, zonal, backup habilitado).
   - **Consola Web con Direct IAP:** Cloud Run service `console` (`https://console-m6hls6q6ua-uc.a.run.app`) con Direct Cloud Run IAP activo, invoker restringido a `service-198112926147@gcp-sa-iap.iam.gserviceaccount.com` y acceso web IAP a `user:js@qhhe.net`.
   - **Ejecutor de Pipeline:** Cloud Run Job `suite-orchestrator`.
   - **Mensajería:** Tópicos Pub/Sub `client-interview-questions`, `layer-handoff`, `review-queue-events`.
   - **Workload Identity Federation:** Pool `github-actions` y Provider `github-actions-provider` con condición estricta `assertion.repository == 'jaimevelarca/agentic-marketing-suite' && assertion.ref.startsWith('refs/tags/v')`.
   - **Permisos Cross-Project:** Lectura de imágenes en Artifact Registry `agentic-marketing-suite/suite` concedida a `console-web`, `suite-runner`, `service-198112926147@serverless-robot-prod.iam.gserviceaccount.com` y `pulumi-deployer`.

4. **Verificación CI/CD en Vivo (Release `v0.1.0`):**
   - Tag git `v0.1.0` disparó el workflow [`.github/workflows/promote-prod.yml`](file:///Users/jaime/dev/qhhe/agentic-marketing-suite/.github/workflows/promote-prod.yml).
   - **GitHub Actions Run:** [`Promote to Prod (Run 32621989376)`](https://github.com/jaimevelarca/agentic-marketing-suite/actions/runs/32621989376) completado en 4m 18s **100% verde de punta a punta**.
   - Autenticación OIDC vía WIF sin llaves estáticas.
   - Resolución de digests inmutables desde Artifact Registry.
   - Despliegue de Pulumi stack `prod`.
   - Compuerta de humo automatizada (`scripts/smoke_check.py`) verificó:
     1. Redirección HTTP 302 hacia Google Authentication en la URL de producción (`https://console-m6hls6q6ua-uc.a.run.app`).
     2. Digests de imágenes desplegadas validados contra Artifact Registry.
     3. Ejecución en vivo de Cloud Run Job `suite-orchestrator` con `SUITE_LLM_PROVIDER=fixture` (19/19 agentes, salida 0, $0.00 costo Gemini).

5. **Pruebas Offline:**
   - `uv run --all-extras pytest -q`: **257/257 passed** (4.1s).

---

## 2. Datos y URLs de Producción

| Recurso | Identificador / URL |
|---|---|
| **Proyecto GCP Prod** | `agentic-marketing-suite-prod` (Número: `198112926147`) |
| **URL Consola Prod (Direct IAP)** | `https://console-m6hls6q6ua-uc.a.run.app` |
| **Usuario Autorizado IAP** | `user:js@qhhe.net` |
| **WIF Provider Prod** | `projects/198112926147/locations/global/workloadIdentityPools/github-actions/providers/github-actions-provider` |
| **Deployer Service Account** | `pulumi-deployer@agentic-marketing-suite-prod.iam.gserviceaccount.com` |
| **Digest Imagen Consola Promovida** | `us-central1-docker.pkg.dev/agentic-marketing-suite/suite/console@sha256:17d3d2108ad237da638f8e28caca781afb12ed9efc44ac5252e79d9e381bd483` |
| **Digest Imagen Orchestrator Promovida** | `us-central1-docker.pkg.dev/agentic-marketing-suite/suite/orchestrator@sha256:555ef81cc7ea34921fd5ec7328fa5c2d6079eaf8f80d9af1d2d82c7d769b7041` |
| **Release Tag** | `v0.1.0` |

---

## 3. Estado Final y Siguientes Fases

- **Hitos Completados:** Fases 0, 1, 2, 3, 4, 5, 6a, 6b y Producción Release `v0.1.0` están 100% concluidas y operativas.
- **Siguientes Pasos Disponibles:**
  1. **Fase 7 — Superficie Gemini Enterprise Agent Platform:** Exponer los agentes a Gemini Enterprise (Pay-as-you-go) mediante Vertex Reasoning Engine (`gcp.vertex.AiReasoningEngine` / `agent_engines`) o tarjetas de agente A2A.
  2. **Fase 8 — Integraciones Reales de Distribución:** Conectores reales para Meta Ads API (Capa 4) y Resend API (Capa 5) detrás del servidor MCP `platform_apis` con la compuerta humana obligatoria de autorización financiera (`#1ebe82`).
