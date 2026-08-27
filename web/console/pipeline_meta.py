"""Metadata and presentation helpers for the 19-agent pipeline and deliverables.

Provides human-friendly descriptions, layer grouping, live status computation,
and deliverable card formatters for the review console.
"""
from __future__ import annotations

from typing import Any

# Complete registry of the 19 agents across all 6 layers
PIPELINE_AGENTS: dict[str, dict[str, Any]] = {
    "1.1": {
        "id": "1.1",
        "name": "Business Diagnostics",
        "title": "Diagnóstico de Negocio",
        "layer": "L1",
        "layer_title": "Capa 1: Inteligencia & Diagnóstico",
        "block": "client_profile",
        "reads": (),
        "gate": "review",
        "gate_label": "Revisión Humana Requerida",
        "mission": "Analiza la presencia digital de la empresa, extrae su propuesta de valor, analiza el modelo comercial y consolida la identidad inicial de la marca.",
        "deliverable": "Ficha Maestra del Cliente (`client_profile`): servicios, propuestas de valor, colores de marca, tono de voz y canales.",
        "handoff": "Habilita la base estratégica para Inteligencia de Audiencia (1.2), Competencia (1.3) y Radar de Tendencias (1.4).",
    },
    "1.2": {
        "id": "1.2",
        "name": "Audience Intelligence",
        "title": "Inteligencia de Audiencias",
        "layer": "L1",
        "layer_title": "Capa 1: Inteligencia & Diagnóstico",
        "block": "audience_segments",
        "reads": ("client_profile",),
        "gate": "review",
        "gate_label": "Revisión Humana Requerida",
        "mission": "Segmenta y perfila a los clientes ideales (ICP), detectando dolores prioritarios, motivaciones de compra, objeciones y hábitos de consumo.",
        "deliverable": "Segmentos de Audiencia (`audience_segments`): clusters demográficos y firmográficos listos para pauta y contenido.",
        "handoff": "Entrega los perfiles de comprador a Estrategia (2.1), Campañas (2.2) y Motor de Redacción (4.1).",
    },
    "1.3": {
        "id": "1.3",
        "name": "Competitive Intelligence",
        "title": "Auditoría de Competencia",
        "layer": "L1",
        "layer_title": "Capa 1: Inteligencia & Diagnóstico",
        "block": "competitive_map",
        "reads": ("client_profile",),
        "gate": "review-only",
        "gate_label": "Revisión Informativa",
        "mission": "Mapea competidores directos e indirectos, cuadrantes de posicionamiento, fortalezas, debilidades y oportunidades de diferenciación.",
        "deliverable": "Mapa Competitivo (`competitive_map`): matriz de diferenciación y ángulos para destacar frente a rivales.",
        "handoff": "Informa los pilares del Orquestador de Estrategia (2.1) y los ángulos de ataque de Copy (4.1).",
    },
    "1.4": {
        "id": "1.4",
        "name": "Trend Radar",
        "title": "Radar de Tendencias",
        "layer": "L1",
        "layer_title": "Capa 1: Inteligencia & Diagnóstico",
        "block": "trend_signals",
        "reads": ("client_profile",),
        "gate": "autonomous",
        "gate_label": "Autónomo",
        "mission": "Monitorea señales emergentes en el sector, temas de conversación en tendencia, hashtags y oportunidades estacionales.",
        "deliverable": "Señales de Tendencia (`trend_signals`): temas de alto impacto para sincronizar campañas y contenidos.",
        "handoff": "Alimenta la estrategia activa (2.1) y la planeación de contenido mensual (3.1).",
    },
    "2.1": {
        "id": "2.1",
        "name": "Strategy Orchestrator",
        "title": "Orquestador de Estrategia",
        "layer": "L2",
        "layer_title": "Capa 2: Estrategia & Plan de Crecimiento",
        "block": "active_strategy",
        "reads": ("client_profile", "audience_segments", "competitive_map", "trend_signals"),
        "gate": "binding",
        "gate_label": "Aprobación Vinculante",
        "mission": "Sintetiza la inteligencia de mercado y formula la tesis estratégica de crecimiento, presupuesto por canal y contratos de KPI.",
        "deliverable": "Estrategia Activa (`active_strategy`) y Contratos de KPI (`kpi_contracts`): objetivos SMART, presupuestos y metas de conversión.",
        "handoff": "Gobierna todo el plan mensual (3.1), planificación de campañas (2.2) y el modelo analítico (6.1).",
    },
    "2.2": {
        "id": "2.2",
        "name": "Campaign Planner",
        "title": "Planificador de Campañas",
        "layer": "L2",
        "layer_title": "Capa 2: Estrategia & Plan de Crecimiento",
        "block": "campaign_registry",
        "reads": ("active_strategy", "client_profile", "audience_segments"),
        "gate": "review",
        "gate_label": "Revisión Humana Requerida",
        "mission": "Estructura las campañas por etapa del embudo comercial (atracción, consideración, conversión y retención).",
        "deliverable": "Registro de Campañas (`campaign_registry`): arquitectura de campañas, audiencias asignadas y presupuesto.",
        "handoff": "Determina los calendarios editoriales (3.1/3.2), landing pages (4.3) y pauta publicitaria (5.1).",
    },
    "3.1": {
        "id": "3.1",
        "name": "Monthly Marketing Deck",
        "title": "Deck de Marketing Mensual",
        "layer": "L3",
        "layer_title": "Capa 3: Planificación de Contenidos",
        "block": "content_plan",
        "reads": ("campaign_registry", "audience_segments", "active_strategy", "trend_signals"),
        "gate": "review",
        "gate_label": "Revisión Humana Requerida",
        "mission": "Diseña la narrativa de contenidos del mes, temas clave por semana y distribución de formatos para medios y redes.",
        "deliverable": "Plan de Contenido (`content_plan`): pilares temáticos, formatos requeridos y ángulos editoriales.",
        "handoff": "Entrega las pautas al Programador de Contenido (3.2) para el armado de la parrilla fecha por fecha.",
    },
    "3.2": {
        "id": "3.2",
        "name": "Content Scheduler",
        "title": "Programador de Contenido",
        "layer": "L3",
        "layer_title": "Capa 3: Planificación de Contenidos",
        "block": "content_calendar",
        "reads": ("content_plan", "campaign_registry"),
        "gate": "review",
        "gate_label": "Revisión Humana Requerida",
        "mission": "Traduce el plan en un calendario editorial de 4 semanas con fecha, hora, canal, formato y copy teaser.",
        "deliverable": "Calendario Editorial (`content_calendar`): cronograma de 4 semanas con slots específicos listos para producción.",
        "handoff": "Insumo directo para los redactores de copy (4.1), diseñadores visuales (4.2) y publicador (5.2).",
    },
    "3.3": {
        "id": "3.3",
        "name": "Approval Workflow",
        "title": "Control de Calidad de Calendario",
        "layer": "L3",
        "layer_title": "Capa 3: Planificación de Contenidos",
        "block": "approval_log",
        "reads": ("content_calendar",),
        "gate": "queue-mgr",
        "gate_label": "Gestor de Cola",
        "mission": "Verifica que el calendario cumpla con las políticas de marca y frecuencia antes de iniciar producción intensiva.",
        "deliverable": "Bitácora de Aprobación (`approval_log`): registro de validación de contenidos.",
        "handoff": "Habilita la producción creativa segura de la Capa 4.",
    },
    "4.1": {
        "id": "4.1",
        "name": "Copy + Prompt Engine",
        "title": "Motor de Redacción & Copy",
        "layer": "L4",
        "layer_title": "Capa 4: Producción Creativa",
        "block": "copy_assets",
        "reads": ("content_calendar", "audience_segments", "competitive_map", "client_profile"),
        "gate": "risk-tiered",
        "gate_label": "Revisión por Nivel de Riesgo",
        "mission": "Redacta todos los textos persuasivos: titulares H1/H2, copies de anuncios, publicaciones sociales, CTAs y variantes A/B.",
        "deliverable": "Activos de Copy (`copy_assets`): librería de textos listos organizados por canal y audiencia.",
        "handoff": "Entrega los textos para briefs visuales (4.2), páginas de aterrizaje (4.3) y pauta en Meta (5.1).",
    },
    "4.2": {
        "id": "4.2",
        "name": "Visual Creative",
        "title": "Creatividad Visual & Prompts",
        "layer": "L4",
        "layer_title": "Capa 4: Producción Creativa",
        "block": "visual_assets",
        "reads": ("content_calendar", "copy_assets", "client_profile"),
        "gate": "batch-review",
        "gate_label": "Revisión en Lote",
        "mission": "Genera los conceptos gráficos, dirección de arte, especificaciones de imagen/video y prompts generativos de diseño.",
        "deliverable": "Activos Visuales (`visual_assets`): briefs de diseño, proporciones (1:1, 9:16, 16:9) y conceptos gráficos.",
        "handoff": "Entrega los creativos visuales para publicación orgánica (5.2) y anuncios pautados (5.1).",
    },
    "4.3": {
        "id": "4.3",
        "name": "Web + Landing Pages",
        "title": "Páginas Web & Landing Pages",
        "layer": "L4",
        "layer_title": "Capa 4: Producción Creativa",
        "block": "page_assets",
        "reads": ("campaign_registry", "audience_segments", "copy_assets"),
        "gate": "full-review",
        "gate_label": "Revisión Completa",
        "mission": "Estructura la arquitectura de las páginas de aterrizaje: secciones de valor, formularios, prueba social y CTA.",
        "deliverable": "Activos de Página (`page_assets`): wireframes y copys de landing pages para capturar prospectos.",
        "handoff": "Provee el destino de conversión para las campañas de pauta publicitaria (5.1).",
    },
    "4.4": {
        "id": "4.4",
        "name": "Email / WhatsApp",
        "title": "Mensajería, Email & WhatsApp",
        "layer": "L4",
        "layer_title": "Capa 4: Producción Creativa",
        "block": "message_flows",
        "reads": ("audience_segments", "content_calendar"),
        "gate": "first-deploy",
        "gate_label": "Primer Despliegue",
        "mission": "Diseña las secuencias automatizadas de nutrición por correo electrónico y flujos de conversación de WhatsApp.",
        "deliverable": "Flujos de Mensajes (`message_flows`): plantillas de correo y guiones de mensajería para seguimiento de prospectos.",
        "handoff": "Alimenta el sistema de captura y nutrición de prospectos (5.3).",
    },
    "5.1": {
        "id": "5.1",
        "name": "Campaign Launcher",
        "title": "Lanzador de Pauta Publicitaria",
        "layer": "L5",
        "layer_title": "Capa 5: Distribución & Canales",
        "block": "ad_campaign_log",
        "reads": ("campaign_registry", "copy_assets", "page_assets", "active_strategy"),
        "gate": "financial-auth",
        "gate_label": "Autorización Financiera (#1ebe82)",
        "mission": "Ensambla la pauta en Meta Ads / Google Ads, configura presupuestos y aplica el candado financiero `#1ebe82`.",
        "deliverable": "Registro de Campañas de Pauta (`ad_campaign_log`): campañas estructuradas con candado financiero verificado.",
        "handoff": "Envía los eventos de rendimiento publicitario a Analítica de Rendimiento (6.1).",
    },
    "5.2": {
        "id": "5.2",
        "name": "Social Publisher",
        "title": "Publicador en Redes Sociales",
        "layer": "L5",
        "layer_title": "Capa 5: Distribución & Canales",
        "block": "publish_log",
        "reads": ("content_calendar", "copy_assets", "visual_assets"),
        "gate": "autonomous",
        "gate_label": "Autónomo",
        "mission": "Programa y organiza la distribución orgánica en los canales de la marca (LinkedIn, Instagram, etc.).",
        "deliverable": "Bitácora de Publicaciones (`publish_log`): confirmación de fechas y slots de distribución orgánica.",
        "handoff": "Informa los contenidos en circulación a Analítica de Rendimiento (6.1).",
    },
    "5.3": {
        "id": "5.3",
        "name": "Lead Capture + Nurture",
        "title": "Captura & Nutrición de Prospectos",
        "layer": "L5",
        "layer_title": "Capa 5: Distribución & Canales",
        "block": "lead_register",
        "reads": ("audience_segments", "message_flows"),
        "gate": "conditional",
        "gate_label": "Condicional",
        "mission": "Conecta formularios con secuencias de nutrición, scoring de prospectos y asignación al equipo comercial.",
        "deliverable": "Registro de Prospectos (`lead_register`): modelo de captura y calificación de leads.",
        "handoff": "Reporta el volumen de prospectos y tasas de conversión a la Capa 6.",
    },
    "6.1": {
        "id": "6.1",
        "name": "Performance Analytics",
        "title": "Analítica de Rendimiento",
        "layer": "L6",
        "layer_title": "Capa 6: Analítica & Aprendizaje",
        "block": "performance_history",
        "reads": ("ad_campaign_log", "publish_log", "lead_register", "active_strategy", "kpi_contracts"),
        "gate": "auto+alert",
        "gate_label": "Automático + Alerta",
        "mission": "Consolida las métricas de tráfico, costo por lead (CPL), conversiones y cumplimiento de los contratos de KPI.",
        "deliverable": "Historial de Rendimiento (`performance_history`): tablero unificado de métricas reales vs. metas.",
        "handoff": "Base empírica para el Reporte Ejecutivo (6.2) y el Motor de Optimización (6.3).",
    },
    "6.2": {
        "id": "6.2",
        "name": "Client Reporting",
        "title": "Reporte Ejecutivo de Cliente",
        "layer": "L6",
        "layer_title": "Capa 6: Analítica & Aprendizaje",
        "block": "client_health_score",
        "reads": ("performance_history", "active_strategy", "client_profile"),
        "gate": "pre-client",
        "gate_label": "Revisión Pre-Cliente",
        "mission": "Calcula el puntaje de salud de la cuenta, balance de inversión y recomendaciones estratégicas para la dirección.",
        "deliverable": "Score de Salud del Cliente (`client_health_score`): evaluación de resultados y próximos pasos.",
        "handoff": "Informa la propuesta comercial final y retroalimenta la siguiente corrida trimestral.",
    },
    "6.3": {
        "id": "6.3",
        "name": "Optimization Engine",
        "title": "Motor de Optimización Continua",
        "layer": "L6",
        "layer_title": "Capa 6: Analítica & Aprendizaje",
        "block": "content_learnings",
        "reads": ("performance_history", "content_learnings"),
        "gate": "bounded-auto",
        "gate_label": "Autónomo Acotado",
        "mission": "Analiza qué mensajes y audiencias funcionaron mejor, destilando aprendizajes para refinar el siguiente ciclo.",
        "deliverable": "Aprendizajes de Contenido (`content_learnings`): insights destilados que mejoran los prompts futuros.",
        "handoff": "Cierra el ciclo virtuoso de retroalimentación de la suite de 19 agentes.",
    },
}

