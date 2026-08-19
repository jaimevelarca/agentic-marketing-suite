"""Cloud Run Job entrypoint for the Digital Marketing AI Suite (ADR-04).

In production each agent runs as its own Cloud Run Job invocation, triggered by a
Pub/Sub message and chained by Cloud Workflows (see deploy/workflows/). This is
the container entrypoint. It supports two modes via env:

  CLIENT_ID  (required)  — the client to process.
  AGENT_ID   (optional)  — run a SINGLE agent (the prod model): load its upstream
                           memory blocks from Cloud SQL, run it, persist its block,
                           queue the human gate. If unset, run the WHOLE pipeline
                           (useful for the pilot / a manual full cycle).
  INPUTS_JSON (optional) — raw onboarding inputs as a JSON string (mainly for 1.1).
  AUTO_APPROVE (optional, default "false") — only meaningful for full-pipeline mode.

Defaults to the production backends (Claude via Anthropic API + Cloud SQL/Firestore/
Pub-Sub); set SUITE_LLM_PROVIDER=fixture / SUITE_BACKEND=memory to dry-run a single
job locally.
"""
from __future__ import annotations

import os
import sys
import json
import pathlib

_SUITE = pathlib.Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))


def _run_single(agent_id: str, client_id: str, inputs: dict) -> int:
    from orchestration.pipeline import PIPELINE, _load_run
    from infra import clients

    step = next((s for s in PIPELINE if s.id == agent_id), None)
    if step is None:
        print(f"unknown AGENT_ID={agent_id}", file=sys.stderr)
        return 2

    payload: dict = {"client_id": client_id, **inputs}
    for blk in step.reads:
        val = clients.read_memory_block(client_id, blk)
        if val is not None:
            payload[blk] = val

    result = _load_run(step.module)(payload)
    print(json.dumps({
        "agent": agent_id, "client_id": client_id, "valid": result.valid,
        "block": step.block, "error": result.error,
    }))
    return 0 if result.valid else 1


def _run_full(client_id: str, inputs: dict, auto_approve: bool) -> int:
    from orchestration.pipeline import run_pipeline, PIPELINE
    res = run_pipeline(client_id, inputs, auto_approve=auto_approve)
    ran = len(res["transcript"])
    valid = sum(1 for t in res["transcript"] if t.get("valid"))
    flagged = ran - valid  # invalid blocks were routed to the human review queue
    print(json.dumps({
        "client_id": client_id, "blocks": sorted(res["memory"]),
        "agents_ran": ran, "expected": len(PIPELINE),
        "valid": valid, "flagged_for_review": flagged,
    }))
    # A completed pipeline is a SUCCESS even when some blocks are flagged for human
    # review — that is the designed gate behavior, not a job failure. Exit non-zero
    # only when the run was INCOMPLETE (an agent crashed and later layers never ran).
    return 0 if ran == len(PIPELINE) else 1


def main() -> int:
    client_id = os.getenv("CLIENT_ID")
    if not client_id:
        print("CLIENT_ID is required", file=sys.stderr)
        return 2
    inputs = json.loads(os.getenv("INPUTS_JSON", "{}"))
    agent_id = os.getenv("AGENT_ID")
    if agent_id:
        return _run_single(agent_id, client_id, inputs)
    auto_approve = os.getenv("AUTO_APPROVE", "false").lower() in ("1", "true", "yes")
    return _run_full(client_id, inputs, auto_approve)


if __name__ == "__main__":
    raise SystemExit(main())
