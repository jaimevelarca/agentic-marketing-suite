"""Agentic Marketing Suite — project infrastructure.

Everything in the GCP project is managed here except:
  - the project itself (created under folder 274831265727)
  - the state bucket gs://agentic-marketing-suite-pulumi-state
See infra/README.md for bootstrap and operating instructions.
"""
import pulumi
import pulumi_gcp as gcp
import pulumi_random as random

# --- Stack Configuration ---------------------------------------------------
gcp_cfg = pulumi.Config("gcp")
project = gcp_cfg.require("project")
region = gcp_cfg.require("region")

app_cfg = pulumi.Config()
stack = pulumi.get_stack()
project_number = app_cfg.get("projectNumber") or "54069477296"
budget_amount = app_cfg.get("budgetAmount") or "2000"
is_artifact_host = app_cfg.get_bool("isArtifactHost") if app_cfg.get("isArtifactHost") is not None else (stack == "dev")
artifact_host_project = app_cfg.get("artifactHostProject") or "agentic-marketing-suite"

BILLING_ACCOUNT = "01624A-839C44-1DB4D6"
IAP_USER = "user:js@qhhe.net"
IAP_JUDGES = [
    "user:testing@devpost.com",
    "user:cloudhackathons@google.com",
]

# Images: prefer resolved immutable digest/tag from stack config, else default
_default_img_base = f"{region}-docker.pkg.dev/{artifact_host_project}/suite"
console_image = app_cfg.get("consoleImage") or f"{_default_img_base}/console:dev"
orchestrator_image = app_cfg.get("orchestratorImage") or f"{_default_img_base}/orchestrator:dev"

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
    "iap.googleapis.com",       # direct Cloud Run IAP (Phase 6b)
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
# Central repository hosted in the dev project; other stacks/projects read from it.
if is_artifact_host:
    repo = gcp.artifactregistry.Repository(
        "suite",
        project=project,
        location=region,
        repository_id="suite",
        format="DOCKER",
        description="Container images for the Agentic Marketing Suite",
        opts=pulumi.ResourceOptions(depends_on=[apis["artifactregistry.googleapis.com"]]),
    )
    artifact_repo_url = repo.repository_id.apply(
        lambda rid: f"{region}-docker.pkg.dev/{project}/{rid}"
    )
else:
    artifact_repo_url = pulumi.Output.from_input(f"{region}-docker.pkg.dev/{artifact_host_project}/suite")

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

# --- Budget alert (configured per stack, e.g. MXN 2,000 in dev, MXN 4,000 in prod)
budget = gcp.billing.Budget(
    "monthly-budget",
    billing_account=BILLING_ACCOUNT,
    display_name=f"{project} monthly",
    budget_filter={
        "projects": [f"projects/{project_number}"],
    },
    amount={"specified_amount": {"currency_code": "MXN", "units": budget_amount}},
    threshold_rules=[
        {"threshold_percent": 0.5},
        {"threshold_percent": 0.9},
        {"threshold_percent": 1.0},
    ],
    opts=pulumi.ResourceOptions(depends_on=[apis["billingbudgets.googleapis.com"]]),
)

# --- Cloud Build (default compute SA needs source + push + logs) ------------
build_sa = f"serviceAccount:{project_number}-compute@developer.gserviceaccount.com"
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

# Pulumi Passphrase Secret Container (Value seeded manually from vault out-of-band)
sec_passphrase = gcp.secretmanager.Secret(
    "pulumi-passphrase",
    project=project,
    secret_id="pulumi-passphrase",
    replication={"auto": {}},
    opts=pulumi.ResourceOptions(depends_on=[apis["secretmanager.googleapis.com"]]),
)

