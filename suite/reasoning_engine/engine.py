"""Marketing Suite Reasoning Engine implementation.

Conforms to Vertex AI Reasoning Engine interface and provides conversational
intelligence over the 19-agent marketing stack.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from infra import clients
from infra.config import settings
from infra.log import get_logger
from suite.reasoning_engine import tools

_log = get_logger("reasoning_engine")

SYSTEM_INSTRUCTION = """Eres el Asistente de Inteligencia de Marketing de QHHE (Que Hueva Hacerlo Enteprise).
Tu función es consultar, sintetizar y presentar la información generada por la suite de 19 agentes de marketing.

Reglas obligatorias:
1. Idioma: Español profesional de negocios en México (es-MX).
2. Precisión: Basa tus respuestas EXCLUSIVAMENTE en los datos de los bloques de memoria consultados mediante tus herramientas.
3. Compuertas humanas (#1ebe82): Indica con claridad si una estrategia o bloque requiere aprobación humana antes de publicarse o ejecutarse.
4. Cifras y métricas: Si mencionas presupuestos, canales o KPIs, cita los valores exactos devueltos por las herramientas.
"""


class MarketingSuiteReasoningEngine:
    """Vertex AI Reasoning Engine instance for the Agentic Marketing Suite."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.gemini_model_primary
        self.tools_map: dict[str, Callable] = {
            t.__name__: t for t in tools.TOOLS
        }
        self._is_setup = False

    def set_up(self) -> None:
        """Initialize tools and runtime clients."""
        _log.info(f"Setting up MarketingSuiteReasoningEngine with model {self.model_name}")
        self._is_setup = True

    def query(self, prompt: str, client_id: str | None = None, tool_name: str | None = None) -> dict[str, Any]:
        """Execute a conversational or tool-assisted query.

        Args:
            prompt: User question or natural language instruction.
            client_id: Target client identifier (e.g. 'u-storage', 'alonso-y-cia').
            tool_name: Optional explicit tool name to run.
        """
        if not self._is_setup:
            self.set_up()

        _log.info(f"Reasoning engine query: prompt={prompt!r}, client_id={client_id!r}, tool={tool_name!r}")

        tools_invoked = []
        tool_results = {}

        # 1. If explicit tool is requested or client_id is provided, execute domain tools
        if tool_name and tool_name in self.tools_map:
            fn = self.tools_map[tool_name]
            res = fn(client_id=client_id) if client_id else fn()
            tools_invoked.append(tool_name)
            tool_results[tool_name] = res

        elif client_id:
            # Auto-route to relevant tools based on prompt keywords
            prompt_lower = prompt.lower()
            if any(k in prompt_lower for k in ("resumen", "perfil", "cliente", "empresa", "quien es", "presupuesto")):
                res = tools.get_client_summary(client_id)
                tools_invoked.append("get_client_summary")
                tool_results["get_client_summary"] = res

            if any(k in prompt_lower for k in ("audiencia", "segmento", "competencia", "radar", "competidor", "tendencia")):
                res = tools.get_audience_and_competition(client_id)
                tools_invoked.append("get_audience_and_competition")
                tool_results["get_audience_and_competition"] = res

            if any(k in prompt_lower for k in ("estrategia", "canal", "mix", "kpi", "tesis", "presupuesto")):
                res = tools.get_marketing_strategy(client_id)
                tools_invoked.append("get_marketing_strategy")
                tool_results["get_marketing_strategy"] = res

            if any(k in prompt_lower for k in ("campaña", "calendario", "publicacion", "post", "semana")):
                res = tools.get_content_and_campaigns(client_id)
                tools_invoked.append("get_content_and_campaigns")
                tool_results["get_content_and_campaigns"] = res

            if any(k in prompt_lower for k in ("copy", "texto", "visual", "anuncio", "correo", "whatsapp", "landing")):
                res = tools.get_creative_deliverables(client_id)
                tools_invoked.append("get_creative_deliverables")
                tool_results["get_creative_deliverables"] = res

            if any(k in prompt_lower for k in ("estado", "estatus", "compuerta", "revision", "gate", "progreso")):
                res = tools.get_run_execution_status(client_id)
                tools_invoked.append("get_run_execution_status")
                tool_results["get_run_execution_status"] = res

            # Fallback: if no specific keyword matched, load summary & status
            if not tools_invoked:
                res_sum = tools.get_client_summary(client_id)
                res_stat = tools.get_run_execution_status(client_id)
                tools_invoked.extend(["get_client_summary", "get_run_execution_status"])
                tool_results["get_client_summary"] = res_sum
                tool_results["get_run_execution_status"] = res_stat

        # 2. Synthesize response
        if settings.llm_provider == "gemini" and settings.backend == "gcp":
            # Live Vertex AI Gemini synthesis
            try:
                from google import genai
                client = clients._genai_client()
                context_str = json.dumps(tool_results, ensure_ascii=False, indent=2)
                full_prompt = (
                    f"{SYSTEM_INSTRUCTION}\n\n"
                    f"Datos obtenidos de las herramientas:\n{context_str}\n\n"
                    f"Pregunta del usuario: {prompt}"
                )
                resp = client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                )
                response_text = resp.text
            except Exception as exc:
                _log.warning(f"Live Gemini synthesis fallback due to: {exc}")
                response_text = self._offline_synthesis(prompt, client_id, tool_results)
        else:
            response_text = self._offline_synthesis(prompt, client_id, tool_results)

        return {
            "response": response_text,
            "client_id": client_id,
            "tools_invoked": tools_invoked,
            "tool_data": tool_results,
        }

    def _offline_synthesis(self, prompt: str, client_id: str | None, tool_data: dict[str, Any]) -> str:
        """Deterministic offline text synthesis for fixtures / testing."""
        lines = [f"### Reporte de Inteligencia de Marketing — {client_id or 'General'}"]

        if "get_client_summary" in tool_data:
            s = tool_data["get_client_summary"]
            lines.append(f"- **Cliente:** {s.get('name')} ({s.get('industry')})")
            lines.append(f"- **Propuesta Única:** {s.get('usp')}")
            lines.append(f"- **Presupuesto Mensual:** {s.get('monthly_budget')}")
            lines.append(f"- **Estado de Validación:** {s.get('gate_status')}")

        if "get_audience_and_competition" in tool_data:
            ac = tool_data["get_audience_and_competition"]
            lines.append(f"- **Segmentos de Audiencia:** {ac.get('total_segments')} definidos.")
            lines.append(f"- **Competidores Analizados:** {ac.get('total_competitors')} identificados.")
            if ac.get("content_gaps"):
                lines.append(f"- **Oportunidades de Contenido:** {len(ac.get('content_gaps'))} brechas competitivas detectadas.")

        if "get_marketing_strategy" in tool_data:
            st = tool_data["get_marketing_strategy"]
            lines.append(f"- **Tesis Estratégica:** {st.get('strategic_thesis')}")
            if st.get("channel_mix"):
                lines.append(f"- **Mix de Canales:** {', '.join(st.get('channel_mix'))}")
            lines.append(f"- **Compuerta de Revisión:** {st.get('gate_status')}")

        if "get_content_and_campaigns" in tool_data:
            cc = tool_data["get_content_and_campaigns"]
            lines.append(f"- **Campañas Activas:** {cc.get('total_campaigns')}")
            lines.append(f"- **Publicaciones Programadas:** {cc.get('total_content_slots')} en un ciclo de {cc.get('cycle_weeks')} semanas.")

        if "get_creative_deliverables" in tool_data:
            cd = tool_data["get_creative_deliverables"]
            lines.append(f"- **Entregables Creativos:** {cd.get('copy_assets_count')} copys, {cd.get('visual_specs_count')} especificaciones visuales, {cd.get('message_flows_count')} flujos de mensajes.")

        if "get_run_execution_status" in tool_data:
            stat = tool_data["get_run_execution_status"]
            lines.append(f"- **Bloques Generados:** {stat.get('populated_blocks_count')}/{stat.get('total_blocks_checked')}")
            if stat.get("pending_human_gates"):
                lines.append(f"- **Compuertas Humanas Pendientes (#1ebe82):** {', '.join(stat.get('pending_human_gates'))}")

        lines.append(f"\n*Respuesta generada en base a la consulta:* «{prompt}»")
        return "\n".join(lines)
