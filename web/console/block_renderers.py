"""Specialized visual formatters for marketing memory blocks.

Transforms raw JSON payloads into human-friendly cards, tables, color swatches,
and copywriting registers for the review UI.
"""
from __future__ import annotations

from typing import Any


def _val(x: Any) -> Any:
    """Recursively extract value from DEL-09 confidence_metadata tagged leaf fields."""
    if isinstance(x, dict):
        if "value" in x:
            return _val(x["value"])
        if "primary" in x:
            return _val(x["primary"])
        if "statement" in x:
            return _val(x["statement"])
        if "description" in x and len(x) <= 2 and "metadata" in x:
            return _val(x["description"])
    return x


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
    visual = payload.get("visual_identity") or scraper.get("visual_identity") or {}
    voice = payload.get("brand_voice_tokens") or scraper.get("brand_voice") or {}

    # Company name
    name_obj = payload.get("name")
    if isinstance(name_obj, dict):
        company_name = name_obj.get("trade") or name_obj.get("legal") or _val(name_obj.get("value"))
    else:
        company_name = name_obj or quick.get("company_name") or payload.get("company_name")
    company_name = company_name or payload.get("client_id", "")

    # Website URL
    web_obj = payload.get("website_url")
    if isinstance(web_obj, dict):
        website_url = web_obj.get("primary") or _val(web_obj.get("value"))
        if not website_url and web_obj.get("additional"):
            website_url = web_obj["additional"][0]
    else:
        website_url = web_obj or quick.get("website_url") or scraper.get("website_url") or payload.get("website_url") or ""

    # Industry
    ind_obj = payload.get("industry")
    if isinstance(ind_obj, dict):
        industry = ind_obj.get("primary") or _val(ind_obj.get("value"))
    else:
        industry = ind_obj or quick.get("industry") or payload.get("industry") or ""

    # Offer description
    offers_obj = payload.get("offers")
    if isinstance(offers_obj, dict):
        offer_desc = offers_obj.get("description") or _val(offers_obj.get("value"))
    else:
        offer_desc = offers_obj or quick.get("offer_description") or scraper.get("meta_description") or ""

    # USP / Value propositions
    usp_obj = payload.get("usp")
    if isinstance(usp_obj, dict):
        usp_stmt = usp_obj.get("statement") or _val(usp_obj.get("value"))
    else:
        usp_stmt = usp_obj or ""
    
    value_props = scraper.get("value_propositions") or ([usp_stmt] if usp_stmt else [])
    if isinstance(value_props, str):
        value_props = [value_props]

    # Colors
    colors = (
        visual.get("primary_colors_hex")
        or visual.get("top_5_hex")
        or ([payload.get("primary_hex")] if payload.get("primary_hex") else [])
    )

    # Voice register & tokens
    if isinstance(voice, dict):
        voice_register = voice.get("vocabulary_register") or voice.get("tone_selected") or "professional/corporate"
        voice_tokens = voice.get("tokens") or voice.get("proposed_voice_tokens") or []
    else:
        voice_register = "professional/corporate"
        voice_tokens = []

    # Target markets & customer
    tgt_obj = payload.get("target_markets")
    if isinstance(tgt_obj, dict):
        target_markets = tgt_obj.get("ranked") or _val(tgt_obj.get("value")) or []
    else:
        target_markets = tgt_obj or quick.get("target_markets") or scraper.get("locations_detected") or []

    goals_obj = payload.get("goals")
    if isinstance(goals_obj, dict):
        primary_goal = goals_obj.get("primary_objective") or _val(goals_obj.get("value"))
    else:
        primary_goal = goals_obj or quick.get("marketing_objective") or ""

    logo_url = visual.get("logo_url")
    if not logo_url and isinstance(visual.get("logo"), dict):
        logo_url = visual["logo"].get("url")

    return {
        "type": "client_profile",
        "title": "Ficha Maestra de Cliente e Identidad de Marca",
        "company_name": company_name,
        "website_url": website_url,
        "industry": industry,
        "offer_description": offer_desc,
        "primary_market": quick.get("primary_market") or "México",
        "target_markets": target_markets,
        "target_customer": quick.get("target_customer") or primary_goal or "",
        "value_propositions": value_props,
        "services_extracted": scraper.get("services_extracted") or [],
        "primary_cta": scraper.get("primary_cta") or "Solicitar información",
        "colors": colors,
        "voice_register": voice_register,
        "voice_tokens": voice_tokens,
        "logo_url": logo_url,
        "operator_notes": payload.get("operator_notes") or "",
        "lifecycle_stage": payload.get("lifecycle_stage") or "pre-launch",
    }