# --- Cloud SQL (Django auth/admin/sessions ONLY — domain data is Firestore) --
sql_instance = gcp.sql.DatabaseInstance(
    "console-pg",
    project=project,
    name="console-pg",
    region=region,
    database_version="POSTGRES_16",
    deletion_protection=True,
    settings={
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

# --- Cross-project Artifact Registry permissions (for prod/non-host stacks) ---
if not is_artifact_host:
    # Grant Cloud Run service agent and SAs permission to pull images from host repo
    serverless_robot = f"serviceAccount:service-{project_number}@serverless-robot-prod.iam.gserviceaccount.com"
    for idx, member in enumerate([
        web_sa.email.apply(lambda e: f"serviceAccount:{e}"),
        runner_sa.email.apply(lambda e: f"serviceAccount:{e}"),
        pulumi.Output.from_input(serverless_robot),
    ]):
        gcp.artifactregistry.RepositoryIamMember(
            f"cross-project-ar-reader-{idx}",
            project=artifact_host_project,
            location=region,
            repository=f"projects/{artifact_host_project}/locations/{region}/repositories/suite",
            role="roles/artifactregistry.reader",
            member=member,
        )

# --- Cloud Run: console service + orchestrator job ---------------------------
def _secret_env(name: str, secret) -> dict:
    return {"name": name, "value_source": {
        "secret_key_ref": {"secret": secret.secret_id, "version": "latest"}}}

console = gcp.cloudrunv2.Service(
    "console",
    project=project,
    location=region,
    name="console",
    ingress="INGRESS_TRAFFIC_ALL",
    iap_enabled=True,
    template={
        "service_account": web_sa.email,
        "max_instance_request_concurrency": 40,
        "scaling": {"max_instance_count": 2},
        "containers": [{
            "image": console_image,
            "resources": {"cpu_idle": True,
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
    opts=pulumi.ResourceOptions(depends_on=[apis["run.googleapis.com"], apis["iap.googleapis.com"]]),
)

# Direct Cloud Run IAP: IAP service agent invokes Cloud Run; user accesses via IAP
iap_service_agent = f"serviceAccount:service-{project_number}@gcp-sa-iap.iam.gserviceaccount.com"
gcp.cloudrunv2.ServiceIamMember(
    "console-iap-invoker",
    project=project,
    location=region,
    name=console.name,
    role="roles/run.invoker",
    member=iap_service_agent,
    opts=pulumi.ResourceOptions(depends_on=[console]),
)

gcp.iap.WebCloudRunServiceIamMember(
    "console-iap-accessor",
    project=project,
    location=region,
    cloud_run_service_name=console.name,
    role="roles/iap.httpsResourceAccessor",
    member=IAP_USER,
    opts=pulumi.ResourceOptions(depends_on=[console, apis["iap.googleapis.com"]]),
)

for idx, judge_user in enumerate(IAP_JUDGES):
    gcp.iap.WebCloudRunServiceIamMember(
        f"console-iap-judge-{idx}",
        project=project,
        location=region,
        cloud_run_service_name=console.name,
        role="roles/iap.httpsResourceAccessor",
        member=judge_user,
        opts=pulumi.ResourceOptions(depends_on=[console, apis["iap.googleapis.com"]]),
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
            "image": orchestrator_image,
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

# --- Workload Identity Federation (WIF) for GitHub Actions CI/CD -------------
wif_pool = gcp.iam.WorkloadIdentityPool(
    "github-actions-pool",
    project=project,
    workload_identity_pool_id="github-actions",
    display_name="GitHub Actions Pool",
    description="Identity pool for GitHub Actions CI/CD workflows",
    opts=pulumi.ResourceOptions(depends_on=[apis["iamcredentials.googleapis.com"]]),
)

if stack == "prod":
    attribute_condition = (
        "assertion.repository == 'jaimevelarca/agentic-marketing-suite' && "
        "assertion.ref.startsWith('refs/tags/v')"
    )
else:
    attribute_condition = "assertion.repository == 'jaimevelarca/agentic-marketing-suite'"

wif_provider = gcp.iam.WorkloadIdentityPoolProvider(
    "github-actions-provider",
    project=project,
    workload_identity_pool_id=wif_pool.workload_identity_pool_id,
    workload_identity_pool_provider_id="github-actions-provider",
    display_name="GitHub Actions Provider",
    attribute_mapping={
        "google.subject": "assertion.sub",
        "attribute.actor": "assertion.actor",
        "attribute.repository": "assertion.repository",
        "attribute.repository_owner": "assertion.repository_owner",
        "attribute.ref": "assertion.ref",
    },
    attribute_condition=attribute_condition,
    oidc={"issuer_uri": "https://token.actions.githubusercontent.com"},
    opts=pulumi.ResourceOptions(depends_on=[wif_pool]),
)

deployer_sa = gcp.serviceaccount.Account(
    "pulumi-deployer",
    project=project,
    account_id="pulumi-deployer",
    display_name="Pulumi CI/CD Deployer (GitHub Actions)",
)

gcp.serviceaccount.IAMMember(
    "deployer-wif-binding",
    service_account_id=deployer_sa.name,
    role="roles/iam.workloadIdentityUser",
    member=pulumi.Output.all(project_number, wif_pool.workload_identity_pool_id).apply(
        lambda a: f"principalSet://iam.googleapis.com/projects/{a[0]}/locations/global/workloadIdentityPools/{a[1]}/attribute.repository/jaimevelarca/agentic-marketing-suite"
    ),
)

DEPLOYER_ROLES = [
    "roles/run.admin",
    "roles/cloudbuild.builds.editor",
    "roles/secretmanager.admin",
    "roles/secretmanager.secretAccessor",
    "roles/datastore.owner",
    "roles/cloudsql.admin",
    "roles/pubsub.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountUser",
    "roles/iam.serviceAccountAdmin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/storage.admin",
    "roles/logging.logWriter",
    "roles/logging.viewer",
    "roles/iap.admin",
    "roles/aiplatform.admin",
]
if is_artifact_host:
    DEPLOYER_ROLES.append("roles/artifactregistry.admin")

for role in DEPLOYER_ROLES:
    gcp.projects.IAMMember(
        f"deployer-{role.split('/')[-1]}",
        project=project,
        role=role,
        member=deployer_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )

# Grant deployer SA write access to the state bucket and cloudbuild bucket
gcp.storage.BucketIAMMember(
    "deployer-state-bucket-access",
    bucket="agentic-marketing-suite-pulumi-state",
    role="roles/storage.objectAdmin",
    member=deployer_sa.email.apply(lambda e: f"serviceAccount:{e}"),
)

if is_artifact_host:
    gcp.storage.BucketIAMMember(
        "deployer-cloudbuild-bucket-access",
        bucket=f"{project}_cloudbuild",
        role="roles/storage.admin",
        member=deployer_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )
else:
    gcp.artifactregistry.RepositoryIamMember(
        "deployer-host-ar-reader",
        project=artifact_host_project,
        location=region,
        repository=f"projects/{artifact_host_project}/locations/{region}/repositories/suite",
        role="roles/artifactregistry.reader",
        member=deployer_sa.email.apply(lambda e: f"serviceAccount:{e}"),
    )


# --- Outputs ----------------------------------------------------------------
pulumi.export("web_url", console.uri)
pulumi.export("artifact_repo_url", artifact_repo_url)
pulumi.export("firestore_database", firestore_db.name)
pulumi.export("runner_sa_email", runner_sa.email)
pulumi.export("topics", list(topics.keys()))
pulumi.export("deployed_console_image", console_image)
pulumi.export("deployed_orchestrator_image", orchestrator_image)
pulumi.export("wif_provider_name", wif_provider.name)
pulumi.export("deployer_sa_email", deployer_sa.email)
