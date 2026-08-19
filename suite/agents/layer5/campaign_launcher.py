"""Agent 5.1 — Campaign Launcher (Layer 5 — Distribution).

Built on `suite/agents/base.py`. Turns an approved marketing campaign and its
production assets into a ready-to-launch paid-media SETUP SPEC across Meta /
Google / TikTok Ads: per-platform campaign -> ad sets -> ads, budgets and
schedules, targeting, optimization/bid strategy, conversion tracking, and the
creative-to-landing-page wiring. Its output — the `ad_campaign_log` memory
block — is read by Layer 6 (6.1 Performance Analytics reconciles spend / ROAS /
CPL against the kpi_contracts; 6.3 Optimization Engine reallocates within bounds).

FINANCIAL-AUTH gate: this agent NEVER spends money and NEVER launches. It emits
a draft with gate_status='pending_review' and authorization.status=
'awaiting_authorization'; a human operator must grant financial authorization
before any spec is pushed to a platform. The agent never calls a platform API.

The production system prompt is the versioned asset
`suite/agents/layer5/prompts/campaign_launcher_system.txt` (the machine source of
truth; DEL-30 is its human-readable wrapper).

Reads (memory blocks injected by the orchestrator under their block-name keys):
  campaign_registry (2.2), copy_assets (4.1), page_assets (4.3),
  active_strategy (2.1); optionally client_profile + visual_assets.
Writes: ad_campaign_log. Human gate: financial authorization (default
pending_review — paid media is never auto-launched).

Cost & Runtime Profile: see `project/specs/AGENT_COST_MODEL.md` (row 5.1) and
`agents/5.1-campaign_launcher.md`. Model = Sonnet (primary generation); system
prompt cached; ~$0.059/run, T1 $0.00 / T2 $0.12 / T3 $0.24.
"""
from __future__ import annotations

import json

from agents.base import BaseAgent
from infra.config import settings

# Upstream memory blocks this agent reads. Injected under these exact keys.
_UPSTREAM_BLOCKS = ("campaign_registry", "active_strategy", "copy_assets", "page_assets")

# Truncate any single injected JSON blob so a large memory block can't blow the
# user turn (and the input-token cost) out of proportion.
_MAX_BLOCK_CHARS = 24000


def _block(name: str, obj) -> str:
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(body) > _MAX_BLOCK_CHARS:
        body = body[:_MAX_BLOCK_CHARS] + "\n... [truncated]"
    return f"### MEMORY BLOCK: {name}\n{body}\n"


class Agent51(BaseAgent):
    """Campaign Launcher — produces the `ad_campaign_log` block (per-platform
    Meta/Google/TikTok campaign setup specs: budgets, schedules, targeting, ad
    sets, creative-to-landing wiring + budget reconciliation), awaiting human
    financial authorization. Builds the spec; never spends or launches."""

    def build_user_turn(self, payload: dict) -> str:
        parts = ["## PAID-MEDIA CAMPAIGN SETUP REQUEST — AGENT 5.1\n"]
        parts.append(f"client_id: {payload.get('client_id', 'UNKNOWN')}\n")
        if payload.get("campaign_id"):
            parts.append(f"campaign_id (requested): {payload['campaign_id']}\n")
        if payload.get("platforms"):
            parts.append(f"platforms (requested): {payload['platforms']}\n")

        present = []
        for name in _UPSTREAM_BLOCKS:
            val = payload.get(name)
            if val:
                parts.append(_block(name, val))
                present.append(name)
        # Optional context: client_profile (constraints / markets / budget) and
        # visual_assets references for ad creatives.
        if payload.get("client_profile"):
            parts.append(_block("client_profile", payload["client_profile"]))
        if payload.get("visual_assets"):
            parts.append(_block("visual_assets", payload["visual_assets"]))

        if "campaign_registry" not in present:
            parts.append(
                "### MISSING REQUIRED INPUT\n"
                "campaign_registry not provided. Per the prompt rules, emit a minimal "
                "valid ad_campaign_log object with gate_status='blocked', empty "
                "platform_campaigns, a zeroed budget_reconciliation, and "
                "authorization.status='awaiting_authorization'. Explain in setup_notes / "
                "OUTPUT 3. Do not invent a campaign or a budget.\n"
            )
        if "active_strategy" not in present:
            parts.append(
                "### NOTE\n"
                "active_strategy not provided. Use the per-campaign budget_usd / "
                "channel_budget from campaign_registry as the spending envelope and KPI "
                "targets, and flag in setup_notes / OUTPUT 3 that the binding strategy was "
                "not available. Do not exceed the campaign budget.\n"
            )
        if "page_assets" not in present:
            parts.append(
                "### NOTE\n"
                "page_assets not provided. Conversion ad sets require an approved landing "
                "page: set landing_page_ref=null, do NOT invent a URL, raise a coherence_flag, "
                "and consider blocking conversion-objective platform campaigns.\n"
            )

        parts.append(
            "\n---\nBuild the paid-media setup spec per the system prompt: select the "
            "campaign + spending envelope, choose platforms and split the budget (never "
            "exceeding the authorized budget), structure each platform campaign into "
            "1-3 well-funded ad sets with targeting + optimization + bid strategy, wire "
            "each ad to approved copy_assets and page_assets, reconcile the budget so the "
            "math foots, and frame the financial authorization. NEVER launch and NEVER "
            "self-authorize: gate_status='pending_review', authorization awaiting human. "
            "Produce the three required outputs."
        )
        return "\n".join(parts)


AGENT = Agent51(
    agent_id="5.1",
    prompt_asset="agents/layer5/prompts/campaign_launcher_system.txt",
    model=settings.model_primary,
    max_tokens=16000,
    schema_name="ad_campaign_log",
    memory_block="ad_campaign_log",
)


def run(payload: dict):
    """Convenience entrypoint. `payload` keys: client_id; the upstream memory
    blocks campaign_registry / active_strategy / copy_assets / page_assets
    (injected by the orchestrator under their block names); optional
    client_profile, visual_assets, campaign_id, platforms."""
    return AGENT.run(payload)
