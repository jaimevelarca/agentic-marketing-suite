"""Pipeline orchestrator for the Digital Marketing AI Suite.

Runs the 6-layer / 19-agent flow in dependency order, passing each agent's
validated memory-block output forward to the agents that read it, and honoring
the human-gate map from `project/specs/ARCHITECTURE.md`.

Design:
  - Agent modules are imported LAZILY (only when an agent actually runs), so this
    module imports cleanly even before every agent is built, and a single missing
    agent degrades to a transcript error instead of crashing the whole run.
  - The orchestrator's own `memory` dict (built from each AgentResult.structured)
    is the source of truth passed downstream — independent of the persistence
    backend. With SUITE_LLM_PROVIDER=fixture + SUITE_BACKEND=memory the entire
    pipeline runs offline (no GCP, no Anthropic EULA) for dev/demo.
  - Human gates: in production a gated agent's output sits at gate_status
    "pending_review" until an operator approves it in the review UI; the next
    layer only reads APPROVED blocks. `auto_approve=True` simulates the operator
    for the offline demo so the full chain executes in one pass.

Production deployment (ADR-04): each AgentStep becomes a Cloud Run Job invocation
chained by Pub/Sub + Cloud Workflows (see deploy/workflows/). This module is the
single readable definition of the DAG that those artifacts mirror.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class AgentStep:
    id: str
    name: str
    layer: str
    module: str            # dotted path under the suite/ package, exposes run(payload)
    block: str             # memory block this agent writes
    reads: tuple[str, ...] = ()        # upstream blocks injected into its payload
    gate: str = "review"               # human-gate tier (ARCHITECTURE.md)
    exports: dict[str, str] = field(default_factory=dict)  # extra blocks pulled from nested output


# Gate tiers that require human approval before downstream layers may read the block.
GATED = {
    "review", "review-only", "binding", "financial-auth", "pre-client",
    "first-deploy", "full-review", "batch-review", "risk-tiered", "conditional",
}

# Dependency-ordered: every step's `reads` are produced by an earlier step.
PIPELINE: tuple[AgentStep, ...] = (
    # --- Layer 1: Intelligence ---
    AgentStep("1.1", "Business Diagnostics", "L1", "agents.layer1.agent_1_1", "client_profile", (), "review"),
    AgentStep("1.2", "Audience Intelligence", "L1", "agents.layer1.audience_intelligence", "audience_segments", ("client_profile",), "review"),
    AgentStep("1.3", "Competitive Intelligence", "L1", "agents.layer1.competitive_intelligence", "competitive_map", ("client_profile",), "review-only"),
    AgentStep("1.4", "Trend Radar", "L1", "agents.layer1.trend_radar", "trend_signals", ("client_profile",), "autonomous"),
    # --- Layer 2: Strategy ---
    AgentStep("2.1", "Strategy Orchestrator", "L2", "agents.layer2.strategy_orchestrator", "active_strategy",
              ("client_profile", "audience_segments", "competitive_map", "trend_signals"), "binding",
              {"kpi_contracts": "kpi_contracts"}),
    AgentStep("2.2", "Campaign Planner", "L2", "agents.layer2.campaign_planner", "campaign_registry",
              ("active_strategy", "client_profile", "audience_segments"), "review"),
    # --- Layer 3: Content Planning ---
    AgentStep("3.1", "Monthly Marketing Deck", "L3", "agents.layer3.monthly_marketing_deck", "content_plan",
              ("campaign_registry", "audience_segments", "active_strategy", "trend_signals"), "review"),
    AgentStep("3.2", "Content Scheduler", "L3", "agents.layer3.content_scheduler", "content_calendar",
              ("content_plan", "campaign_registry"), "review"),
    AgentStep("3.3", "Approval Workflow", "L3", "agents.layer3.approval_workflow", "approval_log",
              ("content_calendar",), "queue-mgr"),
    # --- Layer 4: Production ---
    AgentStep("4.1", "Copy + Prompt Engine", "L4", "agents.layer4.copy_prompt_engine", "copy_assets",
              ("content_calendar", "audience_segments", "competitive_map", "client_profile"), "risk-tiered"),
    AgentStep("4.2", "Visual Creative", "L4", "agents.layer4.visual_creative", "visual_assets",
              ("content_calendar", "copy_assets", "client_profile"), "batch-review"),
    AgentStep("4.3", "Web + Landing Pages", "L4", "agents.layer4.web_landing_pages", "page_assets",
              ("campaign_registry", "audience_segments", "copy_assets"), "full-review"),
    AgentStep("4.4", "Email / WhatsApp", "L4", "agents.layer4.email_whatsapp", "message_flows",
              ("audience_segments", "content_calendar"), "first-deploy"),
    # --- Layer 5: Distribution ---
    AgentStep("5.1", "Campaign Launcher", "L5", "agents.layer5.campaign_launcher", "ad_campaign_log",
              ("campaign_registry", "copy_assets", "page_assets", "active_strategy"), "financial-auth"),
    AgentStep("5.2", "Social Publisher", "L5", "agents.layer5.social_publisher", "publish_log",
              ("content_calendar", "copy_assets", "visual_assets"), "autonomous"),
    AgentStep("5.3", "Lead Capture + Nurture", "L5", "agents.layer5.lead_capture_nurture", "lead_register",
              ("audience_segments", "message_flows"), "conditional"),
    # --- Layer 6: Analytics & Feedback ---
    AgentStep("6.1", "Performance Analytics", "L6", "agents.layer6.performance_analytics", "performance_history",
              ("ad_campaign_log", "publish_log", "lead_register", "active_strategy", "kpi_contracts"), "auto+alert"),
    AgentStep("6.2", "Client Reporting", "L6", "agents.layer6.client_reporting", "client_health_score",
              ("performance_history", "active_strategy", "client_profile"), "pre-client"),
    AgentStep("6.3", "Optimization Engine", "L6", "agents.layer6.optimization_engine", "content_learnings",
              ("performance_history", "content_learnings"), "bounded-auto"),
)

_LAYER_ORDER = ("L1", "L2", "L3", "L4", "L5", "L6")


def _load_run(module: str) -> Callable[[dict], object]:
    return importlib.import_module(module).run


def run_pipeline(
    client_id: str,
    inputs: dict | None = None,
    *,
    auto_approve: bool = True,
    stop_after_layer: str | None = None,
    on_event: Callable[[dict], None] | None = None,
    capture_results: bool = False,
) -> dict:
    """Execute the suite for one client.

    Returns {"memory": {block: obj}, "transcript": [per-agent event dicts]}.
    `inputs` supplies the raw onboarding sources (quick_start_form, crm_data, …).
    `auto_approve` simulates the operator approving each gate so the chain runs
    end-to-end offline; set False to halt at the first un-approved gate.
    `stop_after_layer` (e.g. "L1") ends the run after that layer — handy for the
    Phase-1 milestone (client_profile + audience_segments).
    """
    inputs = inputs or {}
    memory: dict[str, object] = {}
    transcript: list[dict] = []

    for step in PIPELINE:
        payload: dict = {"client_id": client_id, **inputs}
        for blk in step.reads:
            if blk in memory:
                payload[blk] = memory[blk]

        entry: dict = {"agent": step.id, "name": step.name, "layer": step.layer, "gate": step.gate}
        try:
            result = _load_run(step.module)(payload)
        except ModuleNotFoundError as e:
            entry.update(valid=False, error=f"agent not built yet: {e}")
            transcript.append(entry)
            if on_event:
                on_event(entry)
            continue

        entry["valid"] = result.valid
        entry["error"] = result.error
        if capture_results:
            entry["_result"] = result   # full AgentResult, for the validation harness
        if result.valid and result.structured:
            obj = dict(result.structured)
            gate_status = obj.get("gate_status", "auto_approved")
            if auto_approve and gate_status in ("pending_review", "returned", "blocked"):
                obj["gate_status"] = "approved"
            if step.gate in GATED and obj.get("gate_status") not in ("approved", "auto_approved"):
                entry["blocked_downstream"] = True
            else:
                memory[step.block] = obj
                for export_block, key in step.exports.items():
                    val = obj.get(key)
                    if val is not None:
                        memory[export_block] = val
            entry["gate_status"] = obj.get("gate_status")
        transcript.append(entry)
        if on_event:
            on_event(entry)

        if stop_after_layer and step.layer == stop_after_layer:
            # finish the rest of this layer, then stop
            if not any(s.layer == stop_after_layer for s in PIPELINE[PIPELINE.index(step) + 1:]):
                break

    return {"memory": memory, "transcript": transcript}
