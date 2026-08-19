"""Export the 19 product agents as a platform-neutral bundle.

For each agent in the pipeline registry this writes, under `exports/agents/<id>_<slug>/`:
  - system_prompt.txt        the raw, human-editable system prompt asset
  - system_prompt.full.txt   the prompt actually sent in production = asset + the
                             schema-derived OUTPUT-1 structure appendix (use this
                             when the target platform can't enforce a JSON schema
                             natively, e.g. pasting into the Claude Console)
  - output_schema.json       the resolved JSON Schema for the agent's output block
                             (use as a tool input_schema / structured-output spec)
  - config.json              id, name, layer, model, model_tier, max_tokens,
                             memory_block, reads, gate

…and a top-level `exports/manifest.json` describing the whole roster.

Run offline (no GCP / no API key):
    cd ai-mkt-suite
    PYTHONPATH=suite python -m scripts.export_agents
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from infra import clients, skeleton
from infra.config import settings
from orchestration.pipeline import PIPELINE

_ROOT = Path(__file__).resolve().parents[2]   # ai-mkt-suite/
_OUT = _ROOT / "exports"

_TIERS = {
    settings.model_primary: "primary",
    settings.model_routing: "routing",
    settings.model_deep: "deep",
}


def _slug(module: str) -> str:
    return module.rsplit(".", 1)[-1]


def main() -> None:
    agents_dir = _OUT / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "suite": "Digital Marketing AI Suite",
        "agent_count": len(PIPELINE),
        "model_tiers": {
            "primary": settings.model_primary,
            "routing": settings.model_routing,
            "deep": settings.model_deep,
        },
        "agents": [],
    }

    for step in PIPELINE:
        mod = importlib.import_module(step.module)
        agent = mod.AGENT
        slug = _slug(step.module)
        d = agents_dir / f"{step.id}_{slug}"
        d.mkdir(parents=True, exist_ok=True)

        raw_prompt = agent.system_prompt
        (d / "system_prompt.txt").write_text(raw_prompt + "\n", encoding="utf-8")

        schema = None
        if agent.schema_name:
            schema = clients.load_schema(agent.schema_name)
            (d / "output_schema.json").write_text(
                json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            schema_json = json.dumps(schema, sort_keys=True)
            full = raw_prompt + skeleton.output_structure_appendix(schema_json, agent.schema_name)
        else:
            full = raw_prompt
        (d / "system_prompt.full.txt").write_text(full + "\n", encoding="utf-8")

        cfg = {
            "id": step.id,
            "name": step.name,
            "layer": step.layer,
            "slug": slug,
            "model": agent.model,
            "model_tier": _TIERS.get(agent.model, "custom"),
            "max_tokens": agent.max_tokens,
            "memory_block": agent.memory_block,
            "schema_name": agent.schema_name,
            "reads": list(step.reads),
            "gate": step.gate,
            "human_gated": step.gate in __import__("orchestration.pipeline", fromlist=["GATED"]).GATED,
        }
        (d / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest["agents"].append({k: cfg[k] for k in ("id", "name", "layer", "model_tier", "memory_block", "gate")})

    (_OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"exported {len(PIPELINE)} agents → {_OUT.relative_to(_ROOT)}/")


if __name__ == "__main__":
    main()
