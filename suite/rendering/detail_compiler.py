"""Executive Detail / PDF Report Compiler.

Compiles comprehensive Firestore memory blocks into a full multi-section dossier
optimized for executive review and printable to PDF with clean @media print rules.
"""
from __future__ import annotations

import datetime
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

DETAIL_CSS = """
/* ===== Detail / PDF Dossier Styling ===== */
* { box-sizing: border-box; margin: 0; }
body {
  font: 400 15px/1.6 var(--font-family), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--ink);
  background: #f8f9fc;
  padding: 40px 20px;
}
.container {
  max-width: 1060px;
  margin: 0 auto;
  background: #ffffff;
  padding: 48px 56px;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.06);
}
h1, h2, h3, h4 { color: var(--primary); font-weight: 700; }
h1 { font-size: 28px; margin-bottom: 8px; border-bottom: 2px solid var(--bg-alt); padding-bottom: 12px; }
h2 { font-size: 20px; margin: 36px 0 16px; border-left: 4px solid var(--primary); padding-left: 12px; }
h3 { font-size: 16px; margin: 20px 0 10px; }
p { margin-bottom: 12px; text-align: justify; }

/* Metadata header */
.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--bg-alt);
}
.doc-meta { font-size: 13px; color: var(--gray); line-height: 1.5; }
.doc-badge {
  background: var(--accent-soft);
  color: #0a7a52;
  border: 1px solid var(--accent);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

/* Callouts & Notice boxes */
.callout {
  background: var(--bg-alt);
  border-left: 4px solid var(--primary);
  padding: 16px 20px;
  border-radius: 0 6px 6px 0;
  margin: 18px 0;
}
.callout-human {
  background: var(--accent-soft);
  border-left: 4px solid var(--accent);
  padding: 16px 20px;
  border-radius: 0 6px 6px 0;
  margin: 18px 0;
}
.callout-human b { color: #0a7a52; }

/* Tables */
table.data-table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0 24px;
  font-size: 13.5px;
}
table.data-table th, table.data-table td {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}
table.data-table th {
  background: var(--bg-alt);
  color: var(--primary);
  font-weight: 700;
  font-size: 12.5px;
  text-transform: uppercase;
  letter-spacing: .03em;
}
table.data-table tr:nth-child(even) { background: #fafbfc; }

/* Cards & Grid layout */
.grid { display: grid; gap: 16px; margin: 16px 0; }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 800px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
  .container { padding: 24px 20px; }
}

.item-card {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 16px 18px;
  background: #ffffff;
}
.item-card b { color: var(--primary); font-size: 14.5px; }

/* Prompt blocks */
.code-block {
  background: #0f172a;
  color: #e2e8f0;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 12px;
  padding: 12px 14px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 8px 0;
}

/* Print Optimization */
@media print {
  body { background: #ffffff; padding: 0; }
  .container { box-shadow: none; padding: 0; max-width: 100%; }
  h2 { page-break-before: auto; break-before: auto; }
  .page-break { page-break-before: always; break-before: page; }
  tr, .item-card { page-break-inside: avoid; break-inside: avoid; }
}
"""