LAYER_CONFIG = [
    {"id": "L1", "title": "Capa 1: Inteligencia & Diagnóstico de Mercado", "desc": "Compila la identidad comercial, audiencias, competencia y tendencias."},
    {"id": "L2", "title": "Capa 2: Estrategia Comercial & Objetivos SMART", "desc": "Orquesta el plan rector, arquitectura de campañas y contratos de KPI."},
    {"id": "L3", "title": "Capa 3: Planificación Editorial & Contenidos", "desc": "Estructura la narrativa mensual y el calendario de 4 semanas."},
    {"id": "L4", "title": "Capa 4: Producción Creativa Multicanal", "desc": "Redacta copies, crea conceptos visuales, landing pages y flujos de email."},
    {"id": "L5", "title": "Capa 5: Distribución, Pauta & Nutrición", "desc": "Prepara anuncios pautados con candado financiero, redes sociales y captura de leads."},
    {"id": "L6", "title": "Capa 6: Analítica, Salud de Cuenta & Aprendizaje", "desc": "Evalúa KPIs, genera reportes ejecutivos y retroalimenta el sistema."},
]


def build_pipeline_tree(session_dict: dict) -> dict[str, Any]:
    """Augment session dictionary with live status for all 19 agents organized by layer."""
    approved_blocks = set(session_dict.get("blocks") or [])
    pending_blocks = set(session_dict.get("pending") or [])
    transcript = session_dict.get("transcript") or []
    is_paused = session_dict.get("paused", False)

    # Map transcript by agent id
    transcript_by_id = {t.get("agent"): t for t in transcript if t.get("agent")}

    # Determine running agent if in flight
    running_agent_id = None
    if not is_paused and len(approved_blocks) < 19:
        for aid, meta in PIPELINE_AGENTS.items():
            if meta["block"] not in approved_blocks and meta["block"] not in pending_blocks:
                running_agent_id = aid
                break

    layers_out = []
    total_completed = 0

    for l_conf in LAYER_CONFIG:
        layer_id = l_conf["id"]
        agents_in_layer = [meta for meta in PIPELINE_AGENTS.values() if meta["layer"] == layer_id]
        augmented_agents = []

        for meta in agents_in_layer:
            aid = meta["id"]
            block = meta["block"]
            t_record = transcript_by_id.get(aid)

            # Determine live status
            if block in approved_blocks or (t_record and t_record.get("valid") and block not in pending_blocks):
                status = "completed"
                status_label = "Completado"
                status_class = "ok"
                total_completed += 1
                is_done = True
            elif block in pending_blocks:
                status = "pending"
                status_label = "Pausado: Requiere Aprobación"
                status_class = "pausa"
                is_done = False
            elif aid == running_agent_id:
                status = "running"
                status_label = "Trabajando..."
                status_class = "running"
                is_done = False
            elif t_record and not t_record.get("valid"):
                status = "error"
                status_label = f"Error: {t_record.get('error')}"
                status_class = "bad"
                is_done = False
            else:
                status = "waiting"
                status_label = "En espera de dependencias"
                status_class = "waiting"
                is_done = False

            augmented_agents.append({
                **meta,
                "status": status,
                "status_label": status_label,
                "status_class": status_class,
                "is_done": is_done,
                "has_block": block in approved_blocks or block in pending_blocks,
                "gate_status": (t_record.get("gate_status") if t_record else None) or ("pending_review" if block in pending_blocks else None),
            })

        layer_completed = sum(1 for a in augmented_agents if a["is_done"])
        layers_out.append({
            **l_conf,
            "agents": augmented_agents,
            "completed_count": layer_completed,
            "total_count": len(augmented_agents),
            "is_layer_done": layer_completed == len(augmented_agents),
            "is_layer_active": any(a["status"] in ("running", "pending") for a in augmented_agents),
        })

    percent = int((total_completed / 19) * 100) if total_completed > 0 else 0

    return {
        "layers": layers_out,
        "total_completed": total_completed,
        "total_agents": 19,
        "percent": percent,
        "running_agent": PIPELINE_AGENTS.get(running_agent_id),
    }


def find_agent_for_block(block_name: str) -> dict[str, Any] | None:
    """Find agent metadata for a given memory block name."""
    for meta in PIPELINE_AGENTS.values():
        if meta["block"] == block_name:
            return meta
    return None
