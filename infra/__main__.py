"""Agentic Marketing Suite — project infrastructure.

Everything in the GCP project `agentic-marketing-suite` is managed here except:
  - the project itself (created 2026-08-19, folder 274831265727)
  - the state bucket gs://agentic-marketing-suite-pulumi-state
See infra/README.md for bootstrap and operating instructions.
"""
import pulumi
import pulumi_gcp as gcp

cfg = pulumi.Config("gcp")
project = cfg.require("project")
region = cfg.require("region")

BILLING_ACCOUNT = "01624A-839C44-1DB4D6"

# --- APIs -------------------------------------------------------------------
API_IDS = [
    "run.googleapis.com",
    "firestore.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "billingbudgets.googleapis.com",
    "iamcredentials.googleapis.com",
    "sqladmin.googleapis.com",  # Django auth DB arrives in roadmap Phase 5
    "compute.googleapis.com",   # provider region metadata (silences ADC probe warning)
]
apis = {
    api: gcp.projects.Service(
        api.split(".")[0],
        project=project,
        service=api,
        disable_on_destroy=False,
    )
    for api in API_IDS
}

# --- Artifact Registry ------------------------------------------------------
repo = gcp.artifactregistry.Repository(
    "suite",
    project=project,
    location=region,
    repository_id="suite",
    format="DOCKER",
    description="Container images for the Agentic Marketing Suite",
    opts=pulumi.ResourceOptions(depends_on=[apis["artifactregistry.googleapis.com"]]),
)

# --- Firestore (primary application database) -------------------------------
firestore_db = gcp.firestore.Database(
    "default",
    project=project,
    name="(default)",
    location_id=region,
    type="FIRESTORE_NATIVE",
    delete_protection_state="DELETE_PROTECTION_ENABLED",
    deletion_policy="ABANDON",
    opts=pulumi.ResourceOptions(depends_on=[apis["firestore.googleapis.com"]]),
)

# --- Runtime service account + IAM ------------------------------------------
runner_sa = gcp.serviceaccount.Account(
    "suite-runner",
    project=project,
    account_id="suite-runner",
    display_name="Suite pipeline runtime (Cloud Run Jobs)",
)

RUNNER_ROLES = [
    "roles/datastore.user",
    "roles/pubsub.publisher",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
]
for role in RUNNER_ROLES:
    gcp.projects.IAMMember(
        f"runner-{role.split('/')[-1]}",
        project=project,
        role=role,
        member=runner_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# --- Pub/Sub topics (names consumed by suite/infra/config.py) ---------------
topics = {
    name: gcp.pubsub.Topic(
        name,
        project=project,
        name=name,
        opts=pulumi.ResourceOptions(depends_on=[apis["pubsub.googleapis.com"]]),
    )
    for name in ("client-interview-questions", "layer-handoff")
}

# --- Budget alert (MXN 2,000/mo ≈ USD 100 on this project) ------------------
budget = gcp.billing.Budget(
    "monthly-budget",
    billing_account=BILLING_ACCOUNT,
    display_name="agentic-marketing-suite monthly",
    # Project number hardcoded (project created 2026-08-19); avoids a
    # get_project data-source probe that requires extra APIs at preview time.
    budget_filter={
        "projects": ["projects/54069477296"],
    },
    # Billing account currency is MXN — a mismatched currency_code is a 400.
    amount={"specified_amount": {"currency_code": "MXN", "units": "2000"}},
    threshold_rules=[
        {"threshold_percent": 0.5},
        {"threshold_percent": 0.9},
        {"threshold_percent": 1.0},
    ],
    opts=pulumi.ResourceOptions(depends_on=[apis["billingbudgets.googleapis.com"]]),
)

# --- Outputs ----------------------------------------------------------------
pulumi.export("artifact_repo_url", pulumi.Output.concat(
    region, "-docker.pkg.dev/", project, "/", repo.repository_id))
pulumi.export("firestore_database", firestore_db.name)
pulumi.export("runner_sa_email", runner_sa.email)
pulumi.export("topics", list(topics.keys()))
