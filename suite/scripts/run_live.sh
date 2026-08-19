#!/usr/bin/env bash
# Run one agent (or the full pipeline) LIVE: Claude via the Anthropic API +
# Cloud SQL/Firestore/Pub-Sub. (To use Vertex instead, set SUITE_LLM_PROVIDER=vertex
# — that needs the Anthropic EULAs accepted in Vertex Model Garden + Vertex quota.)
#
# Prereqs (one-time, human):
#   - ANTHROPIC_API_KEY available: either exported in the env, or stored in Secret
#     Manager as `anthropic-api-key` (this script pulls it if the env var is unset).
#   - Billing enabled + (recommended) a monthly budget alert.
#   - gcloud ADC present with quota project set to the deploy project.
#
# Usage:
#   suite/scripts/run_live.sh                 # Agent 1.1 smoke test on Acme Co.
#   AGENT_ID=1.2 suite/scripts/run_live.sh    # a different single agent
#   AGENT_ID= AUTO_APPROVE=true suite/scripts/run_live.sh   # full pipeline
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-ai-mkt-suite}"
REGION="${GCP_REGION:-us-central1}"
INSTANCE="${SQL_INSTANCE:-ai-mkt-pg}"
PROXY_PORT="${SQL_PROXY_PORT:-5433}"
CLIENT_ID="${CLIENT_ID:-acme}"
AGENT_ID_DEFAULT="1.1"
AGENT_ID="${AGENT_ID-$AGENT_ID_DEFAULT}"   # set AGENT_ID= (empty) to run the full pipeline
INPUT_FILE="${INPUT_FILE:-suite/inputs/acme.json}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# --- DB password from Secret Manager (never hard-coded) ----------------------
export PGPASSWORD="$(gcloud secrets versions access latest --secret=db-app-password --project="$PROJECT")"

# --- cloud-sql-proxy (start if not already listening on $PROXY_PORT) ----------
PROXY_PID=""
if ! pg_isready -h 127.0.0.1 -p "$PROXY_PORT" >/dev/null 2>&1; then
  echo "Starting cloud-sql-proxy on 127.0.0.1:$PROXY_PORT ..."
  cloud-sql-proxy "$PROJECT:$REGION:$INSTANCE" --port "$PROXY_PORT" &
  PROXY_PID=$!
  trap '[ -n "$PROXY_PID" ] && kill "$PROXY_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 15); do pg_isready -h 127.0.0.1 -p "$PROXY_PORT" >/dev/null 2>&1 && break; sleep 1; done
fi

# --- live runtime switches ----------------------------------------------------
export SUITE_LLM_PROVIDER="${SUITE_LLM_PROVIDER:-anthropic}"
export SUITE_BACKEND=gcp
# Anthropic API key: use the env var if set, else fetch from Secret Manager
# (same pattern as PGPASSWORD above). Only needed for the anthropic provider.
if [ "$SUITE_LLM_PROVIDER" = "anthropic" ]; then
  export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$(gcloud secrets versions access latest --secret=anthropic-api-key --project="$PROJECT")}"
fi
export SQL_PROXY_PORT="$PROXY_PORT"
export GCP_PROJECT_ID="$PROJECT"
export CLIENT_ID
export AGENT_ID
export INPUTS_JSON="$(cat "$INPUT_FILE")"
[ -n "${AUTO_APPROVE:-}" ] && export AUTO_APPROVE

echo "→ LIVE run: agent='${AGENT_ID:-<full pipeline>}' client='$CLIENT_ID' provider=$SUITE_LLM_PROVIDER backend=gcp"
PYTHONPATH=suite python -m orchestration.job_entrypoint
