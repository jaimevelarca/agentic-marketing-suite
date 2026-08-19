"""Agent 4.3 — Web + Landing Pages (Layer 4 — Production).

Built on `suite/agents/base.py`. Turns an approved campaign and its briefed
content into production-ready landing pages: ordered sections + ES-MX copy, the
conversion form + single primary CTA, SEO/technical scaffolding, and a
disciplined set of A/B test variants. Its output — the `page_assets` memory
block — is read by Layer 5 (5.1 Campaign Launcher points paid traffic at these
pages; 5.3 Lead Capture wires the form to the CRM) and Layer 6 (6.1 measures the
variants; 6.3 picks the winners).

The production system prompt is the versioned asset
`suite/agents/layer4/prompts/web_landing_pages_system.txt` (the machine source of
truth; DEL-28 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  campaign_registry (2.2), audience_segments (1.2), copy_assets (4.1);
  optionally client_profile for constraints / brand voice / visual identity.
Writes: page_assets. Human gate: full review (default pending_review — a public,
conversion-critical artifact is never auto-published).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 4.3) and
`agents/4.3-web_landing_pages.md`. Model = Sonnet (primary generation); system
prompt cached; ~$0.125/run, T1 $0.00 / T2 $0.25 / T3 $0.50.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
_UPSTREAM_BLOCKS = ("campaign_registry", "audience_segments", "copy_assets")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent43(BaseAgent):
    """Web + Landing Pages — produces the `page_assets` block (pages: sections +
    copy + conversion form + SEO + A/B variants) for a campaign, from the
    campaign registry + audience segments + approved copy assets."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## LANDING PAGE BUILD REQUEST — AGENT 4.3\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("campaign_id"):
            parts.append(f"campaign_id (requested): {payload['campaign_id']}\n")
        if payload.get("page_goal"):
            parts.append(f"page_goal (requested): {payload['page_goal']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)
        # Optional client_profile context (constraints / brand voice / visual identity / language).
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))

        if "campaign_registry" not in present:
            parts.append(
                "### MISSING REQUIRED INPUT\n"
                "campaign_registry not provided. Per the prompt rules, emit a minimal "
                "valid page_assets object with gate_status='blocked' and explain in "
                "build_notes / OUTPUT 3. Do not invent a campaign.\n"
            )
        if "copy_assets" not in present:
            parts.append(
                "### NOTE\n"
                "copy_assets not provided. You may still build the page by authoring all "
                "copy fresh, but set every section's source_copy_ref to null and flag in "
                "build_notes / OUTPUT 3 that no approved copy was available.\n"
            )

        parts.append(
            "\n---\nBuild the landing page(s) per the system prompt: one page per campaign "
            "objective with a single primary CTA, ordered sections (reuse approved copy where "
            "present), a short consented form, SEO/technical scaffolding, and 1-3 single-element "
            "A/B tests. Keep the summary footing to what you built, and produce the three "
            "required outputs."
        )
        return "\n".join(parts)


AGENT = Agent43(
    agent_id="4.3",
    prompt_asset="agents/layer4/prompts/web_landing_pages_system.txt",
    model=settings.model_primary,
    max_tokens=32000,   # raised from 16000 — large landing-page specs truncated the JSON mid-block on real client data
    schema_name="page_assets",
    memory_block="page_assets",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks campaign_registry / audience_segments / copy_assets (injected by the
    orchestrator under their block names); optional client_profile, campaign_id,
    page_goal."""
    return AGENT.run(payload)
