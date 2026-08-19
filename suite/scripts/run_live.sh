#!/usr/bin/env bash
# Run one agent (or the full pipeline) LIVE against GCP: Firestore + Pub/Sub
# backend, LLM per SUITE_LLM_PROVIDER (anthropic | vertex; gemini arrives in
# roadmap Phase 3).
#
# Prereqs (one-time, human):
#   - gcloud ADC present with quota project = the target project.
#   - For the anthropic provider: ANTHROPIC_API_KEY exported, or stored in
#     Secret Manager as `anthropic-api-key` (this script pulls it if unset).
#
# Usage:
#   suite/scripts/run_live.sh                 # Agent 1.1 smoke test on Acme Co.
#   AGENT_ID=1.2 suite/scripts/run_live.sh    # a different single agent
#   AGENT_ID= AUTO_APPROVE=true suite/scripts/run_live.sh   # full pipeline
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-agentic-marketing-suite}"
CLIENT_ID="${CLIENT_ID:-acme}"
AGENT_ID_DEFAULT="1.1"
AGENT_ID="${AGENT_ID-$AGENT_ID_DEFAULT}"   # set AGENT_ID= (empty) to run the full pipeline
INPUT_FILE="${INPUT_FILE:-suite/inputs/acme.json}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# --- live runtime switches ----------------------------------------------------
export SUITE_LLM_PROVIDER="${SUITE_LLM_PROVIDER:-anthropic}"
export SUITE_BACKEND=gcp
# Anthropic API key: use the env var if set, else fetch from Secret Manager.
if [ "$SUITE_LLM_PROVIDER" = "anthropic" ]; then
  export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$(gcloud secrets versions access latest --secret=anthropic-api-key --project="$PROJECT")}"
fi
export GCP_PROJECT_ID="$PROJECT"
export CLIENT_ID
export AGENT_ID
export INPUTS_JSON="$(cat "$INPUT_FILE")"
[ -n "${AUTO_APPROVE:-}" ] && export AUTO_APPROVE

echo "→ LIVE run: agent='${AGENT_ID:-<full pipeline>}' client='$CLIENT_ID' provider=$SUITE_LLM_PROVIDER backend=gcp"
PYTHONPATH=suite python -m orchestration.job_entrypoint