def _format_audience_segments(payload: dict) -> dict[str, Any]:
    raw_segments = payload.get("segments") or payload.get("audience_segments") or []
    if isinstance(raw_segments, dict):
        raw_segments = list(raw_segments.values())

    segments_out = []
    for idx, s in enumerate(raw_segments):
        if not isinstance(s, dict):
            segments_out.append({"index": idx, "name": f"Segmento {idx+1}", "description": str(s)})
            continue

        name = _val(s.get("segment_name") or s.get("name")) or f"Segmento {idx+1}"
        desc = _val(s.get("funnel_focus") or s.get("description") or s.get("profile") or "")

        pains = _val(s.get("pain_points") or s.get("pains") or [])
        if isinstance(pains, dict):
            pains = _val(pains.get("value") or [])
        if isinstance(pains, str):
            pains = [pains]

        motivations = _val(s.get("motivations") or s.get("desires") or [])
        if isinstance(motivations, dict):
            motivations = _val(motivations.get("value") or [])
        if isinstance(motivations, str):
            motivations = [motivations]

        core_msg = _val(s.get("core_message") or s.get("key_message") or "")
        if isinstance(core_msg, dict):
            core_msg = _val(core_msg.get("value") or "")

        raw_channels = _val(s.get("preferred_channels") or s.get("channels") or [])
        if isinstance(raw_channels, dict):
            raw_channels = _val(raw_channels.get("value") or [])
        channels = []
        for ch in (raw_channels if isinstance(raw_channels, list) else [raw_channels]):
            if isinstance(ch, dict):
                channels.append(ch.get("channel") or ch.get("name") or str(ch))
            elif isinstance(ch, str):
                channels.append(ch)

        segments_out.append({
            "index": idx,
            "segment_id": s.get("segment_id") or f"seg-{idx+1}",
            "name": name,
            "description": desc,
            "demographics": _val(s.get("demographics") or s.get("demographic_profile") or {}),
            "pain_points": pains,
            "motivations": motivations,
            "core_message": core_msg,
            "channels": channels,
        })

    return {
        "type": "audience_segments",
        "title": "Segmentación Estratégica de Audiencias (Perfiles Objetivo / ICP)",
        "segments": segments_out,
        "total_segments": len(segments_out),
        "notes": payload.get("notes") or "",
    }


def _format_competitive_map(payload: dict) -> dict[str, Any]:
    comps = payload.get("competitors") or []
    if isinstance(comps, dict):
        comps = list(comps.values())

    out_comps = []
    for idx, c in enumerate(comps):
        if not isinstance(c, dict):
            out_comps.append({"index": idx, "name": str(c)})
            continue
        out_comps.append({
            "index": idx,
            "name": _val(c.get("name") or c.get("competitor_name") or "Competidor"),
            "type": _val(c.get("type") or c.get("tier") or c.get("category") or "Directo"),
            "strengths": _val(c.get("strengths") or []),
            "weaknesses": _val(c.get("weaknesses") or []),
            "price_point": _val(c.get("price_point") or c.get("pricing") or "Medio"),
            "differentiation": _val(c.get("differentiation") or c.get("value_prop") or c.get("positioning") or ""),
        })

    return {
        "type": "competitive_map",
        "title": "Auditoría de Competencia & Matriz de Posicionamiento",
        "competitors": out_comps,
        "quadrant_summary": _val(payload.get("quadrant_summary") or payload.get("market_gaps") or payload.get("differentiation_opportunities") or ""),
        "our_advantage": _val(payload.get("our_advantage") or payload.get("strategic_advantage") or payload.get("strategic_positioning") or ""),
    }


