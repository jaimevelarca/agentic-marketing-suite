"""Specialized visual formatters for marketing memory blocks.

Transforms raw JSON payloads into human-friendly cards, tables, color swatches,
and copywriting registers for the review UI.
"""
from __future__ import annotations

from typing import Any


def format_block_payload(block_name: str, payload: Any) -> dict[str, Any]:
    """Inspect block payload and produce structured visual data for template rendering."""
    if not isinstance(payload, dict):
        return {"type": "raw", "data": payload}

    renderer = _RENDERERS.get(block_name, _format_generic_block)
    try:
        return renderer(payload)
    except Exception:
        return _format_generic_block(payload)


def _format_client_profile(payload: dict) -> dict[str, Any]:
    quick = payload.get("quick_start_form") or {}
    scraper = payload.get("scraper_output") or {}
    visual = scraper.get("visual_identity") or {}
    voice = scraper.get("brand_voice") or {}

    colors = visual.get("top_5_hex") or []
    if not colors and payload.get("primary_hex"):
        colors = [payload.get("primary_hex")]

    return {
        "type": "client_profile",
        "title": "Ficha Maestra de Cliente e Identidad de Marca",
        "company_name": quick.get("company_name") or payload.get("company_name") or payload.get("client_id", ""),
        "website_url": quick.get("website_url") or scraper.get("website_url") or "",
        "industry": quick.get("industry") or "",
        "offer_description": quick.get("offer_description") or scraper.get("meta_description") or "",
        "primary_market": quick.get("primary_market") or "México",
        "target_markets": quick.get("target_markets") or scraper.get("locations_detected") or [],
        "target_customer": quick.get("target_customer") or "",
        "value_propositions": scraper.get("value_propositions") or [],
        "services_extracted": scraper.get("services_extracted") or [],
        "primary_cta": scraper.get("primary_cta") or "Solicitar información",
        "colors": colors,
        "voice_register": voice.get("vocabulary_register") or "professional/corporate",
        "voice_tokens": voice.get("proposed_voice_tokens") or [],
        "logo_url": (visual.get("logo") or {}).get("url"),
        "operator_notes": payload.get("operator_notes") or "",
    }


def _format_audience_segments(payload: dict) -> dict[str, Any]:
    raw_segments = payload.get("segments") or payload.get("audience_segments") or []
    if isinstance(raw_segments, dict):
        raw_segments = list(raw_segments.values())

    segments_out = []
    for idx, s in enumerate(raw_segments, 1):
        if not isinstance(s, dict):
            segments_out.append({"name": f"Segmento {idx}", "summary": str(s)})
            continue
        segments_out.append({
            "name": s.get("name") or s.get("segment_name") or f"Segmento {idx}",
            "description": s.get("description") or s.get("profile") or "",
            "demographics": s.get("demographics") or s.get("demographic_profile") or {},
            "pain_points": s.get("pain_points") or s.get("pains") or [],
            "motivations": s.get("motivations") or s.get("desires") or [],
            "core_message": s.get("core_message") or s.get("key_message") or "",
            "channels": s.get("channels") or s.get("preferred_channels") or [],
        })

    return {
        "type": "audience_segments",
        "title": "Segmentación Estratégica de Audiencias (ICP)",
        "segments": segments_out,
        "total_segments": len(segments_out),
        "notes": payload.get("notes") or "",
    }


def _format_competitive_map(payload: dict) -> dict[str, Any]:
    comps = payload.get("competitors") or []
    if isinstance(comps, dict):
        comps = list(comps.values())

    out_comps = []
    for c in comps:
        if not isinstance(c, dict):
            out_comps.append({"name": str(c)})
            continue
        out_comps.append({
            "name": c.get("name") or c.get("competitor_name") or "Competidor",
            "type": c.get("type") or c.get("category") or "Directo",
            "strengths": c.get("strengths") or [],
            "weaknesses": c.get("weaknesses") or [],
            "price_point": c.get("price_point") or c.get("pricing") or "Medio",
            "differentiation": c.get("differentiation") or c.get("value_prop") or "",
        })

    return {
        "type": "competitive_map",
        "title": "Auditoría de Competencia & Matriz de Posicionamiento",
        "competitors": out_comps,
        "quadrant_summary": payload.get("quadrant_summary") or payload.get("market_gaps") or "",
        "our_advantage": payload.get("our_advantage") or payload.get("strategic_advantage") or "",
    }


def _format_active_strategy(payload: dict) -> dict[str, Any]:
    pillars = payload.get("pillars") or payload.get("strategic_pillars") or []
    if isinstance(pillars, dict):
        pillars = list(pillars.values())

    return {
        "type": "active_strategy",
        "title": "Estrategia Activa de Crecimiento & Objetivos",
        "summary": payload.get("summary") or payload.get("thesis") or payload.get("strategy_summary") or "",
        "pillars": pillars,
        "budget_allocation": payload.get("budget_allocation") or payload.get("budgets") or {},
        "target_channels": payload.get("target_channels") or payload.get("channels") or [],
        "kpi_summary": payload.get("kpi_summary") or payload.get("kpis") or {},
    }


