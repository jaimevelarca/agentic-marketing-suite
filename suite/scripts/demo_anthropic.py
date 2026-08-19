"""LIVE demo — Agent 1.1 (Business Diagnostics) on real Acme Co. data, via the
Anthropic first-party API (SUITE_LLM_PROVIDER=anthropic), in-memory backend.

This is the zero-infrastructure live smoke test: the ONLY external dependency is
ANTHROPIC_API_KEY. No Vertex quota, no cloud-sql-proxy, no Secret Manager. It
proves the real model path — real input -> real Claude (Sonnet 4.6) -> schema-
valid client_profile — while Vertex base-model quota is still being granted.

Run:
    ANTHROPIC_API_KEY=sk-ant-... python suite/scripts/demo_anthropic.py
    AGENT_ID=1.1 CLIENT_ID=acme ... (overridable)

To also persist to Cloud SQL/Firestore (full live path minus Vertex), use
run_live.sh with SUITE_LLM_PROVIDER=anthropic instead.
"""
from __future__ import annotations

import os
import sys
import json
import pathlib

# Provider/backend switches MUST be set before importing infra.config.
os.environ["SUITE_LLM_PROVIDER"] = "anthropic"
os.environ.setdefault("SUITE_BACKEND", "memory")

_SUITE = pathlib.Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))


def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set — export it and re-run.", file=sys.stderr)
        return 2

    from orchestration.pipeline import PIPELINE, _load_run
    from infra.config import settings

    client_id = os.getenv("CLIENT_ID", "acme")
    agent_id = os.getenv("AGENT_ID", "1.1")
    input_file = pathlib.Path(os.getenv("INPUT_FILE", str(_SUITE / "inputs" / "acme.json")))

    step = next((s for s in PIPELINE if s.id == agent_id), None)
    if step is None:
        print(f"unknown AGENT_ID={agent_id}", file=sys.stderr)
        return 2

    inputs = json.loads(input_file.read_text(encoding="utf-8"))
    payload = {"client_id": client_id, **inputs}

    print("=" * 72)
    print(f" LIVE demo — agent {agent_id} · client '{client_id}'")
    print(f" provider=anthropic (first-party API) · backend={settings.backend} · model={settings.model_primary}")
    print(f" input: {input_file.name}")
    print("=" * 72)

    result = _load_run(step.module)(payload)

    # Always dump the full raw outputs for offline inspection (no re-run needed to debug).
    dump = pathlib.Path("/tmp") / f"agent_{agent_id}_last_outputs.json"
    dump.write_text(json.dumps(result.outputs, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n→ valid={result.valid}  block='{step.block}'  error={result.error}")
    print(f"  full raw outputs saved to: {dump}\n")
    if result.structured is not None:
        print("--- validated structured output (the real model-generated block) ---")
        print(json.dumps(result.structured, indent=2, ensure_ascii=False))
    else:
        # Show the parseable JSON (full) so the failing field is visible.
        obj = None
        from agents.base import BaseAgent
        obj = BaseAgent.extract_json(result.outputs.get("output_1", ""))
        print("--- parsed OUTPUT 1 JSON (full) ---")
        print(json.dumps(obj, indent=2, ensure_ascii=False) if obj is not None
              else result.outputs.get("output_1", "")[:4000])
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