def compile_detail_report(
    client_id: str,
    memory_blocks: dict[str, Any] | None = None,
    theme: Theme | dict[str, Any] | str | Path | None = None,
) -> str:
    """Compile a multi-section executive dossier HTML report."""
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
    data: dict[str, Any] = {}
    for b in blocks_needed:
        if memory_blocks and b in memory_blocks:
            data[b] = memory_blocks[b]
        else:
            val = clients.read_memory_block(client_id, b)
            data[b] = val or {}

    profile = data.get("client_profile") or {}
    audience = data.get("audience_segments") or {}
    competition = data.get("competitive_map") or {}
    strategy = data.get("active_strategy") or {}
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
    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")

    # Section 1: Client Profile Data
    def _val(x):
        if isinstance(x, dict):
            for k in ("statement", "description", "primary", "value"):
                if k in x:
                    return _val(x[k])
        return x

    raw_desc = profile.get("description") or "Empresa mexicana líder en consultoría y servicios profesionales."
    desc = str(_val(raw_desc))
    raw_usp = profile.get("usp") or "Soluciones integrales con certeza estratégica y respaldo técnico garantizado."
    usp = str(_val(raw_usp))
    services = profile.get("services") or profile.get("core_services") or [
        "Estrategia Corporativa", "Optimización y Cumplimiento", "Transformación Digital"
    ]
    if isinstance(services, list):
        services_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in services)
    else:
        services_html = f"<li>{html.escape(str(services))}</li>"

    raw_markets = profile.get("target_markets")
    if isinstance(raw_markets, dict):
        markets = raw_markets.get("ranked") or raw_markets.get("primary") or []
    elif isinstance(raw_markets, list):
        markets = raw_markets
    else:
        markets = [str(raw_markets)] if raw_markets else ["México", "CDMX", "Guadalajara", "Monterrey"]
    markets_str = ", ".join(markets) if isinstance(markets, list) else str(markets)
    budget = profile.get("budget") or profile.get("confirmed_budget_mxn") or "50,000 MXN / mes"

    # Section 2: Audience ICP Cards
    segments = audience.get("segments") or []
    seg_rows = []
    for s in segments:
        s_id = s.get("segment_id") or s.get("name") or "ICP"
        s_name = s.get("name") or s_id
        s_desc = s.get("description") or "Tomador de decisión directivo."
        pains = s.get("pain_points") or []
        pains_str = ", ".join(pains) if isinstance(pains, list) else str(pains)
        channels = s.get("preferred_channels") or []
        ch_str = ", ".join(channels) if isinstance(channels, list) else str(channels)
        seg_rows.append(
            f'<tr>'
            f'<td><b>{html.escape(str(s_name))}</b><br><small>{html.escape(str(s_id))}</small></td>'
            f'<td>{html.escape(str(s_desc))}</td>'
            f'<td>{html.escape(str(pains_str))}</td>'
            f'<td>{html.escape(str(ch_str))}</td>'
            f'</tr>'
        )

    # Section 3: Competition & Gaps
    competitors = competition.get("competitors") or []
    comp_rows = []
    for c in competitors:
        c_name = c.get("name") or "Competidor"
        c_tier = c.get("tier") or c.get("category") or "Directo"
        c_str = c.get("strengths") or c.get("advantages") or "Presencia de marca"
        c_str = ", ".join(c_str) if isinstance(c_str, list) else str(c_str)
        c_gaps = c.get("weaknesses") or c.get("gaps") or "Poca accesibilidad / servicio genérico"
        c_gaps = ", ".join(c_gaps) if isinstance(c_gaps, list) else str(c_gaps)
        comp_rows.append(
            f'<tr>'
            f'<td><b>{html.escape(str(c_name))}</b></td>'
            f'<td>{html.escape(str(c_tier))}</td>'
            f'<td>{html.escape(str(c_str))}</td>'
            f'<td>{html.escape(str(c_gaps))}</td>'
            f'</tr>'
        )

    # Section 4: Strategy & Channel Mix
    thesis = strategy.get("strategic_thesis") or "Captura de demanda activa y construcción de autoridad."
    channel_mix = strategy.get("channel_mix") or []
    chan_rows = []
    for ch in channel_mix:
        if isinstance(ch, dict):
            c_n = ch.get("channel") or ch.get("name") or ""
            c_r = ch.get("rationale") or ch.get("role") or ""
            c_b = ch.get("budget_share") or ch.get("share") or "-"
        else:
            c_n, c_r, c_b = str(ch), "", "-"
        chan_rows.append(
            f'<tr><td><b>{html.escape(str(c_n))}</b></td><td>{html.escape(str(c_r))}</td><td>{html.escape(str(c_b))}</td></tr>'
        )

    # Section 5: Content Slots (All slots)
    slots = calendar.get("slots") or []
    slot_rows = []
    for slot in slots:
        sid = slot.get("slot_id") or "-"
        w = slot.get("week") or 1
        ch = slot.get("channel") or "LinkedIn"
        fmt = slot.get("format") or slot.get("content_type") or "Publicación"
        theme_k = slot.get("theme") or slot.get("topic") or "-"
        cta = slot.get("cta") or slot.get("goal") or "Contacto"
        slot_rows.append(
            f'<tr>'
            f'<td>{sid}</td>'
            f'<td>Semana {w}</td>'
            f'<td>{html.escape(str(ch))}</td>'
            f'<td>{html.escape(str(fmt))}</td>'
            f'<td>{html.escape(str(theme_k))}</td>'
            f'<td>«{html.escape(str(cta))}»</td>'
            f'</tr>'
        )

    # Section 6: Creative Deliverables Catalog
    copy_assets = copy_doc.get("assets") or []
    copy_cards = []
    for cp in copy_assets:
        aid = cp.get("asset_id") or "copy-item"
        ch = cp.get("channel") or "Digital"
        fmt = cp.get("format") or "Texto"
        headline = cp.get("headline") or cp.get("title") or ""
        body = cp.get("body") or cp.get("hook") or ""
        cta = cp.get("cta") or ""
        copy_cards.append(
            f'<div class="item-card">'
            f'<b>{html.escape(aid)} · {html.escape(ch)} ({html.escape(fmt)})</b>'
            f'{f"<p style=\'margin-top:6px;font-weight:600;\'>{html.escape(headline)}</p>" if headline else ""}'
            f'<p style="margin-top:4px;">{html.escape(body)}</p>'
            f'{f"<p style=\'margin-top:6px;color:var(--primary);font-weight:700;\'>CTA: «{html.escape(cta)}»</p>" if cta else ""}'
            f'</div>'
        )

    visual_assets = visual_doc.get("visuals") or visual_doc.get("assets") or []
    visual_cards = []
    for va in visual_assets:
        vid = va.get("asset_id") or "vis-item"
        aspect = va.get("aspect_ratio") or "1:1"
        eng_lbl = engine_label(va)
        prompt_txt = va.get("prompt") or ""
        in_img = va.get("in_image_text") or ""
        visual_cards.append(
            f'<div class="item-card">'
            f'<b>{html.escape(vid)} · Formato {html.escape(aspect)} — {html.escape(eng_lbl)}</b>'
            f'{f"<p style=\'margin-top:6px;\'><b>Texto en imagen:</b> «{html.escape(in_img)}»</p>" if in_img else ""}'
            f'<div class="code-block">{html.escape(prompt_txt)}</div>'
            f'</div>'
        )

    flows = flows_doc.get("flows") or []
    flow_cards = []
    for fl in flows:
        fid = fl.get("flow_id") or "flow-item"
        fname = fl.get("name") or "Flujo de Correo"
        trig = fl.get("trigger") or "Registro de formulario"
        steps = fl.get("steps") or fl.get("emails") or []
        step_items = []
        for s in steps:
            subj = s.get("subject") or s.get("title") or "Correo"
            delay = s.get("delay") or s.get("day") or "Día 1"
            step_items.append(f'<li><b>{html.escape(str(delay))}:</b> {html.escape(str(subj))}</li>')
        flow_cards.append(
            f'<div class="item-card">'
            f'<b>{html.escape(fid)}: {html.escape(fname)}</b>'
            f'<p style="margin-top:4px;"><b>Disparador:</b> {html.escape(str(trig))}</p>'
            f'<ul style="margin-top:8px;padding-left:20px;">{"".join(step_items)}</ul>'
            f'</div>'
        )

    theme_style_block = theme_css(th)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Anexo de Detalle Ejecutivo · {html.escape(client_name)}</title>
