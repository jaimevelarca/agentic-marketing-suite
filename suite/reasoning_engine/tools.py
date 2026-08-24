"""Structured query tools for the Marketing Suite Reasoning Engine.

Exposes domain-specific reads over Firestore Native memory blocks
(clients/{client_id}/blocks/{block}) to Vertex Reasoning Engine and
Gemini Enterprise A2A agents.
"""
from __future__ import annotations

from typing import Any
from infra import clients


def get_client_summary(client_id: str) -> dict[str, Any]:
    """Retrieve high-level business profile, value proposition, industry, and budget for a client."""
    profile = clients.read_memory_block(client_id, "client_profile") or {}
    brand = clients.read_memory_block(client_id, "brand_core") or {}
    gate_status = clients.read_gate_status(client_id, "client_profile")

    name = profile.get("name")
    if isinstance(name, dict):
        name = name.get("trade") or name.get("legal") or client_id
    elif not name:
        name = client_id

    return {
        "client_id": client_id,
        "name": name,
        "industry": profile.get("industry") or brand.get("industry") or "No especificada",
        "description": profile.get("description") or brand.get("description") or "Sin descripción",
        "usp": profile.get("usp") or brand.get("usp") or "No definida",
        "monthly_budget": profile.get("budget") or profile.get("confirmed_budget_mxn") or "No establecido",
        "gate_status": gate_status or "no_iniciado",
        "has_brand_core": bool(brand),
    }


def get_audience_and_competition(client_id: str) -> dict[str, Any]:
    """Retrieve audience segments (ICPs) and competitive radar/gaps for a client."""
    audience = clients.read_memory_block(client_id, "audience_segments") or {}
    competition = clients.read_memory_block(client_id, "competitive_map") or {}
    trends = clients.read_memory_block(client_id, "trend_signals") or {}

    segments = audience.get("segments") or []
    competitors = competition.get("competitors") or []
    content_gaps = competition.get("content_gaps") or []
    signals = trends.get("signals") or []

    return {
        "client_id": client_id,
        "total_segments": len(segments),
        "segments": segments,
        "total_competitors": len(competitors),
        "competitors": competitors,
        "content_gaps": content_gaps,
        "trend_signals": signals,
    }


def get_marketing_strategy(client_id: str) -> dict[str, Any]:
    """Retrieve strategic thesis, channel mix, budget allocation, and KPI targets for a client."""
    strategy = clients.read_memory_block(client_id, "active_strategy") or {}
    gate_status = clients.read_gate_status(client_id, "active_strategy")

    thesis = strategy.get("strategic_thesis") or strategy.get("thesis") or "No definida"
    pillars = strategy.get("messaging_pillars") or strategy.get("pillars") or []
    budget_alloc = strategy.get("budget_allocation") or {}
    channel_mix = strategy.get("channel_mix") or []
    kpis = strategy.get("kpi_contracts") or strategy.get("kpi_targets") or {}

    return {
        "client_id": client_id,
        "gate_status": gate_status or "pending_review",
        "strategic_thesis": thesis,
        "messaging_pillars": pillars,
        "channel_mix": channel_mix,
        "budget_allocation": budget_alloc,
        "kpi_targets": kpis,
    }


def get_content_and_campaigns(client_id: str) -> dict[str, Any]:
    """Retrieve active campaigns and the 4-week content calendar for a client."""
    campaigns_doc = clients.read_memory_block(client_id, "campaign_registry") or {}
    calendar_doc = clients.read_memory_block(client_id, "content_calendar") or {}

    campaigns = campaigns_doc.get("campaigns") or []
    slots = calendar_doc.get("slots") or []
    cycle_weeks = calendar_doc.get("cycle_weeks") or 4

    return {
        "client_id": client_id,
        "total_campaigns": len(campaigns),
        "campaigns": campaigns,
        "cycle_weeks": cycle_weeks,
        "total_content_slots": len(slots),
        "content_slots": slots,
    }


def get_creative_deliverables(client_id: str) -> dict[str, Any]:
    """Retrieve copy assets, visual specifications, and email/messaging flows for a client."""
    copy_doc = clients.read_memory_block(client_id, "copy_assets") or {}
    visual_doc = clients.read_memory_block(client_id, "visual_assets") or {}
    flows_doc = clients.read_memory_block(client_id, "message_flows") or {}
    pages_doc = clients.read_memory_block(client_id, "page_assets") or {}

    return {
        "client_id": client_id,
        "copy_assets_count": len(copy_doc.get("assets") or []),
        "copy_assets": copy_doc.get("assets") or [],
        "visual_specs_count": len(visual_doc.get("visuals") or visual_doc.get("assets") or []),
        "visual_specs": visual_doc.get("visuals") or visual_doc.get("assets") or [],
        "message_flows_count": len(flows_doc.get("flows") or []),
        "message_flows": flows_doc.get("flows") or [],
        "landing_pages_count": len(pages_doc.get("pages") or []),
        "landing_pages": pages_doc.get("pages") or [],
    }


def get_run_execution_status(client_id: str) -> dict[str, Any]:
    """Retrieve current human gate statuses, review queue state, and memory block completeness."""
    core_blocks = [
        "client_profile",
        "brand_core",
        "audience_segments",
        "competitive_map",
        "trend_signals",
        "active_strategy",
        "campaign_registry",
        "content_calendar",
        "copy_assets",
        "visual_assets",
        "message_flows",
        "page_assets",
    ]

    block_status = {}
    populated_count = 0
    pending_gates = []

    for b in core_blocks:
        payload = clients.read_memory_block(client_id, b)
        gate = clients.read_gate_status(client_id, b)
        if payload is not None:
            populated_count += 1
        block_status[b] = {
            "has_data": payload is not None,
            "gate_status": gate or "none",
        }
        if gate in ("pending", "pending_review"):
            pending_gates.append(b)

    return {
        "client_id": client_id,
        "total_blocks_checked": len(core_blocks),
        "populated_blocks_count": populated_count,
        "pending_human_gates": pending_gates,
        "blocks": block_status,
        "is_ready_for_review": "active_strategy" in pending_gates or bool(pending_gates),
    }


def compile_client_proposal(client_id: str, format: str = "both") -> dict[str, Any]:
    """Compile the interactive 9-act HTML presentation deck and executive detail dossier for a client."""
    from suite.rendering import compile_proposal

    res = compile_proposal(client_id=client_id)
    return {
        "client_id": client_id,
        "client_name": res["client_name"],
        "presentation_filename": res["presentation_filename"],
        "detail_filename": res["detail_filename"],
        "presentation_size_chars": len(res["presentation_html"]),
        "detail_size_chars": len(res["detail_html"]),
        "generated_at": res["generated_at"],
        "status": "ready",
        "format": format,
    }


TOOLS = [
    get_client_summary,
    get_audience_and_competition,
    get_marketing_strategy,
    get_content_and_campaigns,
    get_creative_deliverables,
    get_run_execution_status,
    compile_client_proposal,
]