def _format_trend_signals(payload: dict) -> dict[str, Any]:
    raw_signals = payload.get("signals") or payload.get("trends") or []
    if isinstance(raw_signals, dict):
        raw_signals = list(raw_signals.values())

    signals_out = []
    for idx, s in enumerate(raw_signals):
        if not isinstance(s, dict):
            signals_out.append({"index": idx, "topic": str(s)})
            continue
        signals_out.append({
            "index": idx,
            "topic": s.get("topic") or f"Señal {idx+1}",
            "category": s.get("category") or "General",
            "velocity": s.get("velocity") or "rising",
            "suggested_angle": s.get("suggested_angle") or s.get("angle") or "",
            "channels": s.get("recommended_channels") or [],
            "rationale": s.get("rationale") or "",
        })

    return {
        "type": "trend_signals",
        "title": "Radar de Tendencias & Señales de Mercado",
        "signals": signals_out,
        "total_signals": len(signals_out),
    }


def _format_active_strategy(payload: dict) -> dict[str, Any]:
    thesis = payload.get("strategic_thesis")
    if isinstance(thesis, dict):
        thesis_text = thesis.get("statement") or _val(thesis.get("value")) or str(thesis)
    else:
        thesis_text = thesis or payload.get("summary") or payload.get("thesis") or ""

    channel_mix = payload.get("channel_mix") or payload.get("target_channels") or payload.get("channels") or []
    channels_out = []
    for ch in channel_mix:
        if isinstance(ch, dict):
            name = ch.get("name", "Canal")
            share = f" ({ch.get('budget_share_pct')}%)" if ch.get("budget_share_pct") else ""
            role = f" — {ch.get('role')}" if ch.get("role") else ""
            channels_out.append(f"{name}{share}{role}")
        elif isinstance(ch, str):
            channels_out.append(ch)

    pillars = payload.get("pillars") or payload.get("strategic_pillars") or []
    if isinstance(pillars, dict):
        pillars = list(pillars.values())
    if not pillars and channels_out:
        pillars = channels_out

    return {
        "type": "active_strategy",
        "title": "Estrategia Activa de Crecimiento & Objetivos",
        "summary": thesis_text,
        "pillars": pillars,
        "budget_allocation": payload.get("budget_allocation") or payload.get("budgets") or {},
        "target_channels": channels_out,
        "kpi_summary": payload.get("kpi_contracts") or payload.get("kpi_summary") or payload.get("kpis") or {},
        "primary_objective": _val(payload.get("primary_objective") or ""),
    }


