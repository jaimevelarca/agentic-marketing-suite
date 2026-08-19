# Phase 1 — Pulumi Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The GCP project `agentic-marketing-suite` becomes fully reproducible from `pulumi up` — APIs, Artifact Registry, Firestore, service account + IAM, Pub/Sub, Secret Manager placeholder, budget alert — with only the state bucket and the project itself hand-made (and imported or documented).

**Architecture:** One Pulumi Python program in `infra/` (its own uv project, separate from the suite package), OSS backend with state in a GCS bucket, stack `dev` targeting the single project. Resources the app reads at runtime (topic names, SA email) become stack outputs.

**Tech Stack:** Pulumi CLI ≥3, `pulumi-gcp` v9.x (Python), uv, GCS state backend.

**Spec:** `ROADMAP.md` Phase 1 + stack decisions table.

## Global Constraints

- GCP project `agentic-marketing-suite`, folder `274831265727`, billing `01624A-839C44-1DB4D6`, region `us-central1`.
- Pulumi state: `gs://agentic-marketing-suite-pulumi-state` (the ONE hand-made resource; documented in `infra/README.md`).
- Secrets passphrase for the OSS backend lives in the vault (`~/.agent_dispatcher/`), never in the repo.
- No service-account keys, ever. Local auth = ADC; CI auth = Workload Identity Federation (Phase 6).
- Python 3.12, uv. Suite's 207 offline tests stay green (infra/ must not touch suite code).

---

### Task 1: Bootstrap — state bucket, Pulumi login, project skeleton

**Files:**
- Create: `infra/README.md`, `infra/pyproject.toml`, `infra/Pulumi.yaml`, `infra/Pulumi.dev.yaml`, `infra/.gitignore`

**Interfaces:**
- Produces: a working `pulumi preview` against stack `dev` with zero resources.

- [x] **Step 1: Create the state bucket (hand-made, once)** — `gcloud storage buckets create gs://agentic-marketing-suite-pulumi-state --location=us-central1 --uniform-bucket-level-access` and enable versioning.
- [x] **Step 2: Generate a passphrase into the vault** — `openssl rand -base64 32` → `~/.agent_dispatcher/agentic-marketing-suite-pulumi.env` as `PULUMI_CONFIG_PASSPHRASE=…` (0600). Never echo it.
- [x] **Step 3: Ensure Pulumi CLI** — `pulumi version`; if absent, `brew install pulumi` (Tier 2: standing session authorization covers it).
- [x] **Step 4: Scaffold `infra/`** — `Pulumi.yaml` (name `agentic-marketing-suite-infra`, runtime python with `toolchain: uv`), `pyproject.toml` (deps `pulumi>=3`, `pulumi-gcp>=9,<10`), stack config `gcp:project=agentic-marketing-suite`, `gcp:region=us-central1`.
- [x] **Step 5: `pulumi login gs://agentic-marketing-suite-pulumi-state && pulumi stack init dev --secrets-provider=passphrase`** (passphrase from vault env file).
- [x] **Step 6: `pulumi preview` with empty `__main__.py`** — expect "0 to create". Commit.

### Task 2: Grant the ADC account rights + enable APIs via Pulumi

**Files:**
- Create: `infra/__main__.py` (apis section)

**Interfaces:**
- Produces: `gcp.projects.Service` resources for: `run`, `firestore`, `artifactregistry`, `secretmanager`, `pubsub`, `aiplatform`, `cloudbuild`, `logging`, `monitoring`, `billingbudgets`, `iamcredentials`, `sqladmin`.

- [x] **Step 1:** `gcloud projects add-iam-policy-binding agentic-marketing-suite --member=user:jaimevelarca@gmail.com --role=roles/owner` (ADC account must manage the project; run as js@qhhe.net active config).
- [x] **Step 2:** Write the `services` loop in `__main__.py` with `disable_on_destroy=False`.
- [x] **Step 3:** `pulumi up --yes` → expect all API resources created. Commit.

### Task 3: Artifact Registry + Firestore

**Interfaces:**
- Produces: `gcp.artifactregistry.Repository("suite", format="DOCKER", location=region)`; `gcp.firestore.Database("default", name="(default)", type="FIRESTORE_NATIVE", location_id=region)` — both `depends_on` their APIs.

- [x] **Step 1:** Add both resources; export `artifact_repo_url` output.
- [x] **Step 2:** `pulumi up --yes`; verify `gcloud firestore databases list`. Commit.

### Task 4: Runtime service account + IAM + Pub/Sub + secret placeholder

**Interfaces:**
- Produces: SA `suite-runner@agentic-marketing-suite.iam.gserviceaccount.com` with project roles `datastore.user`, `pubsub.publisher`, `aiplatform.user`, `logging.logWriter`, `secretmanager.secretAccessor`; topics `client-interview-questions`, `layer-handoff`; empty Secret Manager secret `gemini-extras` placeholder is NOT created (no secrets needed for Vertex ADC path — skip unless Phase 3 finds one). Outputs: `runner_sa_email`, `topic_*` names.

- [x] **Step 1:** Add SA, `gcp.projects.IAMMember` per role, `gcp.pubsub.Topic` ×2.
- [x] **Step 2:** `pulumi up --yes`. Commit.

### Task 5: Budget alert

**Interfaces:**
- Produces: `gcp.billing.Budget` on account `01624A-839C44-1DB4D6` scoped to this project — USD 100/mo, thresholds 0.5/0.9/1.0.

- [x] **Step 1:** Add the budget resource (needs `billing.budgets.create` on the account; if ADC lacks it, record the manual `gcloud billing budgets create` fallback in `infra/README.md` and move on).
- [x] **Step 2:** `pulumi up --yes`. Commit.

### Task 6: Document + wire into repo docs

- [x] **Step 1:** `infra/README.md`: bootstrap steps (bucket, vault passphrase, login), how to run (`source vault env → pulumi up`), stack outputs, what is deliberately NOT in IaC (project, state bucket).
- [x] **Step 2:** Update `ROADMAP.md` Phase 1 → exit met; `AGENTS.md` pointer to `infra/README.md`.
- [x] **Step 3:** Suite tests still green (`.venv/bin/python -m pytest -q` → 207). Commit + push.
