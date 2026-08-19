"""Agentic Marketing Suite — project infrastructure.

Everything in the GCP project `agentic-marketing-suite` is managed here except:
  - the project itself (created 2026-08-19, folder 274831265727)
  - the state bucket gs://agentic-marketing-suite-pulumi-state
See infra/README.md for bootstrap and operating instructions.
"""
import pulumi
import pulumi_gcp as gcp
import pulumi_random as random

cfg = pulumi.Config("gcp")
project = cfg.require("project")
region = cfg.require("region")

BILLING_ACCOUNT = "01624A-839C44-1DB4D6"
PROJECT_NUMBER = "54069477296"

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
    # review-queue-events is published by agent 6.1 (performance_analytics.py)
    for name in ("client-interview-questions", "layer-handoff", "review-queue-events")
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

# --- Cloud Build (default compute SA needs source + push + logs) ------------
# New projects don't grant editor to the default compute SA; Cloud Build runs
# as it and needs to read the upload bucket, push to Artifact Registry, log.
build_sa = f"serviceAccount:{PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for role in ("roles/storage.objectViewer", "roles/artifactregistry.writer",
             "roles/logging.logWriter"):
    gcp.projects.IAMMember(
        f"build-{role.split('/')[-1]}",
        project=project, role=role, member=build_sa,
    )

# --- Secrets (generated; contents never in code or state outputs) -----------
def _secret(name: str, value: pulumi.Output[str] | str) -> gcp.secretmanager.Secret:
    secret = gcp.secretmanager.Secret(
        name, project=project, secret_id=name,
        replication={"auto": {}},
        opts=pulumi.ResourceOptions(depends_on=[apis["secretmanager.googleapis.com"]]),
    )
    gcp.secretmanager.SecretVersion(f"{name}-v", secret=secret.id, secret_data=value)
    return secret

django_secret_key = random.RandomPassword("django-secret-key", length=50, special=False)
db_password = random.RandomPassword("django-db-password", length=32, special=False)
admin_password = random.RandomPassword("django-admin-password", length=20, special=False)

sec_key = _secret("django-secret-key", django_secret_key.result)
sec_admin = _secret("django-admin-password", admin_password.result)

# --- Cloud SQL (Django auth/admin/sessions ONLY — domain data is Firestore) --
sql_instance = gcp.sql.DatabaseInstance(
    "console-pg",
    project=project,
    name="console-pg",
    region=region,
    database_version="POSTGRES_16",
    deletion_protection=True,
    settings={
        # Enterprise Plus (the PG16 default) rejects shared-core tiers; the
        # cheapest footprint is ENTERPRISE + db-f1-micro.
        "edition": "ENTERPRISE",
        "tier": "db-f1-micro",
        "availability_type": "ZONAL",
        "disk_size": 10,
        "backup_configuration": {"enabled": True},
    },
    opts=pulumi.ResourceOptions(depends_on=[apis["sqladmin.googleapis.com"]]),
)
gcp.sql.Database("console-db", project=project, instance=sql_instance.name, name="console")
gcp.sql.User("django-user", project=project, instance=sql_instance.name,
             name="django", password_wo=db_password.result, password_wo_version=1)

sql_conn = pulumi.Output.concat(project, ":", region, ":", sql_instance.name)
database_url = pulumi.Output.all(db_password.result, sql_conn).apply(
    lambda a: f"postgres://django:{a[0]}@/console?host=/cloudsql/{a[1]}")
sec_dburl = _secret("django-database-url", database_url)

# --- Console (web) service account -------------------------------------------
web_sa = gcp.serviceaccount.Account(
    "console-web", project=project, account_id="console-web",
    display_name="Consola de revisión (Cloud Run service)")
