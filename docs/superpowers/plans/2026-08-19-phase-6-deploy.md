# Phase 6 — Deploy & CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal (6a):** The actual app runs on GCP: the Django console as a Cloud Run service (Cloud SQL Postgres for auth), the suite orchestrator as a Cloud Run Job, images in Artifact Registry, all resources in Pulumi. **6b (follow-up):** GitHub Actions (WIF) shipping dev on merge + a prod stack.

**Key decisions:**
- Images built with **Cloud Build** (`gcloud builds submit`) — no local Docker dependency.
- Web service: `cpu_idle=False` (CPU always allocated) because start/resume run in daemon threads beyond the response.
- Public ingress + Django login for the dev milestone; IAP hardening recorded as 6b work.
- Cloud SQL Postgres 16, `db-f1-micro`, 10 GB — smallest footprint; `DATABASE_URL` assembled from Secret Manager password.
- Secrets via Pulumi (`pulumi-random` + Secret Manager): `django-secret-key`, `django-db-password`, `django-admin-password` (initial superuser `jaime`, created idempotently by the container entrypoint).
- Suite job defaults: `SUITE_LLM_PROVIDER=gemini`, `SUITE_BACKEND=gcp`; entrypoint `orchestration.adk_entrypoint` with args per execution.
- Deps: `web` extra gains `gunicorn` + `psycopg[binary]` (Django→Cloud SQL only; the suite itself stays SQL-free).

## Tasks
- [ ] **T1** Dockerfiles: rewrite `deploy/Dockerfile` (suite job, adk+gemini), add `web/Dockerfile` + `web/entrypoint.sh` (migrate → ensure superuser → gunicorn); `.dockerignore` updates; `gcloud builds submit` both images to Artifact Registry.
- [ ] **T2** Pulumi: pulumi-random; Cloud SQL instance+db+user; 3 secrets + versions; web SA + roles (datastore.user, aiplatform.user, pubsub.publisher, logging.logWriter, secretmanager.secretAccessor, cloudsql.client); Cloud Run v2 Service (web, cpu always-on, Cloud SQL volume, secret envs, public invoker) + Cloud Run v2 Job (suite-runner SA). Outputs: `web_url`.
- [ ] **T3** Live smoke: web URL serves the login page (200); log in as `jaime` works (verified via HTTP, password never printed); suite Job executes `start --auto-approve` with fixture provider (env override) and completes.
- [ ] **T4** Docs (`infra/README.md`, `web/README.md` prod section), ROADMAP 6a ✅, commit + push. 6b (GitHub Actions WIF + prod stack + IAP) left explicitly open.