def _format_campaign_registry(payload: dict) -> dict[str, Any]:
    raw_campaigns = payload.get("campaigns") or []
    if isinstance(raw_campaigns, dict):
        raw_campaigns = list(raw_campaigns.values())

    stage_labels = {
        "top_of_funnel": "Atracción (TOFU)",
        "middle_of_funnel": "Consideración (MOFU)",
        "bottom_of_funnel": "Conversión (BOFU)",
        "retention": "Retención / Lealtad",
        "tofu": "Atracción (TOFU)",
        "mofu": "Consideración (MOFU)",
        "bofu": "Conversión (BOFU)",
    }

    out_campaigns = []
    for idx, c in enumerate(raw_campaigns):
        if not isinstance(c, dict):
            out_campaigns.append({"index": idx, "name": str(c)})
            continue

        raw_channels = c.get("channel_mix") or c.get("channels") or []
        channels = []
        for ch in raw_channels:
            if isinstance(ch, dict):
                channels.append(ch.get("channel") or str(ch))
            else:
                channels.append(str(ch))

        stage_raw = str(c.get("funnel_stage", "")).lower()
        stage_label = stage_labels.get(stage_raw, c.get("funnel_stage") or "General")

        pillars = c.get("messaging_pillars") or []
        if isinstance(pillars, str):
            pillars = [pillars]

        metrics = c.get("success_metrics") or []
        metric_labels = []
        for m in metrics:
            if isinstance(m, dict):
                metric_labels.append(f"{m.get('metric', '')}: {m.get('target', '')} {m.get('unit', '')}".strip())
            else:
                metric_labels.append(str(m))

        out_campaigns.append({
            "index": idx,
            "campaign_id": c.get("campaign_id") or f"camp-{idx+1}",
            "name": c.get("name") or f"Campaña {idx+1}",
            "theme": c.get("theme") or "",
            "objective": c.get("objective") or "",
            "funnel_stage": stage_label,
            "funnel_stage_raw": stage_raw,
            "priority": c.get("priority", idx+1),
            "channels": channels,
            "messaging_pillars": pillars,
            "target_segments": c.get("primary_segment_ids") or [],
            "metrics": metric_labels,
        })

    budget_summary = payload.get("budget_summary") or {}
    total_budget = ""
    if isinstance(budget_summary, dict):
        total_budget = budget_summary.get("total_budget_usd") or budget_summary.get("monthly_total") or ""

    return {
        "type": "campaign_registry",
        "title": "Registro Estratégico de Campañas por Etapa del Embudo",
        "campaigns": out_campaigns,
        "total_campaigns": len(out_campaigns),
        "total_budget": total_budget,
        "cycle_label": payload.get("cycle_label") or "Ciclo 1",
    }


def _format_content_plan(payload: dict) -> dict[str, Any]:
    raw_pillars = payload.get("pillars") or payload.get("themes") or payload.get("weeks") or []
    if isinstance(raw_pillars, dict):
        raw_pillars = list(raw_pillars.values())

    pillars_out = []
    for idx, p in enumerate(raw_pillars):
        if not isinstance(p, dict):
            pillars_out.append({"index": idx, "name": str(p)})
            continue
        pillars_out.append({
            "index": idx,
            "week": p.get("week") or f"Semana {idx+1}",
            "name": p.get("pillar_name") or p.get("theme") or p.get("name") or f"Pilar {idx+1}",
            "narrative_angle": p.get("narrative_angle") or p.get("angle") or p.get("description") or "",
            "formats": p.get("formats") or p.get("recommended_formats") or [],
            "channels": p.get("channels") or [],
        })

    return {
        "type": "content_plan",
        "title": "Plan de Contenido Mensual (Pilares Temáticos)",
        "pillars": pillars_out,
        "total_pillars": len(pillars_out),
    }


def _format_kpi_contracts(payload: dict) -> dict[str, Any]:
    contracts = payload.get("kpi_contracts") or payload.get("kpis") or payload.get("contracts") or payload.get("metrics") or []
    if isinstance(contracts, dict):
        targets = contracts.get("targets") or contracts
        if isinstance(targets, list):
            contracts_out = targets
        else:
            contracts_out = [{"name": k, **(v if isinstance(v, dict) else {"target": str(v)})} for k, v in targets.items()]
    else:
        contracts_out = contracts

    return {
        "type": "kpi_contracts",
        "title": "Contratos de KPI & Compromisos de Conversión",
        "contracts": contracts_out,
        "review_period": payload.get("review_period") or "Mensual",
        "primary_metric": payload.get("primary_metric") or "CPL / Leads Calificados",
    }


def _format_content_calendar(payload: dict) -> dict[str, Any]:
    raw_posts = payload.get("slots") or payload.get("calendar") or payload.get("posts") or payload.get("items") or []
    posts_out = []

    for idx, p in enumerate(raw_posts):
        if not isinstance(p, dict):
            posts_out.append({"index": idx, "title": str(p)})
            continue
        
        content_ref = p.get("content_ref") or {}
        topic = content_ref.get("topic_title") or p.get("topic") or p.get("title") or p.get("campaign_name") or ""
        teaser = content_ref.get("messaging_pillar") or p.get("copy_teaser") or p.get("hook") or p.get("copy") or ""
        week_val = p.get("week") or p.get("semana") or 1
        week_label = f"S{week_val}" if isinstance(week_val, int) else str(week_val)

        posts_out.append({
            "index": idx,
            "week": week_label,
            "day": p.get("publish_date") or p.get("day") or p.get("dia") or "Fecha programada",
            "channel": p.get("channel") or p.get("canal") or "Meta",
            "format": p.get("format") or p.get("formato") or "Post",
            "topic": topic,
            "teaser": teaser,
            "approved": p.get("status") == "approved" or p.get("approved", True),
        })

    return {
        "type": "content_calendar",
        "title": "Calendario Editorial (Parrilla de Contenido)",
        "posts": posts_out,
        "total_posts": len(posts_out),
        "duration_weeks": payload.get("duration_weeks") or 4,
    }


