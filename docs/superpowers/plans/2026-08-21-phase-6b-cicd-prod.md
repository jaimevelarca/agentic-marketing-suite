# Phase 6b — CI/CD, IAP Hardening, and Prod Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish an enterprise-grade CI/CD and production infrastructure for `agentic-marketing-suite`:
1. **GitHub Actions CI/CD with Workload Identity Federation (WIF):** Zero long-lived secrets in GitHub. All auth via short-lived OIDC tokens. `PULUMI_CONFIG_PASSPHRASE` loaded at runtime from Secret Manager.
2. **Dedicated Production GCP Project (`agentic-marketing-suite-prod`):** Full blast radius isolation in QHHE folder `274831265727` managed by Pulumi stack `prod` sharing state in `gs://agentic-marketing-suite-pulumi-state`.
3. **Immutable Image Digest Promotion:** Cloud Build produces commit-tagged container images. Merges to `main` deploy `dev` and resolve SHA-256 digests. Git tag `v*` promotes the **exact same immutable image digest** to `prod` without rebuilding.
4. **Direct Cloud Run IAP Hardening:** Direct Identity-Aware Proxy (GA March 2026, no external load balancer or custom domain cost) protecting `console` on both `dev` and `prod` for `js@qhhe.net`, keeping Django login as defense-in-depth and audit identity.
5. **Automated Smoke Gate (`scripts/smoke_check.py`):** Post-deployment verification that triggers a zero-cost fixture orchestrator run (exit 0), validates the 302 redirect to Google IAP authentication on the console URL, and verifies deployed container digests. Includes automated Pulumi rollback on `prod` smoke check failure.

---

## Architectural Decisions & Constraints (from `docs/session_logs/2026-08-19_fase-6b-diseno.md`)

| Decision | Implementation Choice | Rationale |
|---|---|---|
| **Prod Isolation** | Separate GCP project `agentic-marketing-suite-prod` in QHHE folder `274831265727` | Eliminates resource naming collisions (Firestore `(default)` is per-project, unprefixed Cloud SQL/Secret/Run names). Zero code changes in `suite/`. Fixed cost: ~$9–12/mo for Cloud SQL micro. |
| **Promotion Model** | Merge to `main` → deploy `dev`; git tag `v*` → deploy `prod` | Only tested, verified image digests from `dev` are promoted. Never rebuild for production. |
| **Secrets in CI** | **Zero secrets stored in GitHub repository** | Auth via WIF (`id-token: write`). `PULUMI_CONFIG_PASSPHRASE` stored in Secret Manager (`pulumi-passphrase`) and fetched dynamically by the workflow after WIF authentication. |
| **IAP Protection** | Direct Cloud Run IAP (`iap_enabled=True` + `roles/iap.httpsResourceAccessor`) | Direct Cloud Run IAP requires no Load Balancer, no custom domain, and no SSL cert management (zero extra cost). Django login preserved behind IAP as second factor and user session provider. |
| **Artifact Registry** | Single shared repository `suite` in `dev` project | Artifacts are built once and stored in `agentic-marketing-suite`. Prod Cloud Run service agent and SAs receive `roles/artifactregistry.reader` on the dev registry. |
| **Smoke Gate** | Python script `scripts/smoke_check.py` with offline unit tests | Verifies: (a) orchestrator Job execution with `SUITE_LLM_PROVIDER=fixture` succeeds (19/19 agents, zero Gemini cost); (b) console URL returns HTTP 302 redirect to `accounts.google.com`; (c) deployed revision digest matches expected build. |
| **Offline Testing Contract** | 234 existing tests remain 100% green; new tests for workflow security & smoke logic | Every change validated offline without cloud dependencies. |

---

## Global Constraints & Reference Data

- **GCP Folder:** QHHE `274831265727`
- **Billing Account:** `01624A-839C44-1DB4D6` (Currency: MXN)
- **Dev Project:** `agentic-marketing-suite` (Project Number: `54069477296`)
- **Prod Project:** `agentic-marketing-suite-prod` (To be created / configured)
- **Primary Region:** `us-central1`
- **State Bucket:** `gs://agentic-marketing-suite-pulumi-state`
- **Authorized IAP User:** `user:js@qhhe.net`
- **Repository:** `jaimevelarca/agentic-marketing-suite`

---

## Tasks Breakdown

### Task 1: Pulumi Parameterization & Immutable Image Tagging

