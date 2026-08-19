"""Offline end-to-end demo of the Digital Marketing AI Suite.

Runs the full onboarding -> intelligence -> strategy -> planning -> production ->
distribution -> analytics pipeline with the canned per-agent fixtures and an
in-process memory store. NO GCP project and NO Anthropic EULA required — this is
the MVP "it actually runs" proof while the live Vertex gates (I-01/I-02) are
deferred.

    python -m orchestration.demo                # full pipeline, auto-approve gates
    python -m orchestration.demo --stop-after L1  # Phase-1 milestone only
    python -m orchestration.demo --no-approve   # halt at the first human gate

(Run from the suite/ dir, or `PYTHONPATH=suite python -m orchestration.demo`.)
"""
from __future__ import annotations

import os
import sys
import pathlib

# Force offline mode unless the caller already chose a provider/backend. Must be
# set BEFORE importing anything that reads infra.config.settings.
os.environ.setdefault("SUITE_LLM_PROVIDER", "fixture")
os.environ.setdefault("SUITE_BACKEND", "memory")

_SUITE = pathlib.Path(__file__).resolve().parents[1]
if str(_SUITE) not in sys.path:
    sys.path.insert(0, str(_SUITE))

# Minimal seed onboarding inputs for the Acme Co. pilot. In fixture mode the
# canned outputs drive the run; these just exercise each agent's build_user_turn.
SEED_INPUTS = {
    "quick_start_form": {
        "name": "the AI Marketing Suite vendor",
        "website": "https://www.acme.com.mx",
        "industry": "technology_consulting",
        "objective": "Sign 5 private-education pilot clients in Mexico in 90 days",
        "markets": ["Mexico", "Colombia", "Dominican Republic", "Puerto Rico"],
    },
    "scraper_output": {"pages": ["/", "/servicios"], "detected_offer": "Digital Marketing AI Suite"},
    "competitor_list": ["agency-x", "agency-y"],
    "inbound_leads": [],
}


def main(argv: list[str]) -> int:
    stop_after = None
    auto_approve = True
    if "--stop-after" in argv:
        stop_after = argv[argv.index("--stop-after") + 1]
    if "--no-approve" in argv:
        auto_approve = False

    from orchestration.pipeline import run_pipeline, PIPELINE
    from infra import clients

    clients.reset_memory_store()
    client_id = "acme-co"

    print("=" * 74)
    print(" Digital Marketing AI Suite — OFFLINE end-to-end run (fixtures + memory)")
    print(f" client: {client_id} | agents: {len(PIPELINE)} | "
          f"auto-approve gates: {auto_approve}" + (f" | stop after {stop_after}" if stop_after else ""))
    print("=" * 74)

    def on_event(e: dict) -> None:
        status = "OK " if e.get("valid") else "ERR"
        gate = e.get("gate_status", "-")
        line = f"  [{e['layer']}] {e['agent']:>3} {e['name']:<26} {status} gate={gate}"
        if e.get("blocked_downstream"):
            line += "  (awaiting human gate — downstream paused)"
        if e.get("error"):
            line += f"  ! {e['error']}"
        print(line)

    res = run_pipeline(client_id, SEED_INPUTS, auto_approve=auto_approve,
                       stop_after_layer=stop_after, on_event=on_event)

    valid = sum(1 for t in res["transcript"] if t.get("valid"))
    total = len(res["transcript"])
    print("-" * 74)
    print(f" Memory blocks produced ({len(res['memory'])}): {', '.join(sorted(res['memory']))}")
    print(f" Agents valid: {valid}/{total}")
    rq = len(clients.MEMORY_STORE["review_queue"])
    pub = len(clients.MEMORY_STORE["published"])
    print(f" Review-queue docs: {rq} | Pub/Sub events: {pub}")
    print("=" * 74)

    # Non-zero exit if any agent errored (e.g. a fixture/agent still missing).
    return 0 if valid == total else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
