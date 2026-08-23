# Production Bootstrap and Release v0.1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the dedicated production GCP project `agentic-marketing-suite-prod` (QHHE folder `274831265727`, billing `01624A-839C44-1DB4D6`), initialize and apply the Pulumi `prod` stack, and trigger and verify the first production release via git tag `v0.1.0` through GitHub Actions WIF CI/CD.

---

## Architectural Context & Reference Data

| Attribute | Value / Decision | Notes |
|---|---|---|
| **Prod Project ID** | `agentic-marketing-suite-prod` | Dedicated GCP project under QHHE folder `274831265727` |
| **Dev Project ID** | `agentic-marketing-suite` | Project Number: `54069477296` (hosts Artifact Registry `suite`) |
| **Billing Account** | `01624A-839C44-1DB4D6` | Currency: MXN (Monthly budget alert: MXN 4,000 in prod) |
| **GCP Identity** | `js@qhhe.net` (`dispatcher switch qhhe`) | Owner / admin permissions on folder `274831265727` |
| **State Backend** | `gs://agentic-marketing-suite-pulumi-state` | Shared bucket in `us-central1`, stack `prod` |
| **Secrets Engine** | `PULUMI_CONFIG_PASSPHRASE` from `~/.agent_dispatcher/` & Secret Manager | Zero secrets stored in GitHub repository |
| **Promotion Model** | Git Tag `refs/tags/v*` (e.g. `v0.1.0`) | Promotes exact immutable image digests verified in `dev` |
| **Smoke Gate** | `scripts/smoke_check.py` | Liveness + IAP 302 redirect check + zero-cost fixture job (19/19) |

---

## Tasks Breakdown

### Task 1: GCP Project Creation & Billing Association

**Files:**
- None (GCP CLI commands)

**Objective:**
Create project `agentic-marketing-suite-prod` in folder `274831265727`, link billing account `01624A-839C44-1DB4D6`, enable foundational service APIs, and capture the assigned `PROD_PROJECT_NUMBER`.

- [x] **Step 1.1:** Create GCP project `agentic-marketing-suite-prod`:
  ```bash
  gcloud projects create agentic-marketing-suite-prod \
    --folder=274831265727 \
    --name="agentic-marketing-suite-prod"
  ```
- [x] **Step 1.2:** Link billing account:
  ```bash
  gcloud beta billing projects link agentic-marketing-suite-prod \
    --billing-account=01624A-839C44-1DB4D6
  ```
- [x] **Step 1.3:** Enable baseline APIs (`serviceusage`, `cloudresourcemanager`, `secretmanager`):
  ```bash
  gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com secretmanager.googleapis.com --project=agentic-marketing-suite-prod
  ```
- [x] **Step 1.4:** Retrieve assigned `PROD_PROJECT_NUMBER`:
  ```bash
  gcloud projects describe agentic-marketing-suite-prod --format="value(projectNumber)"
  ```

---

### Task 2: Secret Manager Seeding & Pulumi Prod Stack Configuration

**Files:**
- Modify: `infra/Pulumi.prod.yaml`
- Modify: `.github/workflows/promote-prod.yml`
- Modify: `tests/infra/test_workflow_security.py`

**Objective:**
Seed `pulumi-passphrase` into `agentic-marketing-suite-prod` Secret Manager, update `infra/Pulumi.prod.yaml` with the real `projectNumber`, and configure `PROD_WIF_PROVIDER` in `.github/workflows/promote-prod.yml`.

- [x] **Step 2.1:** Create and seed `pulumi-passphrase` in `agentic-marketing-suite-prod`:
  ```bash
  gcloud secrets create pulumi-passphrase --replication-policy="automatic" --project=agentic-marketing-suite-prod
  gcloud secrets versions add pulumi-passphrase \
    --project=agentic-marketing-suite-prod \
    --data-file=<(grep PULUMI_CONFIG_PASSPHRASE ~/.agent_dispatcher/agentic-marketing-suite-pulumi.env | cut -d= -f2-)
  ```
- [x] **Step 2.2:** Update `infra/Pulumi.prod.yaml` with `projectNumber: "<PROD_PROJECT_NUMBER>"`.
- [x] **Step 2.3:** Update `.github/workflows/promote-prod.yml`:
  - Set `PROD_WIF_PROVIDER` to `projects/<PROD_PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-actions/providers/github-actions-provider`.
