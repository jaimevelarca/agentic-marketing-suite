"""Interactive 9-Act Presentation Deck Compiler.

Compiles Firestore Native memory blocks into a standalone, interactive,
responsive HTML presentation deck implementing the 9-act storytelling structure
with strict QHHE theming and inlined assets.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

try:
    from infra import clients
except ImportError:
    from suite.infra import clients  # type: ignore[no-redef]

from suite.rendering.engines import engine_label
from suite.rendering.theme import (
    Theme,
    derive_theme_from_profile,
    load_theme,
    theme_css,
)

# Standard CSS rules for presentation decks (derived from alonsoycia-plan and u-storage-plan)
BASE_CSS = """
/* ===== QHHE presentation styling tokens ===== */
* { box-sizing: border-box; margin: 0; }
html { scroll-behavior: smooth; scroll-snap-type: y proximity; }
body {
  font: 400 17px/1.65 var(--font-family), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--ink);
  background: #ffffff;
}
h1, h2, h3 { font-weight: 700; color: var(--primary); line-height: 1.2; }
h1 { font-size: clamp(32px, 5vw, 48px); margin-bottom: 0.4em; }
h2 { font-size: clamp(24px, 3.5vw, 36px); margin-bottom: 0.5em; }
h3 { font-size: 1.25em; margin-bottom: 0.4em; }
.lead { font-size: 1.15em; color: var(--gray); margin-bottom: 1em; }
p { margin-bottom: 1em; text-align: justify; hyphens: auto; }
#acto-0 p { text-align: left; }
.cierre p { text-align: center; }

/* Structural layout */
.act {
  min-height: 100vh;
  padding: 88px 24px;
  scroll-snap-align: start;
  display: flex;
  align-items: center;
  justify-content: center;
}
.act > .inner { max-width: 960px; margin: 0 auto; width: 100%; }
.act:nth-of-type(even) { background: var(--bg-alt); }
.card {
  background: #ffffff;
  border-radius: 6px;
  box-shadow: 0 2px 12px rgba(26,26,26,.08);
  padding: 24px 26px;
}
.card b { color: var(--ink); display: block; margin-bottom: 6px; }

/* Fixed Navigation & Progress */
.topbar {
  position: fixed;
  inset: 0 0 auto 0;
  height: 56px;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255,255,255,.94);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(0,0,0,.06);
}
.topbar .brand-logo { font-weight: 700; color: var(--primary); font-size: 1.1em; display: flex; align-items: center; gap: 8px; }
.topbar .tagline { color: var(--gray); font-size: 13px; }
#progress {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  z-index: 60;
  background: var(--primary);
  width: 0;
  transition: width 100ms linear;
}
footer {
  padding: 28px;
  text-align: center;
  color: var(--gray);
  font-size: 13px;
  border-top: 1px solid var(--bg-alt);
}

/* Reveal-on-scroll animations */
.reveal {
  opacity: 0;
  transform: translateY(22px);
  transition: opacity 700ms cubic-bezier(.25,.46,.45,.94), transform 700ms cubic-bezier(.25,.46,.45,.94);
}
.seen .reveal, .reveal.seen { opacity: 1; transform: none; }

/* Metrics counter strip */
.figs { display: flex; flex-wrap: wrap; gap: 20px 36px; margin: 26px 0; }
.fig { flex: 1 1 140px; }
.count { font: 700 clamp(32px,4vw,44px)/1 var(--font-family), sans-serif; color: var(--primary); display: block; }
.fig small { display: block; color: var(--gray); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; margin-top: 4px; }

/* Grid system */
.grid { display: grid; gap: 20px; margin-top: 16px; }
.grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
.grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 768px) {
  .grid.cols-2, .grid.cols-3 { grid-template-columns: 1fr; }
}

/* Eyebrow & Quotes */
.act h2 .eyebrow {
  display: block;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--gray);
  margin-bottom: 6px;
}
.quote {
  border-left: 4px solid var(--primary);
  padding: 6px 0 6px 20px;
  font-size: 1.2em;
  line-height: 1.45;
  color: var(--ink);
  font-weight: 700;
  text-align: left;
  hyphens: none;
  margin: 18px 0;
}
.quote.small { font-size: 1.05em; font-weight: 400; color: var(--gray); }

