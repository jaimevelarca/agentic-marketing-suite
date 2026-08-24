# Cloud Run Job image for the Agentic Marketing Suite orchestrator.
# One image runs the ADK workflow (start / resume / status via
# orchestration.adk_entrypoint), args chosen per execution.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/suite

WORKDIR /app

# Dependencies first (better layer caching).
COPY pyproject.toml README.md ./
COPY suite ./suite
RUN pip install ".[adk]"

# Runtime assets the code reads by path: per-block JSON Schemas
# (clients.load_schema + the legacy DEL-17 registry).
COPY project/resources/schemas ./project/resources/schemas

# Production defaults; override per execution. Never bake secrets — Vertex
# Gemini authenticates via the runtime service account (ADC), no API key.
ENV SUITE_LLM_PROVIDER=gemini \
    SUITE_BACKEND=gcp \
    GCP_PROJECT_ID=agentic-marketing-suite \
    GCP_REGION=us-central1

ENTRYPOINT ["python", "-m", "orchestration.adk_entrypoint"]
CMD ["--help"]