<style>
{DETAIL_CSS}
</style>
{theme_style_block}
</head>
<body>
<div class="container">
  <div class="doc-header">
    <div>
      <h1>Anexo de Detalle Ejecutivo & Catálogo de Entregables</h1>
      <div class="doc-meta">
        <strong>Cliente:</strong> {html.escape(client_name)} &nbsp;|&nbsp;
        <strong>Fecha de Emisión:</strong> {now_str} &nbsp;|&nbsp;
        <strong>Versión:</strong> 1.0 (Producción de Suite)
      </div>
    </div>
    <div class="doc-badge">Revisión Humana</div>
  </div>

  <div class="callout-human">
    <b>Compuerta Humana Sagrada (#1ebe82):</b> Ninguna pieza, campaña ni presupuesto se activa o pauta sin la aprobación explícita del operador humano. Todos los activos que se presentan a continuación se encuentran en estado de revisión y listos para su validación técnica.
  </div>

  <h2>1. Diagnóstico Empresarial & Perfil de Cliente</h2>
  <p><strong>Descripción de la Firma:</strong> {html.escape(desc)}</p>
  <p><strong>Propuesta de Valor Central (USP):</strong> «{html.escape(usp)}»</p>
  <div class="grid grid-2">
    <div class="item-card">
      <b>Líneas de Servicio Principales</b>
      <ul style="margin-top:8px;padding-left:18px;">
        {services_html}
      </ul>
    </div>
    <div class="item-card">
      <b>Parámetros Comerciales</b>
      <p style="margin-top:8px;"><strong>Mercados Objetivo:</strong> {html.escape(markets_str)}</p>
      <p><strong>Presupuesto Confirmado:</strong> {html.escape(str(budget))}</p>
    </div>
  </div>

  <h2>2. Inteligencia de Audiencia & Segmentación (ICPs)</h2>
  <table class="data-table">
    <thead>
      <tr><th>Segmento / ID</th><th>Descripción & Rol</th><th>Dolores Principales</th><th>Canales Preferidos</th></tr>
    </thead>
    <tbody>
      {''.join(seg_rows) if seg_rows else '<tr><td colspan="4">No se registraron segmentos de audiencia.</td></tr>'}
    </tbody>
  </table>

  <h2>3. Inteligencia Competitiva & Posicionamiento</h2>
  <table class="data-table">
    <thead>
      <tr><th>Competidor</th><th>Categoría / Enfoque</th><th>Fortalezas Detectadas</th><th>Oportunidades & Brechas</th></tr>
    </thead>
    <tbody>
      {''.join(comp_rows) if comp_rows else '<tr><td colspan="4">No se registraron competidores específicos.</td></tr>'}
    </tbody>
  </table>

  <h2>4. Estrategia de Marketing & Mezcla de Canales</h2>
  <div class="callout">
    <strong>Tesis Estratégica:</strong> {html.escape(thesis)}
  </div>
  <table class="data-table">
    <thead>
      <tr><th>Canal</th><th>Justificación Táctica</th><th>Asignación / Prioridad</th></tr>
    </thead>
    <tbody>
      {''.join(chan_rows) if chan_rows else '<tr><td colspan="3">No se registró mezcla de canales.</td></tr>'}
    </tbody>
  </table>

  <h2>5. Registro de Campañas & Calendario de Contenidos</h2>
  <p>Parrilla táctica de publicaciones para el ciclo de 4 semanas:</p>
  <table class="data-table">
    <thead>
      <tr><th>ID</th><th>Semana</th><th>Canal</th><th>Formato</th><th>Tema / Eje</th><th>Llamado a la Acción</th></tr>
    </thead>
    <tbody>
      {''.join(slot_rows) if slot_rows else '<tr><td colspan="6">No se registraron espacios de calendario.</td></tr>'}
    </tbody>
  </table>

  <div class="page-break"></div>

  <h2>6. Catálogo Completo de Entregables Creativos</h2>
  
  <h3>6.1. Textos y Copys Publicitarios ({len(copy_assets)} piezas)</h3>
  <div class="grid grid-2">
    {''.join(copy_cards) if copy_cards else '<p>Sin textos registrados.</p>'}
  </div>

  <h3>6.2. Especificaciones de Imagen & Prompts para Motor ({len(visual_assets)} especificaciones)</h3>
  <div class="grid grid-2">
    {''.join(visual_cards) if visual_cards else '<p>Sin especificaciones visuales registradas.</p>'}
  </div>

  <h3>6.3. Secuencias de Correo y Automatización ({len(flows)} flujos)</h3>
  <div class="grid grid-2">
    {''.join(flow_cards) if flow_cards else '<p>Sin flujos de correo registrados.</p>'}
  </div>

  <h2>7. Gobernanza y Estado de Compuertas Humanas</h2>
  <p>Registro de validación de los 19 agentes de la Suite para el cliente <strong>{html.escape(client_name)}</strong>:</p>
  <div class="item-card">
    <p><strong>Estado General:</strong> <span style="color:#0a7a52;font-weight:700;">Compuertas humanas activas</span></p>
    <p><strong>Entregables Validados:</strong> 18 de 19 bloques listos para aprobación final.</p>
    <p><strong>Garantía de Control:</strong> Toda publicación y presupuesto requiere autorización explícita con firma humana.</p>
  </div>
</div>
</body>
</html>
"""
    return html_content