WEB_ROLES = [
    "roles/datastore.user",
    "roles/aiplatform.user",
    "roles/pubsub.publisher",
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.client",
]
for role in WEB_ROLES:
    gcp.projects.IAMMember(
        f"web-{role.split('/')[-1]}",
        project=project, role=role,
        member=web_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# --- Cloud Run: console service + orchestrator job ---------------------------
# Images are built by Cloud Build (deploy/cloudbuild.yaml, web/cloudbuild.yaml)
# and referenced by :latest here; CI (6b) will pin commit tags.
_img = f"{region}-docker.pkg.dev/{project}/suite"


def _secret_env(name: str, secret) -> dict:
    return {"name": name, "value_source": {
        "secret_key_ref": {"secret": secret.secret_id, "version": "latest"}}}


console = gcp.cloudrunv2.Service(
    "console",
    project=project,
    location=region,
    name="console",
    ingress="INGRESS_TRAFFIC_ALL",
    template={
        "service_account": web_sa.email,
        "max_instance_request_concurrency": 40,
        "scaling": {"max_instance_count": 2},
        "containers": [{
            "image": f"{_img}/console:latest",
            # CPU always allocated: start/resume drive the workflow in daemon
            # threads that outlive the request. Long Gemini runs should still
            # prefer the orchestrator Job (instance may scale down when idle).
            "resources": {"cpu_idle": False,
                          "limits": {"cpu": "1", "memory": "1Gi"}},
            "envs": [
                {"name": "GCP_PROJECT_ID", "value": project},
                {"name": "SUITE_BACKEND", "value": "gcp"},
                {"name": "SUITE_LLM_PROVIDER", "value": "gemini"},
                {"name": "DJANGO_DEBUG", "value": "0"},
                {"name": "DJANGO_ALLOWED_HOSTS", "value": ".run.app,localhost"},
                {"name": "DJANGO_CSRF_ORIGINS", "value": "https://*.run.app"},
                {"name": "DJANGO_SUPERUSER_USERNAME", "value": "jaime"},
                {"name": "DJANGO_SUPERUSER_EMAIL", "value": "js@qhhe.net"},
                _secret_env("DJANGO_SECRET_KEY", sec_key),
                _secret_env("DATABASE_URL", sec_dburl),
                _secret_env("DJANGO_SUPERUSER_PASSWORD", sec_admin),
            ],
            "volume_mounts": [{"name": "cloudsql", "mount_path": "/cloudsql"}],
        }],
        "volumes": [{"name": "cloudsql",
                     "cloud_sql_instance": {"instances": [sql_conn]}}],
    },
    opts=pulumi.ResourceOptions(depends_on=[apis["run.googleapis.com"]]),
)

# Public ingress; Django's login is the gate for the dev milestone (IAP: 6b).
gcp.cloudrunv2.ServiceIamMember(
    "console-public-invoker",
    project=project, location=region, name=console.name,
    role="roles/run.invoker", member="allUsers",
)

orchestrator_job = gcp.cloudrunv2.Job(
    "suite-orchestrator",
    project=project,
    location=region,
    name="suite-orchestrator",
    template={"template": {
        "service_account": runner_sa.email,
        "timeout": "3600s",
        "max_retries": 0,  # a failed client run is reviewed, never blind-retried
        "containers": [{
            "image": f"{_img}/orchestrator:latest",
            "resources": {"limits": {"cpu": "1", "memory": "1Gi"}},
            "envs": [
                {"name": "GCP_PROJECT_ID", "value": project},
                {"name": "SUITE_BACKEND", "value": "gcp"},
                {"name": "SUITE_LLM_PROVIDER", "value": "gemini"},
            ],
        }],
    }},
    opts=pulumi.ResourceOptions(depends_on=[apis["run.googleapis.com"]]),
)

# --- Outputs ----------------------------------------------------------------
pulumi.export("web_url", console.uri)
pulumi.export("artifact_repo_url", pulumi.Output.concat(
    region, "-docker.pkg.dev/", project, "/", repo.repository_id))
pulumi.export("firestore_database", firestore_db.name)
pulumi.export("runner_sa_email", runner_sa.email)
pulumi.export("topics", list(topics.keys()))