def _format_copy_assets(payload: dict) -> dict[str, Any]:
    raw_copies = payload.get("assets") or payload.get("copies") or payload.get("copy_list") or []
    if isinstance(raw_copies, dict):
        raw_copies = list(raw_copies.values())

    copies_out = []
    for idx, c in enumerate(raw_copies):
        if not isinstance(c, dict):
            copies_out.append({"index": idx, "body": str(c)})
            continue
        headline = c.get("hook") or c.get("headline") or c.get("title") or c.get("h1") or ""
        body = c.get("primary_caption") or c.get("body") or c.get("text") or c.get("copy") or ""
        copies_out.append({
            "index": idx,
            "channel": c.get("channel") or c.get("platform") or "General",
            "target_audience": c.get("target_segment_id") or c.get("target_audience") or c.get("segment") or "Audiencia Principal",
            "headline": headline,
            "body": body,
            "cta": c.get("cta") or c.get("button_text") or "",
            "variation": c.get("risk_tier") or c.get("variation") or c.get("version") or "A",
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
    for idx, v in enumerate(raw_visuals):
        if not isinstance(v, dict):
            visuals_out.append({"index": idx, "description": str(v)})
            continue
        concept = v.get("concept_rationale") or v.get("rationale") or v.get("concept") or v.get("description") or ""
        prompt = v.get("prompt") or v.get("image_prompt") or ""
        if isinstance(prompt, dict):
            prompt = prompt.get("prompt") or str(prompt)
        visuals_out.append({
            "index": idx,
            "name": v.get("asset_id") or v.get("name") or v.get("title") or "Creativo",
            "ratio": v.get("aspect_ratio") or v.get("ratio") or "1:1",
            "channel": v.get("channel") or v.get("platform") or "Redes",
            "concept": concept,
            "prompt": prompt,
            "colors": v.get("palette_applied") or v.get("colors") or [],
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
        v_unwrapped = _val(v)
        if isinstance(v_unwrapped, (str, int, float, bool)):
            items.append({"key": k.replace("_", " ").title(), "val": str(v_unwrapped), "is_list": False})
        elif isinstance(v_unwrapped, list) and all(isinstance(x, (str, int, float)) for x in v_unwrapped):
            items.append({"key": k.replace("_", " ").title(), "val": v_unwrapped, "is_list": True})
        elif isinstance(v_unwrapped, dict):
            clean_d = {dk: str(_val(dv)) for dk, dv in v_unwrapped.items() if dk != "metadata"}
            items.append({"key": k.replace("_", " ").title(), "val": str(clean_d), "is_list": False})
        else:
            items.append({"key": k.replace("_", " ").title(), "val": str(v_unwrapped), "is_list": False})

    return {
        "type": "generic",
        "title": "Entregable del Bloque",
        "items": items,
    }


_RENDERERS = {
    "client_profile": _format_client_profile,
    "audience_segments": _format_audience_segments,
    "competitive_map": _format_competitive_map,
    "trend_signals": _format_trend_signals,
    "active_strategy": _format_active_strategy,
    "campaign_registry": _format_campaign_registry,
    "content_plan": _format_content_plan,
    "content_calendar": _format_content_calendar,
    "kpi_contracts": _format_kpi_contracts,
    "copy_assets": _format_copy_assets,
    "visual_assets": _format_visual_assets,
}
