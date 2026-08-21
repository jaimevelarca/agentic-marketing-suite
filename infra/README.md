# infra/ — Pulumi IaC for `agentic-marketing-suite`

Everything in the GCP projects (`agentic-marketing-suite` for dev, `agentic-marketing-suite-prod` for prod) is managed from here, **except hand-made bootstrap resources** (deliberate):

1. The GCP projects — folder QHHE `274831265727`, billing `01624A-839C44-1DB4D6` (MXN).
2. The Pulumi state bucket — `gs://agentic-marketing-suite-pulumi-state` (us-central1, uniform access, versioned).
3. The initial secret version for `pulumi-passphrase` in Secret Manager (seeded from the vault so the passphrase never enters Pulumi state).

## Operating Locally

```bash
cd infra
set -a; source ~/.agent_dispatcher/agentic-marketing-suite-pulumi.env; set +a  # PULUMI_CONFIG_PASSPHRASE
pulumi login gs://agentic-marketing-suite-pulumi-state

# Dev stack
pulumi select dev
pulumi up
pulumi stack output  # web_url, wif_provider_name, deployer_sa_email, deployed_console_image, etc.

# Prod stack
pulumi select prod
pulumi up
```

Auth is ADC (`jaimevelarca@gmail.com` for dev / `js@qhhe.net` for prod). Provider config sets `gcp:billingProject` + `gcp:userProjectOverride`.

---

## Phase 6b Architecture (CI/CD, IAP & Prod Isolation)

### 1. Workload Identity Federation (WIF) & GitHub Actions
- **Zero static secrets in GitHub Actions:** CI workflows authenticate using GCP Workload Identity Federation with short-lived OIDC tokens (`id-token: write`).
- The WIF provider validates that the token originates from repository `jaimevelarca/agentic-marketing-suite`.
- On `prod`, the WIF provider condition additionally enforces `assertion.ref.startsWith('refs/tags/v')`, ensuring prod can only be deployed via tagged releases.
- The `pulumi-deployer` service account holds minimal required IAM roles and accesses `pulumi-passphrase` directly from Secret Manager at workflow runtime.

### 2. Direct Cloud Run IAP Hardening
- Direct Cloud Run Identity-Aware Proxy (`iap_enabled=True`) is active on both `dev` and `prod` `console` services.
- Requires no external Application Load Balancer, no custom domain, and no SSL certificate management (zero extra cost).
- Public access (`allUsers`) is completely removed.
- `service-{PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com` receives `roles/run.invoker`.
- `user:js@qhhe.net` receives `roles/iap.httpsResourceAccessor`.
- Django authentication is preserved behind IAP for defense-in-depth, admin portal access, and user auditing.

### 3. Dedicated Prod Project & Immutable Image Promotion
- `dev` project: `agentic-marketing-suite` (hosts Artifact Registry `suite`).
- `prod` project: `agentic-marketing-suite-prod` (reads images from `dev` Artifact Registry with `roles/artifactregistry.reader`).
- **Promotion Model:**
  1. Merge to `main` builds container images tagged with `${SHORT_SHA}` and deploys to `dev`.
  2. The exact immutable SHA256 digest (`sha256:...`) is resolved and recorded.
  3. Release tag `v*` promotes the **exact same immutable image digest** to `prod` without rebuilding.

### 4. Automated Smoke Gate (`scripts/smoke_check.py`)
Post-deployment verification gate executed after `pulumi up`:
```bash
uv run python scripts/smoke_check.py \
  --project agentic-marketing-suite \
  --region us-central1 \
  --stack dev \
  --console-url https://console-54069477296.us-central1.run.app
```
- **Check A (IAP & Liveness):** Queries console URL without following redirects, verifying HTTP 302/307 redirect to `accounts.google.com`.
- **Check B (Image Verification):** Verifies deployed revision digest matches the target build.
- **Check C (Fixture Job Execution):** Executes `suite-orchestrator` with `SUITE_LLM_PROVIDER=fixture` and asserts exit code 0 (19/19 agents, zero Gemini spend).
- **Rollback:** In `prod`, a failed smoke gate automatically triggers an atomic Pulumi rollback to the previous deployed image.

---

## Seeding Secrets (Out-of-Band)

To seed the Pulumi passphrase into a project's Secret Manager container:
```bash
# In dev
gcloud secrets versions add pulumi-passphrase \
  --project=agentic-marketing-suite \
  --data-file=<(grep PULUMI_CONFIG_PASSPHRASE ~/.agent_dispatcher/agentic-marketing-suite-pulumi.env | cut -d= -f2-)

# In prod (once created)
gcloud secrets versions add pulumi-passphrase \
  --project=agentic-marketing-suite-prod \
  --data-file=<(grep PULUMI_CONFIG_PASSPHRASE ~/.agent_dispatcher/agentic-marketing-suite-pulumi.env | cut -d= -f2-)
```
