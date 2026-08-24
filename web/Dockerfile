# Cloud Run service image for the Django review console.
# Build context = repo root:  gcloud builds submit --config web/cloudbuild.yaml
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/suite

WORKDIR /app

COPY pyproject.toml README.md ./
COPY suite ./suite
RUN pip install ".[adk,web]"

COPY project/resources/schemas ./project/resources/schemas
COPY web ./web

ENV SUITE_LLM_PROVIDER=gemini \
    SUITE_BACKEND=gcp \
    GCP_PROJECT_ID=agentic-marketing-suite \
    GCP_REGION=us-central1 \
    DJANGO_DEBUG=0 \
    PORT=8080

ENTRYPOINT ["/app/web/entrypoint.sh"]
