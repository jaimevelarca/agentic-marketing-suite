# Sesión 2026-08-25 — Publicación y Despliegue: Release v0.2.0 a Producción

**Objetivo:** Desplegar y verificar en producción (`agentic-marketing-suite-prod`, Project Number `198112926147`) el release `v0.2.0`, integrando las capacidades completas de las Fases 7 (Gemini Enterprise Reasoning Engine + A2A), Fase 8 (Integración real con Meta Ads y Resend Email con compuerta financiera `#1ebe82`) y Fase 9 (Compilador automatizado de propuestas comerciales en 9 actos y reportes de detalle).

---

## 1. Ajustes y Resiliencia en el Pipeline de CI/CD

Durante la validación y el despliegue se realizaron las siguientes correcciones operativas:

1. **Configuración de Proyecto GCP por Defecto (`suite/infra/config.py`):**
   - Se actualizó el valor por defecto de `project_id` de `"ai-mkt-suite"` a `"agentic-marketing-suite"`.

2. **Resolución de Rutas de Importación en Contenedores (`deploy/Dockerfile` y `web/Dockerfile`):**
   - Se unificó `ENV PYTHONPATH=/app:/app/suite` garantizando la resolución tanto de `suite.*` como de los módulos raíz `infra.*`, `agents.*` y `orchestration.*`.

3. **Resiliencia de Sesiones en Modo Fixture (`suite/orchestration/adk_entrypoint.py`):**
   - Se implementó la selección dinámica del servicio de sesiones en `_runner_and_service()`:
     - `SUITE_BACKEND=memory` → `InMemorySessionService()` (para ejecución offline / compuerta de humo en Cloud Run).
     - `SUITE_BACKEND=gcp` → `FirestoreSessionService()` (para producción y ejecución con persistencia en Firestore Native).

4. **Resiliencia de Publicación en Pub/Sub (`suite/infra/clients.py`):**
   - Se envolvió `publish` con `try-except` y timeout seguro de 10s para registrar advertencias en log sin interrumpir la ejecución de los agentes en caso de latencia en colas.

5. **Manejo Seguro de Excepciones en Nodos DAG (`suite/orchestration/adk_workflow.py`):**
   - Se añadió captura y registro de excepciones por nodo en `_make_agent_fn`, alineado al contrato de `pipeline.py`.

6. **Diagnóstico Automatizado en Smoke Gate (`scripts/smoke_check.py` y `infra/__main__.py`):**
   - Se otorgó el rol `roles/logging.viewer` a la cuenta de servicio `pulumi-deployer`.
   - Se añadió extracción de detalles (`executions describe`) y lectura de logs de Cloud Logging ante fallas en `scripts/smoke_check.py`.

---

## 2. Ejecución y Verificación de Flujos en GitHub Actions

1. **CI & Deploy Dev (Run ID: `32797018672`):**
   - ✅ 313 pruebas offline pasando al 100%.
   - ✅ Construcción y publicación de imágenes inmutables en Artifact Registry.
   - ✅ Despliegue de stack `dev` en `agentic-marketing-suite`.
   - ✅ Compuerta de humo (*smoke gate*) verificada:
     - Direct IAP 302 redirect a Google OAuth validado.
     - Ejecución de job de orquestador (`suite-orchestrator`) con 19/19 agentes completados exitosamente (exit 0).

2. **Promote to Prod — Release `v0.2.0` (Run ID: `32797756714`):**
   - ✅ Disparado por tag `v0.2.0`.
   - ✅ Autenticación WIF contra `agentic-marketing-suite-prod` (Proyecto: `198112926147`).
   - ✅ Reutilización de imágenes inmutables probadas en `dev`.
   - ✅ Despliegue atómico de stack `prod` vía Pulumi.
   - ✅ Compuerta de humo en producción aprobada exitosamente:
     - Consola IAP viva y protegida (`https://console-m6hls6q6ua-uc.a.run.app`).
     - Orquestador en producción ejecutado y verificado (19/19 agentes).

---

## 3. Estado Final

- **Versión en Producción:** `v0.2.0` (Git Tag: `v0.2.0`, Digest inmutable verificado).
- **Entorno Dev:** `agentic-marketing-suite` sincronizado en `main`.
- **Entorno Prod:** `agentic-marketing-suite-prod` activo y verificado.
- **Suite de Pruebas Offline:** 313 pruebas pasando en 5.5s.