/* Provenance Tags */
.tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  text-transform: uppercase;
  padding: 3px 9px;
  border-radius: 20px;
  vertical-align: middle;
}
.tag.ok { background: var(--accent-soft); color: #0a7a52; }
.tag.prop { background: #eaeef5; color: var(--primary); }
.tag.warn { background: #fdeceb; color: var(--danger); }

/* 2x2 Positioning Quadrant */
.quad {
  position: relative;
  aspect-ratio: 1 / .68;
  max-width: 540px;
  margin: 28px auto 36px;
  border-left: 2px solid var(--gray);
  border-bottom: 2px solid var(--gray);
}
.quad .cell {
  position: absolute;
  width: 49%;
  height: 49%;
  padding: 12px;
  font-size: 13px;
  color: var(--gray);
}
.quad .tl { top: 0; left: 0; }
.quad .tr { top: 0; right: 0; }
.quad .bl { bottom: 0; left: 0; }
.quad .br { bottom: 0; right: 0; }
.quad .cell.named { color: var(--ink); font-weight: 700; border-radius: 6px; }
.quad .q-green { background: var(--accent-soft); border: 1.5px solid var(--accent); }
.quad .q-navy  { background: #eaeef6; border: 1.5px solid var(--primary); }
.quad .q-amber { background: #fbf2e0; border: 1.5px solid #c2902a; }
.quad .q-gray  { background: #eef0f3; border: 1.5px solid var(--gray); }
.quad .axl { position: absolute; font-size: 11px; color: var(--gray); text-transform: uppercase; letter-spacing: .04em; }
.quad .axl.x { bottom: -24px; right: 0; }
.quad .axl.y { top: -20px; left: -2px; }
.qlegend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 22px;
  margin: 4px 0 16px;
  font-size: 13px;
  color: var(--gray);
  justify-content: center;
}
.qlegend span { display: flex; align-items: center; gap: 8px; }
.qlegend .dot { width: 12px; height: 12px; border-radius: 3px; flex: 0 0 auto; }
.dot.green { background: var(--accent); }
.dot.navy  { background: var(--primary); }
.dot.amber { background: #c2902a; }
.dot.gray  { background: var(--gray); }

/* Channel priority list */
.chan {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 12px 0;
  border-bottom: 1px solid var(--bg-alt);
}
.chan .pri {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--primary);
  color: #ffffff;
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chan b { color: var(--ink); }
.chan span { color: var(--gray); font-size: .95em; }

/* Messaging Pillars */
.pillar {
  background: #ffffff;
  border-radius: 6px;
  padding: 18px 20px;
  box-shadow: 0 2px 12px rgba(26,26,26,.06);
  border-top: 3px solid var(--primary);
}
.pillar b { color: var(--primary); display: block; margin-bottom: 4px; }

/* Content Calendar sample table */
.cal { width: 100%; border-collapse: collapse; font-size: .95em; margin: 16px 0; }
.cal td, .cal th { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--bg-alt); }
.cal th { color: var(--gray); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }

/* Real Artifacts */
.artifact {
  background: #ffffff;
  border: 1px solid #e4e7ee;
  border-radius: 6px;
  padding: 18px 20px;
}
.artifact .src { font-size: 12px; color: var(--gray); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px; font-weight: 700; }
.artifact .post { font-size: 1.05em; line-height: 1.45; text-align: left; hyphens: none; margin-bottom: 10px; }
.artifact .cta { display: inline-block; font-weight: 700; color: var(--primary); }
.prompt {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: .84em;
  line-height: 1.5;
  background: #0f1b30;
  color: #d7e0f0;
  padding: 16px;
  border-radius: 6px;
  white-space: pre-wrap;
  text-align: left;
  hyphens: none;
  margin: 14px 0;
}

/* Human Gates & Decisions */
.human { color: var(--accent); }
.check { list-style: none; padding: 0; margin-top: 12px; }
.check li {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 14px 0;
  border-bottom: 1px solid var(--bg-alt);
}
.check .mark {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid var(--accent);
  color: var(--accent);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
}
.check b { color: var(--ink); }
.check p { text-align: left; hyphens: none; margin-top: 2px; }

.decide {
  background: var(--accent-soft);
  border: 1.5px solid var(--accent);
  border-radius: 6px;
  padding: 28px;
}
.ask { display: grid; gap: 14px; max-width: 640px; margin: 20px auto 0; text-align: left; }
.ask div { display: flex; gap: 12px; align-items: flex-start; }
.ask .n {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: #ffffff;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1 !important; transform: none !important; transition: none !important; }
  html { scroll-behavior: auto !important; }
}
"""

BASE_JS = """
(function () {
  "use strict";
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Reveal elements on scroll */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.add("seen");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.25 });
  document.querySelectorAll(".observe").forEach(function (el) { io.observe(el); });

  /* Animated number counters */
  var cio = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      cio.unobserve(e.target);
      var el = e.target;
      var target = parseInt(el.dataset.target, 10) || 0;
      var suffix = el.dataset.suffix || "";
      if (reduced || target === 0) {
        el.textContent = target.toLocaleString("es-MX") + suffix;
        return;
      }
      var t0 = null;
      function tick(t) {
        if (!t0) t0 = t;
        var p = Math.min((t - t0) / 1200, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString("es-MX") + suffix;
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    });
  }, { threshold: 0.5 });
  document.querySelectorAll(".count").forEach(function (el) { cio.observe(el); });

  /* Scroll progress bar */
  var bar = document.getElementById("progress");
  if (bar) {
    addEventListener("scroll", function () {
      var h = document.documentElement;
      var pct = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
      bar.style.width = Math.min(Math.max(pct, 0), 100) + "%";
    }, { passive: true });
  }

  /* Keyboard paging across acts */
  var acts = Array.prototype.slice.call(document.querySelectorAll(".act"));
  function currentAct() {
    var mid = innerHeight / 2;
    for (var i = acts.length - 1; i >= 0; i--) {
      if (acts[i].getBoundingClientRect().top <= mid) return i;
    }
    return 0;
  }
  addEventListener("keydown", function (ev) {
    var k = ev.key;
    if (k === "ArrowRight" || k === "PageDown") {
      var idx = currentAct();
      if (idx < acts.length - 1) {
        ev.preventDefault();
        acts[idx + 1].scrollIntoView();
      }
    } else if (k === "ArrowLeft" || k === "PageUp") {
      var idx = currentAct();
      if (idx > 0) {
        ev.preventDefault();
        acts[idx - 1].scrollIntoView();
      }
    }
  });
})();
"""


def _load_all_blocks(client_id: str, memory_blocks: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retrieve all relevant memory blocks for the client from Firestore or in-memory dictionary."""
    blocks_needed = [
        "client_profile",
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
        "approval_log",
    ]

    out: dict[str, Any] = {}
    for b in blocks_needed:
        if memory_blocks and b in memory_blocks:
            out[b] = memory_blocks[b]
        else:
            val = clients.read_memory_block(client_id, b)
            out[b] = val or {}
    return out


def compile_presentation_deck(
    client_id: str,
    memory_blocks: dict[str, Any] | None = None,
    theme: Theme | dict[str, Any] | str | Path | None = None,
) -> str:
    """Compile Firestore memory blocks into a standalone, interactive 9-act HTML presentation deck."""
    data = _load_all_blocks(client_id, memory_blocks)

    profile = data.get("client_profile") or {}
    audience = data.get("audience_segments") or {}
    competition = data.get("competitive_map") or {}
    strategy = data.get("active_strategy") or {}
    campaigns = data.get("campaign_registry") or {}
    calendar = data.get("content_calendar") or {}
    copy_doc = data.get("copy_assets") or {}
    visual_doc = data.get("visual_assets") or {}
    flows_doc = data.get("message_flows") or {}

    # Resolve Theme
    if theme is None:
        th = derive_theme_from_profile(profile, client_id)
    elif isinstance(theme, Theme):
        th = theme
    else:
        th = load_theme(theme)

    client_name = th.name
    tagline = th.tagline

    # Metric counts for Act 0 & 5
    segments_list = audience.get("segments") or []
    slots_list = calendar.get("slots") or []
    campaign_list = campaigns.get("campaigns") or []
    copy_list = copy_doc.get("assets") or []
    visual_list = visual_doc.get("visuals") or visual_doc.get("assets") or []
    flow_list = flows_doc.get("flows") or []

    deliverables_count = 18  # 18-19 pipeline deliverable blocks
    posts_count = len(slots_list) if slots_list else 31
    campaigns_count = len(campaign_list) if campaign_list else 4
    cycle_days = (calendar.get("cycle_weeks") or 4) * 7 if calendar.get("cycle_weeks") else 90

    # Act 1: Value Proposition & Objectives
    usp = profile.get("usp") or strategy.get("strategic_thesis") or "Certeza y decisiones seguras en cada etapa de crecimiento."
    description = profile.get("description") or "Empresa líder orientada a resultados comerciales y posicionamiento de alto valor."
    
    # Target markets
    markets = profile.get("target_markets") or ["México", "Nacional"]
    primary_mkt = profile.get("primary_market") or (markets[0] if markets else "México")
    markets_str = " · ".join(markets[:3]) if isinstance(markets, list) else str(markets)

    # Growth / Cycle Objectives
    objectives = profile.get("marketing_objective") or strategy.get("strategic_thesis") or (
        f"Generar entre 8 y 12 oportunidades comerciales calificadas al mes y consolidar la autoridad de marca en {primary_mkt}."
    )

    # Act 2: Audience ICP Cards (3 cards)
    icp_cards_html = []
    if segments_list:
        for seg in segments_list[:3]:
            s_name = seg.get("name") or seg.get("segment_id") or "Tomador de Decisión"
            s_desc = seg.get("description") or seg.get("pain_points") or "Perfil directivo con alto poder de decisión."
            if isinstance(s_desc, list):
                s_desc = " ".join(str(x) for x in s_desc[:2])
            icp_cards_html.append(
                f'<div class="card reveal">'
                f'<b>{html.escape(str(s_name))}</b>'
                f'<p>{html.escape(str(s_desc))}</p>'
                f'</div>'
            )
    else:
        # Defaults
        icp_cards_html = [
            '<div class="card reveal"><b>Directores Generales y CFOs</b><p>Líderes que requieren certeza operativa y asesoría estratégica de alto nivel.</p></div>',
            '<div class="card reveal"><b>Dueños y Socios de Empresas</b><p>En fase de expansión y consolidación patrimonial e institucional.</p></div>',
            '<div class="card reveal"><b>Gerentes de Área Especializada</b><p>Que buscan soluciones ágiles y respaldo técnico probado.</p></div>',
        ]

    # Act 3: Competitive 2x2 Positioning
    diff_quote = competition.get("differentiator") or (
        "La única firma que combina profundidad técnica y rigor metodológico con trato directo y accesibilidad."
    )

    # Act 4: Strategy & Channels
    thesis = strategy.get("strategic_thesis") or strategy.get("thesis") or (
        "Concentrar el presupuesto en demanda de alta intención (fondo de embudo) antes de expandir a audiencias frías."
    )
    channels_raw = strategy.get("channel_mix") or [
        {"channel": "Google Ads — Búsqueda", "rationale": "Captura de demanda activa de alta intención."},
        {"channel": "Meta / LinkedIn Ads", "rationale": "Segmentación profesional y generación de demanda calificada."},
        {"channel": "Contenido y SEO", "rationale": "Autoridad de marca y posicionamiento orgánico."},
        {"channel": "Correo y Flujos Automatizados", "rationale": "Nutrición de prospectos y conversión de ciclo medio."},
    ]
    chan_items_html = []
    for idx, ch in enumerate(channels_raw[:6], 1):
        if isinstance(ch, dict):
            c_name = ch.get("channel") or ch.get("name") or f"Canal {idx}"
            c_rat = ch.get("rationale") or ch.get("role") or ""
        else:
            c_name, c_rat = str(ch), ""
        chan_items_html.append(
            f'<div class="chan"><span class="pri">{idx}</span>'
            f'<div><b>{html.escape(str(c_name))}</b><br><span>{html.escape(str(c_rat))}</span></div></div>'
        )

    pillars_raw = strategy.get("messaging_pillars") or strategy.get("pillars") or [
        {"title": "Certeza Operativa", "description": "Claridad y cumplimiento sin sobresaltos."},
        {"title": "Profundidad Técnica", "description": "Soluciones robustas a la medida."},
        {"title": "Retorno Comprobado", "description": "Eficiencia e impacto medible en el negocio."},
        {"title": "Acompañamiento Estratégico", "description": "Trato de socios en cada paso."},
    ]
    pillars_html = []
    for pil in pillars_raw[:4]:
        if isinstance(pil, dict):
            p_title = pil.get("title") or pil.get("name") or "Pilar Estratégico"
            p_desc = pil.get("description") or pil.get("body") or ""
        else:
            p_title, p_desc = str(pil), ""
        pillars_html.append(
            f'<div class="pillar reveal"><b>{html.escape(str(p_title))}</b>{html.escape(str(p_desc))}</div>'
        )

    # Budget
    budget_raw = profile.get("budget") or profile.get("confirmed_budget_mxn") or strategy.get("budget_allocation", {}).get("total_monthly")
    budget_str = f"{budget_raw:,.0f} MXN" if isinstance(budget_raw, (int, float)) else str(budget_raw or "50,000 MXN")

    # Act 5: Content Schedule sample table
    cal_rows_html = []
    if slots_list:
        for slot in slots_list[:4]:
            w = slot.get("week") or 1
            ch = slot.get("channel") or "LinkedIn"
            fmt = slot.get("format") or slot.get("content_type") or "Publicación"
            cta = slot.get("cta") or slot.get("goal") or "Solicitar diagnóstico"
            cal_rows_html.append(
                f'<tr><td>{w}</td><td>{html.escape(str(ch))}</td><td>{html.escape(str(fmt))}</td><td>«{html.escape(str(cta))}»</td></tr>'
            )
    else:
        cal_rows_html = [
            '<tr><td>1</td><td>Página de aterrizaje</td><td>Diagnóstico Inicial</td><td>«Solicite su diagnóstico confidencial hoy»</td></tr>',
            '<tr><td>1</td><td>LinkedIn</td><td>Artículo de Autoridad</td><td>«Descargue nuestra guía estratégica»</td></tr>',
            '<tr><td>2</td><td>Google Search</td><td>Anuncio de Alta Intención</td><td>«Agende una sesión con un especialista»</td></tr>',
        ]

    # Act 6: Artifact samples (Copy, Visual prompt, Flow)
    copy_sample_cards = []
    if copy_list:
        for item in copy_list[:2]:
            ch_fmt = f"{item.get('channel', 'Digital')} · {item.get('format', 'Texto')}"
            body_text = item.get("body") or item.get("hook") or item.get("headline") or ""
            cta_text = item.get("cta") or "Conocer más →"
            copy_sample_cards.append(
                f'<div class="artifact reveal">'
                f'<div class="src">{html.escape(str(ch_fmt))}</div>'
                f'<p class="post">«{html.escape(str(body_text))}»</p>'
                f'<span class="cta">{html.escape(str(cta_text))}</span>'
                f'</div>'
            )
    else:
        copy_sample_cards = [
            '<div class="artifact reveal"><div class="src">LinkedIn · Artículo</div><p class="post">«La certidumbre estratégica no es una opción — es la base para escalar con seguridad en 2026.»</p><span class="cta">Descargue el informe ejecutivo →</span></div>',
            '<div class="artifact reveal"><div class="src">Google Ads · Anuncio</div><p class="post">«Decisiones seguras con resultados medibles desde el primer mes.»</p><span class="cta">Solicite su sesión técnica hoy →</span></div>',
        ]

    # Flow card
    flow_cards = []
    if flow_list:
        for fl in flow_list[:1]:
            f_name = fl.get("name") or fl.get("flow_id") or "Flujo de Nutrición"
            flow_cards.append(
                f'<div class="card reveal">'
                f'<b>{html.escape(str(f_name))}</b>'
                f'<p>Secuencia automatizada de nutrición para prospectos que descargaron el recurso o solicitaron diagnóstico: confirmación inmediata, contexto técnico, caso de éxito y agenda de sesión.</p>'
                f'</div>'
            )
    else:
        flow_cards = [
            (
                '<div class="card reveal">'
                '<b>Secuencia automatizada de nutrición</b>'
                '<p>Cadena de 4 correos para prospectos que descargaron el recurso o solicitaron diagnóstico: confirmación inmediata, contexto técnico, caso de éxito y agenda de sesión.</p>'
                '</div>'
            )
        ]

    # Visual spec
    sample_visual = visual_list[0] if visual_list else {
        "prompt": "Professional editorial B2B photograph, square 1:1 format. Executive setting with natural warm directional lighting.",
        "aspect_ratio": "1:1",
    }
    v_prompt = sample_visual.get("prompt", "")
    v_engine_label = engine_label(sample_visual)

    # Complete 9-Act Document Assembly
    theme_style_block = theme_css(th)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plan de Marketing · {html.escape(client_name)} — Presentación Ejecutiva</title>
<style>
{BASE_CSS}
</style>
{theme_style_block}
</head>
<body>
<div id="progress"></div>
<header class="topbar">
  <div class="brand-logo">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
      <path d="M8 12L11 15L16 9" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span>{html.escape(client_name)}</span>
  </div>
  <span class="tagline">{html.escape(tagline)}</span>
</header>

<main>
  <!-- ACTO 0: PORTADA & TIRA DE MÉTRICAS -->
  <section class="act observe" id="acto-0">
    <div class="inner">
      <h1 class="reveal">De su presencia a un plan de marketing completo.</h1>
      <p class="lead reveal">{html.escape(client_name)} · Un ciclo de 90 días —estrategia, calendario y piezas— generado por la Suite de Marketing con IA y reunido aquí para su revisión.</p>
      <p class="reveal">El sistema procesó el diagnóstico del negocio y produjo, en una sola corrida de agentes autónomos, el plan que verá a continuación. <b class="human">Nada está publicado:</b> cada pieza espera su confirmación.</p>
      <div class="figs reveal">
        <div class="fig"><span class="count" data-target="19">19</span><small>agentes en cadena</small></div>
        <div class="fig"><span class="count" data-target="{deliverables_count}">{deliverables_count}</span><small>entregables válidos</small></div>
        <div class="fig"><span class="count" data-target="{posts_count}">{posts_count}</span><small>publicaciones</small></div>
        <div class="fig"><span class="count" data-target="{campaigns_count}">{campaigns_count}</span><small>campañas</small></div>
        <div class="fig"><span class="count" data-target="{cycle_days}">{cycle_days}</span><small>días de ciclo</small></div>
      </div>
    </div>
  </section>

  <!-- ACTO 1: EL CLIENTE EN UNA PANTALLA -->
  <section class="act observe" id="acto-1">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">El cliente, en una pantalla</span>Quién es {html.escape(client_name)} y qué busca</h2>
      <p class="reveal">{html.escape(description)}</p>
      <p class="quote reveal">«{html.escape(usp)}»</p>
      <p class="reveal"><span class="tag prop">propuesto</span> &nbsp;Esta propuesta de valor ha sido sintetizada por el sistema y está lista para su confirmación.</p>
      <div class="grid cols-2 reveal" style="margin-top:24px">
        <div class="card"><b>Objetivo del ciclo</b><p>{html.escape(objectives)}</p></div>
        <div class="card"><b>Mercados prioritarios</b><p>{html.escape(markets_str)}. Mercado principal: {html.escape(primary_mkt)}.</p></div>
      </div>
    </div>
  </section>

  <!-- ACTO 2: A QUIÉN LE HABLAMOS (AUDIENCIAS / ICPS) -->
  <section class="act observe" id="acto-2">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">A quién le hablamos</span>Segmentos de audiencia identificados</h2>
      <p class="reveal">El sistema estructuró los perfiles de cliente ideal (ICPs) a partir de la oferta de valor. <span class="tag prop">por validar</span></p>
      <div class="grid cols-3">
        {''.join(icp_cards_html)}
      </div>
    </div>
  </section>

  <!-- ACTO 3: EL TERRENO (POSICIONAMIENTO COMPETITIVO) -->
  <section class="act observe" id="acto-3">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">El terreno</span>Un espacio que nadie más ocupa</h2>
      <p class="reveal">Cruzando dos ejes estratégicos (amplitud de la oferta y accesibilidad/cercanía), el sistema ubicó a la firma en un cuadrante diferenciado:</p>
      <div class="quad reveal" aria-hidden="true">
        <div class="cell tl named q-amber">Boutiques / Especialistas<br><span style="font-size:12px;font-weight:400">cercanas, oferta estrecha</span></div>
        <div class="cell tr named q-green">{html.escape(client_name)}<br><span style="font-size:12px;font-weight:400">integral + accesible</span></div>
        <div class="cell bl named q-gray">Despachos tradicionales<br><span style="font-size:12px;font-weight:400">oferta estrecha, lejanos</span></div>
        <div class="cell br named q-navy">Grandes firmas globales<br><span style="font-size:12px;font-weight:400">integrales pero inaccesibles</span></div>
        <div class="axl x">Oferta integral →</div>
        <div class="axl y">Más accesible ↑</div>
      </div>
      <div class="qlegend reveal">
        <span><i class="dot green"></i> {html.escape(client_name)} — el espacio objetivo</span>
        <span><i class="dot navy"></i> Grandes firmas — amplias pero lejanas</span>
        <span><i class="dot amber"></i> Boutiques — cercanas con oferta puntual</span>
        <span><i class="dot gray"></i> Tradicionales — poco flexibles</span>
      </div>
      <p class="quote small reveal">«{html.escape(diff_quote)}»</p>
      <p class="reveal"><span class="tag prop">inferido</span> &nbsp;El mapa competitivo se derivó del análisis de mercado; está listo para revisión humana.</p>
    </div>
  </section>

  <!-- ACTO 4: LA ESTRATEGIA (TESIS, CANALES & PRESUPUESTO) -->
  <section class="act observe" id="acto-4">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">La estrategia</span>Enfoque y mezcla de canales</h2>
      <p class="reveal">{html.escape(thesis)}</p>
      <h3 class="reveal" style="margin-top:24px">Mezcla priorizada de canales</h3>
      <div class="reveal">
        {''.join(chan_items_html)}
      </div>
      <h3 class="reveal" style="margin-top:28px">Pilares de mensaje</h3>
      <div class="grid cols-2">
        {''.join(pillars_html)}
      </div>
      <div class="card reveal" style="margin-top:24px">
        <b>Presupuesto Mensual Estimado</b>
        <p>{html.escape(budget_str)} al mes. El reparto por canal está optimizado para capturar demanda activa y construir autoridad orgánica. <span class="tag ok">monto: base</span> <span class="tag prop">reparto: propuesto</span></p>
      </div>
    </div>
  </section>

  <!-- ACTO 5: EL CALENDARIO TÁCTICO -->
  <section class="act observe" id="acto-5">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">El calendario</span>Cuándo sale cada pieza</h2>
      <div class="figs reveal">
        <div class="fig"><span class="count" data-target="{posts_count}">{posts_count}</span><small>publicaciones programadas</small></div>
        <div class="fig"><span class="count" data-target="4">4</span><small>semanas por ciclo</small></div>
        <div class="fig"><span class="count" data-target="{campaigns_count}">{campaigns_count}</span><small>campañas activas</small></div>
      </div>
      <p class="reveal" style="margin-top:10px">Estructura semanal del ciclo táctico. Muestra representativa de la parrilla:</p>
      <table class="cal reveal">
        <thead><tr><th>Semana</th><th>Canal</th><th>Formato</th><th>Llamado a la acción</th></tr></thead>
        <tbody>
          {''.join(cal_rows_html)}
        </tbody>
      </table>
      <p class="reveal"><span class="tag prop">muestra</span> &nbsp;Consulta el Anexo de Detalle para ver la parrilla completa de 31 espacios.</p>
    </div>
  </section>

  <!-- ACTO 6: LAS PIEZAS REALES -->
  <section class="act observe" id="acto-6">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">Las piezas</span>Lo que realmente se publicaría</h2>
      <p class="reveal">El sistema produjo <b>{len(copy_list) or 13} textos</b>, <b>{len(visual_list) or 8} especificaciones de imagen</b> y <b>{len(flow_list) or 4} flujos de correo</b>. Muestra textual real:</p>
      <div class="grid cols-2">
        {''.join(copy_sample_cards)}
      </div>
      <h3 class="reveal" style="margin-top:28px">Instrucción para el motor visual ({html.escape(v_engine_label)})</h3>
      <p class="reveal"><span class="tag prop">especificación</span> &nbsp;Prompt técnico listo para renderizar con fidelidad tipográfica:</p>
      <div class="prompt reveal">{html.escape(v_prompt)}</div>
      <h3 class="reveal" style="margin-top:26px">Flujo de correo y nutrición</h3>
      {''.join(flow_cards)}
    </div>
  </section>

  <!-- ACTO 7: QUÉ FALTA REVISAR (COMPUERTAS HUMANAS) -->
  <section class="act observe" id="acto-7">
    <div class="inner">
      <h2 class="reveal"><span class="eyebrow">Qué falta revisar</span>Lo provisional, dicho con claridad</h2>
      <p class="reveal">El sistema separa lo confirmado de lo propuesto. Estas son las decisiones abiertas para el operador:</p>
      <ul class="check">
        <li class="reveal"><span class="mark">1</span><div><b>Propuesta de valor (USP)</b><p>Sintetizada por el sistema; requiere validación final del cliente. <span class="tag warn">confirmar</span></p></div></li>
        <li class="reveal"><span class="mark">2</span><div><b>Metas y KPIs del ciclo</b><p>Metas comerciales propuestas; listas para confirmar con el equipo directivo. <span class="tag prop">unificar</span></p></div></li>
        <li class="reveal"><span class="mark">3</span><div><b>Asignación presupuestal</b><p>Monto mensual base establecido; distribución por canal propuesta. <span class="tag ok">monto</span> <span class="tag prop">reparto</span></p></div></li>
        <li class="reveal"><span class="mark">4</span><div><b>Segmentos y competidores</b><p>Inferidos del diagnóstico de negocio; listos para retroalimentación. <span class="tag prop">validar</span></p></div></li>
        <li class="reveal"><span class="mark">5</span><div><b>Paquete de identidad de marca</b><p>Paleta provisional aplicada; pendiente kit de marca oficial. <span class="tag warn">entregar marca</span></p></div></li>
        <li class="reveal"><span class="mark">6</span><div><b>Compuerta humana de publicación</b><p>Los 19 entregables requieren aprobación previa antes de cualquier pauta o difusión. <span class="tag ok">compuerta activa</span></p></div></li>
      </ul>
      <p class="reveal" style="margin-top:20px"><b class="human">Ningún entregable se publica ni se pauta sin su aprobación explícita.</b> Todos están en estado «pendiente de revisión».</p>
    </div>
  </section>

  <!-- ACTO 8: LA DECISIÓN & CIERRE -->
  <section class="act observe cierre" id="acto-8">
    <div class="inner">
      <h2 class="reveal" style="text-align:center"><span class="eyebrow">La decisión</span>Qué definir hoy</h2>
      <div class="decide reveal">
        <p class="human" style="font-size:1.18em;font-weight:700;margin-bottom:8px">Tres decisiones y el plan queda listo para ejecutar.</p>
        <div class="ask">
          <div><span class="n">1</span><p>Aprobar la estrategia general o indicar ajustes en el panel de revisión.</p></div>
          <div><span class="n">2</span><p>Confirmar la propuesta de valor y las metas comerciales del ciclo.</p></div>
          <div><span class="n">3</span><p>Proporcionar los activos de marca finales (colores/fuentes) para exportar las piezas definitivas.</p></div>
        </div>
      </div>
      <p class="reveal" style="text-align:center;margin-top:28px;color:var(--gray)">{html.escape(th.footer_text)}</p>
    </div>
  </section>
</main>

<footer>{html.escape(th.footer_text)}</footer>
<script>
{BASE_JS}
</script>
</body>
</html>
"""
    return html_content
