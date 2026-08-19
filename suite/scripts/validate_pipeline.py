"""Full-pipeline live-validation harness for the Digital Marketing AI Suite.

Runs all 19 agents in dependency order (provider chosen by SUITE_LLM_PROVIDER —
'fixture' for a free dry-run of the harness itself, 'anthropic' for the real
paid validation pass), then for EACH agent:
  - saves its raw OUTPUT 1/2/3 + the parsed/validated block to suite/runs/<ts>/
  - enumerates EVERY schema violation (Draft7Validator.iter_errors), so one run
    surfaces the complete defect list per agent (the loop that made 1.1 cheap).

This is the durable home for dev/validation run artifacts (the 'where do results
go' answer): suite/runs/ — gitignored, in-repo, Drive-synced.

Usage:
  SUITE_LLM_PROVIDER=fixture python suite/scripts/validate_pipeline.py     # free dry-run
  ANTHROPIC_API_KEY=... SUITE_LLM_PROVIDER=anthropic python suite/scripts/validate_pipeline.py
"""
from __future__ import annotations

import os
import re
import sys
import json
import pathlib
import datetime

os.environ.setdefault("SUITE_LLM_PROVIDER", "fixture")
os.environ.setdefault("SUITE_BACKEND", "memory")

_SUITE = pathlib.Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))

_JSON_BLOCK = re.compile(r"```json\n([\s\S]+?)\n```")


def _parse_output_1(outputs: dict) -> dict | None:
    m = _JSON_BLOCK.search(outputs.get("output_1", "") or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def main() -> int:
    from orchestration.pipeline import run_pipeline, PIPELINE
    from infra import clients
    from infra.config import settings
    import jsonschema

    provider = settings.llm_provider
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    input_file = pathlib.Path(os.getenv("INPUT_FILE", str(_SUITE / "inputs" / "acme_test.json")))
    inputs = json.loads(input_file.read_text(encoding="utf-8"))
    client_id = inputs.get("client_id", "acme-test")

    ts = os.getenv("RUN_TS") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs_dir = _SUITE / "runs" / f"{ts}_{provider}_{client_id}"
    runs_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print(f" FULL-PIPELINE VALIDATION — provider={provider} backend={settings.backend}")
    print(f" input={input_file.name}  client_id={client_id}")
    print(f" artifacts -> {runs_dir}")
    print("=" * 78)

    schema_by_block = {s.id: s for s in PIPELINE}
    res = run_pipeline(client_id, inputs, auto_approve=True, capture_results=True)

    report = []
    for entry in res["transcript"]:
        aid = entry["agent"]
        step = schema_by_block[aid]
        result = entry.get("_result")
        rec = {"agent": aid, "name": entry["name"], "layer": entry["layer"],
               "block": step.block, "valid": entry.get("valid"), "error": entry.get("error"),
               "schema_errors": []}

        if result is not None:
            adir = runs_dir / aid
            adir.mkdir(exist_ok=True)
            (adir / "outputs_full.json").write_text(
                json.dumps(result.outputs, indent=2, ensure_ascii=False), encoding="utf-8")
            obj = result.structured if result.structured is not None else _parse_output_1(result.outputs)
            if obj is not None:
                obj = dict(obj)
                obj["client_id"] = client_id  # mirror inject_client_id
                (adir / "block.json").write_text(
                    json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
                # enumerate ALL schema violations for this agent
                try:
                    schema = clients.load_schema(_schema_name(step))
                except Exception:
                    schema = None
                if schema is not None:
                    v = jsonschema.Draft7Validator(schema)
                    for e in sorted(v.iter_errors(obj), key=lambda e: list(e.absolute_path)):
                        loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
                        rec["schema_errors"].append(f"{loc}: {e.message[:120]}")
        report.append(rec)

    (runs_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- console summary ----
    print(f"\n{'agent':6} {'layer':5} {'valid':5} {'#errs':5}  block / first error")
    print("-" * 78)
    n_ok = 0
    for r in report:
        n = len(r["schema_errors"])
        ok = r["valid"] and n == 0
        n_ok += 1 if ok else 0
        flag = "ok " if ok else "FAIL"
        first = "" if ok else (r["error"] or (r["schema_errors"][0] if r["schema_errors"] else "see report"))
        print(f"{r['agent']:6} {r['layer']:5} {str(bool(r['valid'])):5} {n:<5} {flag} {r['block']}  {first[:60]}")
    print("-" * 78)
    print(f" {n_ok}/{len(report)} agents fully valid. Full report: {runs_dir/'report.json'}")
    return 0 if n_ok == len(report) else 1


def _schema_name(step) -> str:
    """Resolve the schema name an agent validates against (defaults to its block,
    with the 1.1 special-case)."""
    import importlib
    agent = getattr(importlib.import_module(step.module), "AGENT", None)
    return getattr(agent, "schema_name", None) or step.block


if __name__ == "__main__":
    raise SystemExit(main())
