# infra/ — Pulumi IaC for `agentic-marketing-suite`

Everything in the GCP project is managed from here, **except two hand-made
resources** (deliberate):

1. The project itself — `agentic-marketing-suite`, folder QHHE `274831265727`,
   billing `01624A-839C44-1DB4D6` (MXN), created 2026-08-19.
2. The Pulumi state bucket — `gs://agentic-marketing-suite-pulumi-state`
   (us-central1, uniform access, versioned).

## Operating

```bash
cd infra
set -a; source ~/.agent_dispatcher/agentic-marketing-suite-pulumi.env; set +a  # PULUMI_CONFIG_PASSPHRASE
pulumi login gs://agentic-marketing-suite-pulumi-state
pulumi up            # stack: dev
pulumi stack output  # artifact_repo_url, runner_sa_email, topics, firestore_database
```

Auth is ADC (`jaimevelarca@gmail.com`). The org blocks external owners, so that
account holds `roles/editor` + `roles/resourcemanager.projectIamAdmin` +
`roles/datastore.owner` on the project instead of owner. Provider config sets
`gcp:billingProject` + `gcp:userProjectOverride` (required for the
billing-budgets API under user ADC).

## What the program manages

- **APIs** (13, `disable_on_destroy=False`): run, firestore, artifactregistry,
  secretmanager, pubsub, aiplatform, cloudbuild, logging, monitoring,
  billingbudgets, iamcredentials, sqladmin (Phase 5), compute (provider probe).
- **Artifact Registry**: docker repo `suite`.
- **Firestore**: `(default)` database, native mode, us-central1,
  delete-protected, `deletion_policy=ABANDON` (a destroy abandons, never deletes
  data).
- **Runtime SA**: `suite-runner@…` with datastore.user, pubsub.publisher,
  aiplatform.user, logging.logWriter, secretmanager.secretAccessor.
- **Pub/Sub**: `client-interview-questions`, `layer-handoff` (names are the
  contract with `suite/infra/config.py`).
- **Budget**: MXN 2,000/mo (account currency is MXN — a USD amount is a 400),
  alerts at 50/90/100%.

## Gotchas learned (2026-08-19)

- Firestore database creation needs `datastore.owner` (editor is not enough).
- Budget currency must match the billing account (MXN).
- Without the compute API the provider logs a harmless region-probe warning.
- Prefer hardcoding the project number (54069477296) over
  `gcp.organizations.get_project` — the data source probes APIs at preview time.