**Files:**
- Modify: `infra/__main__.py`
- Modify: `infra/Pulumi.dev.yaml`
- Modify: `deploy/cloudbuild.yaml`
- Modify: `web/cloudbuild.yaml`

**Objective:**
Remove hardcoded `:latest` tags. Parameterize image URLs, project numbers, budget amounts, and Artifact Registry hosting so that `infra/` supports both `dev` and `prod` cleanly.

- [x] **Step 1.1:** Update `deploy/cloudbuild.yaml` and `web/cloudbuild.yaml` to tag images with `${_TAG}` (short commit SHA) and drop `:latest`.
- [x] **Step 1.2:** Update `infra/Pulumi.dev.yaml` to include stack configuration:
  - `projectNumber: "54069477296"`
  - `budgetAmount: "2000"`
  - `isArtifactHost: "true"`
  - `artifactHostProject: "agentic-marketing-suite"`
- [x] **Step 1.3:** Refactor `infra/__main__.py`:
  - Read `console_image` from config `consoleImage` (falling back to tag if provided, or short-sha tag).
  - Read `orchestrator_image` from config `orchestratorImage`.
  - Read `project_number` and `budget_amount` from stack config.
  - Conditionally create `gcp.artifactregistry.Repository` only when `is_artifact_host` is true.
  - If `is_artifact_host` is false, grant `roles/artifactregistry.reader` on the host repository (`agentic-marketing-suite`) to runtime SA, web SA, and the project's Cloud Run service agent (`service-{PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com`).
  - Export `deployed_console_image` and `deployed_orchestrator_image`.

---

### Task 2: Direct Cloud Run IAP Hardening

**Files:**
- Modify: `infra/__main__.py`

**Objective:**
Lock down the Cloud Run `console` service with Direct Cloud Run IAP. Remove public access (`allUsers`) while granting IAP invoker rights to the Google IAP Service Agent and web access to `js@qhhe.net`.

- [x] **Step 2.1:** Remove `gcp.cloudrunv2.ServiceIamMember("console-public-invoker", ...)` (`allUsers`).
- [x] **Step 2.2:** Configure `gcp.cloudrunv2.Service("console", ...)` with `iap_enabled=True`.
- [x] **Step 2.3:** Grant `roles/run.invoker` to the project's IAP service agent (`service-{PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com`) on the `console` Cloud Run service.
- [x] **Step 2.4:** Add `gcp.iap.WebCloudRunServiceIamMember("console-iap-user", ...)` granting `roles/iap.httpsResourceAccessor` to `user:js@qhhe.net`.

---

### Task 3: Workload Identity Federation (WIF) & Secret Manager Passphrase

**Files:**
- Modify: `infra/__main__.py`

**Objective:**
Provision WIF pool, provider, and `pulumi-deployer` service account in IaC for passwordless, keyless GitHub Actions execution. Manage `pulumi-passphrase` secret container and IAM in Pulumi.

- [x] **Step 3.1:** Provision `gcp.iam.WorkloadIdentityPool("github-actions-pool", workload_identity_pool_id="github-actions", ...)` in `infra/__main__.py`.
- [x] **Step 3.2:** Provision `gcp.iam.WorkloadIdentityPoolProvider("github-actions-provider", ...)` with:
  - Issuer: `https://token.actions.githubusercontent.com`
  - Attribute mapping: `google.subject=assertion.sub`, `attribute.actor=assertion.actor`, `attribute.repository=assertion.repository`, `attribute.repository_owner=assertion.repository_owner`, `attribute.ref=assertion.ref`
  - Attribute condition:
    - On `dev`: `assertion.repository == 'jaimevelarca/agentic-marketing-suite'`
    - On `prod`: `assertion.repository == 'jaimevelarca/agentic-marketing-suite' && assertion.ref.startsWith('refs/tags/v')`
- [x] **Step 3.3:** Provision `gcp.serviceaccount.Account("pulumi-deployer", account_id="pulumi-deployer", ...)` and bind `roles/iam.workloadIdentityUser` to the GitHub repository principalSet.
- [x] **Step 3.4:** Assign required deployment roles to `pulumi-deployer`:
  - `roles/run.admin`
  - `roles/artifactregistry.admin` (or reader on artifact host)
  - `roles/cloudbuild.builds.editor`
  - `roles/secretmanager.admin`
  - `roles/datastore.owner`
  - `roles/cloudsql.admin`
  - `roles/pubsub.admin`
  - `roles/resourcemanager.projectIamAdmin`
  - `roles/iam.serviceAccountUser`
  - `roles/iam.serviceAccountAdmin`
  - `roles/serviceusage.serviceUsageAdmin`