- [x] **Step 2.4:** Run `uv run --all-extras pytest -q` to ensure all 257+ offline tests remain 100% green.

---

### Task 3: Initial Pulumi Prod Stack Provisioning

**Files:**
- Modify / Verify: `infra/__main__.py`
- Modify / Verify: `infra/Pulumi.prod.yaml`

**Objective:**
Initialize and execute `pulumi up --stack prod` locally using ADC credentials (`js@qhhe.net`) to provision all prod resources (Firestore, Cloud SQL, WIF pool/provider, Cloud Run console & orchestrator, IAM, cross-project Artifact Registry permissions).

- [x] **Step 3.1:** Resolve the latest verified container image digests deployed in `dev`:
  ```bash
  cd infra
  export PULUMI_CONFIG_PASSPHRASE=$(grep PULUMI_CONFIG_PASSPHRASE ~/.agent_dispatcher/agentic-marketing-suite-pulumi.env | cut -d= -f2-)
  pulumi login gs://agentic-marketing-suite-pulumi-state
  DEV_CONSOLE=$(pulumi stack output deployed_console_image --stack dev)
  DEV_ORCHESTRATOR=$(pulumi stack output deployed_orchestrator_image --stack dev)
  ```
- [x] **Step 3.2:** Set initial image configs on `prod` stack:
  ```bash
  pulumi config set consoleImage "${DEV_CONSOLE}" --stack prod
  pulumi config set orchestratorImage "${DEV_ORCHESTRATOR}" --stack prod
  ```
- [x] **Step 3.3:** Run `pulumi up --stack prod --yes` and verify all GCP resources are created cleanly.
- [x] **Step 3.4:** Run `scripts/smoke_check.py` against `prod` to verify initial health:
  ```bash
  cd ..
  PROD_CONSOLE_URL=$(cd infra && pulumi stack output web_url --stack prod)
  uv run python scripts/smoke_check.py \
    --project=agentic-marketing-suite-prod \
    --region=us-central1 \
    --stack=prod \
    --console-url="${PROD_CONSOLE_URL}"
  ```

---

### Task 4: Release v0.1.0 via GitHub Actions CI/CD Promotion

**Files:**
- Git repository tags and commits

**Objective:**
Commit the updated configuration (`Pulumi.prod.yaml`, `promote-prod.yml`), push to `origin/main`, tag release `v0.1.0`, and monitor the automated GitHub Actions workflow `.github/workflows/promote-prod.yml` to verify end-to-end WIF auth, image digest promotion, and smoke gate verification in production.

- [x] **Step 4.1:** Commit configuration changes and push to `origin/main`:
  ```bash
  git add infra/Pulumi.prod.yaml .github/workflows/promote-prod.yml
  git commit -m "chore(infra): configure prod project number and WIF provider for v0.1.0 release"
  git push origin main
  ```
- [x] **Step 4.2:** Create and push release tag `v0.1.0`:
  ```bash
  git tag -a v0.1.0 -m "Release v0.1.0 — Production baseline with Direct IAP, ADK 2.x, Firestore, and CI/CD"
  git push origin v0.1.0
  ```
- [x] **Step 4.3:** Monitor GitHub Actions run for `Promote to Prod (Tagged Release)` on tag `v0.1.0` until completion (expected green).
- [x] **Step 4.4:** Inspect live prod console URL to confirm Direct IAP 302 redirect for `js@qhhe.net`.

---

### Task 5: Documentation & Roadmap Closeout

**Files:**
- Modify: `ROADMAP.md`
- Modify: `AGENTS.md`
- Modify: `infra/README.md`
- Create: `docs/session_logs/2026-08-22_prod-release-v0.1.0.md`

**Objective:**
Document the production release, record live proofs and URLs, update ROADMAP, and document the ready state for Phase 7 (Gemini Enterprise Platform Surface) and Phase 8 (Real Distribution Integrations).

- [x] **Step 5.1:** Update `ROADMAP.md` recording production deployment of `agentic-marketing-suite-prod` and release `v0.1.0`.
- [x] **Step 5.2:** Create session log `docs/session_logs/2026-08-22_prod-release-v0.1.0.md` capturing all live outputs and validation proofs.
- [x] **Step 5.3:** Run `uv run --all-extras pytest -q` to confirm full test suite passes.