def _format_kpi_contracts(payload: dict) -> dict[str, Any]:
    contracts = payload.get("kpis") or payload.get("contracts") or payload.get("metrics") or []
    if isinstance(contracts, dict):
        contracts = [{"name": k, **(v if isinstance(v, dict) else {"target": str(v)})} for k, v in contracts.items()]

    return {
        "type": "kpi_contracts",
        "title": "Contratos de KPI & Compromisos de Conversión",
        "contracts": contracts,
        "review_period": payload.get("review_period") or "Mensual",
        "primary_metric": payload.get("primary_metric") or "CPL / Leads Calificados",
    }


def _format_content_calendar(payload: dict) -> dict[str, Any]:
    raw_posts = payload.get("calendar") or payload.get("posts") or payload.get("items") or []
    posts_out = []

    for p in raw_posts:
        if not isinstance(p, dict):
            posts_out.append({"title": str(p)})
            continue
        posts_out.append({
            "week": p.get("week") or p.get("semana") or "S1",
            "day": p.get("day") or p.get("dia") or "Lunes",
            "channel": p.get("channel") or p.get("canal") or "Meta",
            "format": p.get("format") or p.get("formato") or "Post",
            "topic": p.get("topic") or p.get("title") or p.get("tema") or "",
            "teaser": p.get("copy_teaser") or p.get("hook") or p.get("copy") or "",
            "approved": p.get("approved", True),
        })

    return {
        "type": "content_calendar",
        "title": "Calendario Editorial (Parrilla de 4 Semanas)",
        "posts": posts_out,
        "total_posts": len(posts_out),
        "duration_weeks": payload.get("duration_weeks") or 4,
    }


def _format_copy_assets(payload: dict) -> dict[str, Any]:
    raw_copies = payload.get("assets") or payload.get("copies") or payload.get("copy_list") or []
    if isinstance(raw_copies, dict):
        raw_copies = list(raw_copies.values())

    copies_out = []
    for c in raw_copies:
        if not isinstance(c, dict):
            copies_out.append({"body": str(c)})
            continue
        copies_out.append({
            "channel": c.get("channel") or c.get("platform") or "General",
            "target_audience": c.get("target_audience") or c.get("segment") or "Audiencia Principal",
            "headline": c.get("headline") or c.get("title") or c.get("h1") or "",
            "body": c.get("body") or c.get("text") or c.get("copy") or "",
            "cta": c.get("cta") or c.get("button_text") or "",
            "variation": c.get("variation") or c.get("version") or "A",
        })

    return {
        "type": "copy_assets",
        "title": "Librería de Copys Persuasivos & Variantes A/B",
        "copies": copies_out,
        "total_copies": len(copies_out),
    }


def _format_visual_assets(payload: dict) -> dict[str, Any]:
    raw_visuals = payload.get("assets") or payload.get("visuals") or payload.get("creatives") or []
    if isinstance(raw_visuals, dict):
        raw_visuals = list(raw_visuals.values())

    visuals_out = []
    for v in raw_visuals:
        if not isinstance(v, dict):
            visuals_out.append({"description": str(v)})
            continue
        visuals_out.append({
            "name": v.get("name") or v.get("title") or "Creativo",
            "ratio": v.get("ratio") or v.get("aspect_ratio") or "1:1",
            "channel": v.get("channel") or v.get("platform") or "Redes",
            "concept": v.get("concept") or v.get("description") or "",
            "prompt": v.get("prompt") or v.get("image_prompt") or "",
            "colors": v.get("colors") or [],
        })

    return {
        "type": "visual_assets",
        "title": "Activos Visuales & Dirección Creativa",
        "visuals": visuals_out,
        "total_visuals": len(visuals_out),
    }


def _format_generic_block(payload: dict) -> dict[str, Any]:
    items = []
    for k, v in payload.items():
        if isinstance(v, (str, int, float, bool)):
            items.append({"key": k.replace("_", " ").title(), "val": str(v), "is_list": False})
        elif isinstance(v, list) and all(isinstance(x, (str, int, float)) for x in v):
            items.append({"key": k.replace("_", " ").title(), "val": v, "is_list": True})
        else:
            items.append({"key": k.replace("_", " ").title(), "val": str(v), "is_list": False})

    return {
        "type": "generic",
        "title": "Entregable del Bloque",
        "items": items,
    }


_RENDERERS = {
    "client_profile": _format_client_profile,
    "audience_segments": _format_audience_segments,
    "competitive_map": _format_competitive_map,
    "active_strategy": _format_active_strategy,
    "kpi_contracts": _format_kpi_contracts,
    "content_calendar": _format_content_calendar,
    "copy_assets": _format_copy_assets,
    "visual_assets": _format_visual_assets,
}