- [x] **Step 3.5:** Provision `gcp.secretmanager.Secret("pulumi-passphrase", ...)` (metadata/IAM only; version seeded out-of-band) and grant `roles/secretmanager.secretAccessor` to `pulumi-deployer`.
- [x] **Step 3.6:** Export `wif_provider_name` and `deployer_sa_email` from the stack.

---

### Task 4: Production Stack (`prod`) Scaffolding & Documentation

**Files:**
- Create: `infra/Pulumi.prod.yaml`
- Modify: `infra/README.md`

**Objective:**
Define the Pulumi production stack configuration and document bootstrap steps for `agentic-marketing-suite-prod`.

- [x] **Step 4.1:** Create `infra/Pulumi.prod.yaml` with:
  - `gcp:project`: `agentic-marketing-suite-prod`
  - `gcp:region`: `us-central1`
  - `gcp:billingProject`: `agentic-marketing-suite-prod`
  - `gcp:userProjectOverride`: `"true"`
  - `budgetAmount`: `"4000"`
  - `isArtifactHost`: `"false"`
  - `artifactHostProject`: `agentic-marketing-suite`
- [x] **Step 4.2:** Document in `infra/README.md`:
  - Bootstrap guide for creating `agentic-marketing-suite-prod` under QHHE folder `274831265727`.
  - Linking billing account `01624A-839C44-1DB4D6`.
  - Seeding `pulumi-passphrase` secret in Secret Manager from the vault.
  - Initial stack initialization: `pulumi stack init prod --secrets-provider=passphrase`.

---

### Task 5: Smoke Check Gate Script & Offline Tests

**Files:**
- Create: `scripts/smoke_check.py`
- Create: `tests/scripts/__init__.py`
- Create: `tests/scripts/test_smoke_check.py`

**Objective:**
Implement a reliable, zero-cost smoke verification gate in Python to be executed after every deployment.

- [x] **Step 5.1:** Implement `scripts/smoke_check.py` with CLI flags:
  - `--project`: GCP project ID
  - `--region`: GCP region (default `us-central1`)
  - `--stack`: Stack name (`dev` or `prod`)
  - `--console-url`: Cloud Run service URL
  - `--expected-console-digest`: Expected SHA256 digest of console image
  - `--expected-orchestrator-digest`: Expected SHA256 digest of orchestrator image
  - `--timeout`: Timeout in seconds (default 300)
- [x] **Step 5.2:** Implement verification logic in `scripts/smoke_check.py`:
  - **Check A (Job Execution):** Execute Cloud Run Job `suite-orchestrator` with `--override-env SUITE_LLM_PROVIDER=fixture` and client ID `smoke-<sha>` → wait for execution completion → assert exit code 0.
  - **Check B (IAP Verification):** Perform HTTP GET to `console-url` with redirect following disabled (`allow_redirects=False`) → assert HTTP status 302/307 and header `Location` containing `accounts.google.com` or Google IAP auth URL.
  - **Check C (Image Digest Verification):** Query deployed Cloud Run service and job image attributes and assert they match the expected digest.
- [x] **Step 5.3:** Write offline unit tests in `tests/scripts/test_smoke_check.py`:
  - Test Job execution parsing (successful execution vs failed execution).
  - Test IAP 302 redirect verification (valid redirect to accounts.google.com vs unexpected 200/500).
  - Test digest verification logic.
  - Test CLI argument parsing and error reporting.
  - Run `uv run pytest -q tests/scripts/` to ensure green.

---

### Task 6: GitHub Actions CI/CD Workflows & Security Verification Tests

**Files:**
- Create: `.github/workflows/pr-check.yml`
- Create: `.github/workflows/ci-dev.yml`
- Create: `.github/workflows/promote-prod.yml`
- Create: `tests/infra/test_workflow_security.py`

**Objective:**
Create complete GitHub Actions workflows adhering strictly to the zero-secrets, WIF-only model, and verify workflow security offline with pytest.

