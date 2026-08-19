# Cloud Run Job image for the Digital Marketing AI Suite (ADR-04).
# One image runs any agent (or the whole pipeline) via orchestration.job_entrypoint,
# selected at invocation time by the CLIENT_ID / AGENT_ID env vars.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/suite

WORKDIR /app

# Dependencies first (better layer caching).
COPY pyproject.toml README.md ./
COPY suite ./suite
RUN pip install .

# Runtime assets the code reads by path (prompt assets ship inside suite/):
#   - per-block JSON Schemas, incl. the DEL-17 client_profile schema, all under
#     project/resources/schemas (clients.load_schema + the legacy registry).
COPY project/resources/schemas ./project/resources/schemas

# Production defaults; override per-invocation. Model backbone = Claude on the
# Anthropic first-party API (validated path; Vertex is a one-env-var flip to
# SUITE_LLM_PROVIDER=vertex once Vertex Claude quota is granted). NEVER bake
# secrets — Cloud Run injects ANTHROPIC_API_KEY + the DB password from Secret
# Manager at runtime (see deploy/cloudbuild.yaml).
ENV SUITE_LLM_PROVIDER=anthropic \
    SUITE_BACKEND=gcp \
    GCP_PROJECT_ID=ai-mkt-suite \
    GCP_REGION=us-central1

ENTRYPOINT ["python", "-m", "orchestration.job_entrypoint"]