- [x] **Step 6.1:** Create `.github/workflows/pr-check.yml`:
  - Triggers on `pull_request` to `main`.
  - Runs `uv sync` and `uv run pytest -q` (all 234+ tests).
  - Authenticates via WIF (`id-token: write`).
  - Fetches `PULUMI_CONFIG_PASSPHRASE` from Secret Manager.
  - Runs `pulumi preview --stack dev`.
- [x] **Step 6.2:** Create `.github/workflows/ci-dev.yml`:
  - Triggers on `push` to `main` (paths-ignore: docs, markdown, etc.).
  - Runs `uv run pytest -q`.
  - Authenticates via WIF.
  - Builds and pushes images with commit SHA tag using Cloud Build (`gcloud builds submit`).
  - Resolves immutable image digests (`sha256:...`).
  - Configures stack `dev` (`pulumi config set consoleImage ...`, `orchestratorImage ...`).
  - Executes `pulumi up --stack dev --yes`.
  - Executes `uv run python scripts/smoke_check.py --stack dev --project agentic-marketing-suite --console-url $(pulumi stack output web_url)`.
- [x] **Step 6.3:** Create `.github/workflows/promote-prod.yml`:
  - Triggers only on `push` tags `v*`.
  - Authenticates via WIF on `agentic-marketing-suite-prod` (guaranteed by WIF condition `assertion.ref.startsWith('refs/tags/v')`).
  - Resolves image digests deployed in `dev` (or built from commit SHA).
  - Configures stack `prod` (`pulumi config set --stack prod consoleImage ...`, `orchestratorImage ...`).
  - Executes `pulumi up --stack prod --yes`.
  - Executes `uv run python scripts/smoke_check.py --stack prod --project agentic-marketing-suite-prod --console-url $(pulumi stack output web_url)`.
  - **Automated Rollback:** If smoke check fails, runs fallback step `pulumi config set --stack prod consoleImage <previous>` + `pulumi up --stack prod --yes`.
- [x] **Step 6.4:** Implement offline security test `tests/infra/test_workflow_security.py`:
  - Verifies no workflow files contain hardcoded secrets or references to `GCP_SA_KEY` / `GOOGLE_APPLICATION_CREDENTIALS`.
  - Verifies all workflows declare `permissions: id-token: write, contents: read`.
  - Verifies `promote-prod.yml` trigger is restricted strictly to `tags: ['v*']`.
  - Verifies no `:latest` tag literals appear in `infra/__main__.py` container images.
  - Run `uv run pytest -q` to verify entire suite passes.

---

### Task 7: Documentation & Roadmap Closeout

**Files:**
- Modify: `ROADMAP.md`
- Modify: `AGENTS.md`
- Modify: `infra/README.md`

**Objective:**
Update documentation reflecting Phase 6b architecture, bootstrap commands, and operational procedures.

- [x] **Step 7.1:** Update `ROADMAP.md` marking Phase 6 (6a and 6b) complete.
- [x] **Step 7.2:** Update `infra/README.md` with complete instructions for WIF, IAP, multi-project Pulumi management, and the smoke check script.
- [x] **Step 7.3:** Run full offline test suite (`uv run pytest -q`).


---

## Live Verification & Execution Checklist (Post-Approval)

After human approval of this plan, the execution will follow:
1. **Local Test Gate:** `uv run pytest -q` passes 100% offline.
2. **IaC Code Changes:** Update `infra/__main__.py`, `deploy/cloudbuild.yaml`, `web/cloudbuild.yaml`, `scripts/smoke_check.py`, `.github/workflows/*.yml`.
3. **WIF & Dev Stack Deployment:** Run `pulumi up --stack dev` locally to provision WIF and IAP in `agentic-marketing-suite`.
4. **Secret Seeding:** Seed `pulumi-passphrase` in `agentic-marketing-suite` Secret Manager with `gcloud secrets versions add pulumi-passphrase --data-file=...`.
5. **Dev Smoke Run:** Run `python scripts/smoke_check.py --stack dev ...` to verify live IAP 302 redirect and fixture job completion.
6. **Prod Bootstrap:** Create GCP project `agentic-marketing-suite-prod` (via `js@qhhe.net`), link billing, seed secret, run initial `pulumi up --stack prod`.
7. **Git Commit & Push:** Push `main` to trigger `.github/workflows/ci-dev.yml` and tag `v0.1.0` to trigger `.github/workflows/promote-prod.yml`.
