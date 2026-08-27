"""Vistas de la consola de revisión (es-MX; todo requiere sesión iniciada)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services

_SAMPLE_INPUT = Path(__file__).resolve().parents[2] / "suite/inputs/acme.json"


@login_required
def panel(request):
    sessions = services.list_sessions()
    return render(request, "panel.html", {
        "sessions": sessions,
        "pendientes": sum(len(s["pending"]) for s in sessions),
    })


@login_required
def session_detail(request, session_id):
    session = services.get_session(session_id)
    if session is None:
        raise Http404("No existe esa corrida.")
    return render(request, "sesion.html", {"s": session})


@login_required
@require_POST
def session_resume(request, session_id):
    if services.resume_run(session_id):
        messages.success(request, "Corrida reanudada; recarga en unos segundos.")
    else:
        messages.info(request, "La corrida no tiene pausa pendiente.")
    return redirect("sesion", session_id=session_id)


@login_required
def block_review(request, client_id, block):
    detail = services.block_detail(client_id, block)
    if detail["payload"] is None and detail["gate_status"] is None:
        raise Http404("No existe ese bloque.")
    detail["payload_json"] = json.dumps(detail["payload"], indent=2, ensure_ascii=False)
    return render(request, "bloque.html", {"b": detail,
                                           "volver": request.GET.get("volver", "")})


@login_required
@require_POST
def block_decide(request, client_id, block):
    decision = request.POST.get("decision", "")
    note = request.POST.get("nota", "").strip()
    try:
        services.decide(client_id, block, decision,
                        actor=request.user.get_username(), note=note)
    except ValueError:
        messages.error(request, "Decisión no válida.")
        return redirect("bloque", client_id=client_id, block=block)
    labels = {"approved": "aprobado", "returned": "devuelto", "blocked": "bloqueado"}
    messages.success(request, f"Bloque «{block}» {labels[decision]}.")
    volver = request.POST.get("volver", "")
    if volver:
        return redirect("sesion", session_id=volver)
    return redirect("panel")


def _build_inputs_from_form(post: dict) -> tuple[str, dict]:
    """Convert structured form fields or raw JSON into the canonical client input payload."""
    raw_json = post.get("inputs_json", "").strip()
    use_raw = post.get("use_raw_json") == "1"

    # If raw JSON is provided without structured company_name or in explicit raw mode
    if raw_json and (use_raw or not post.get("company_name")):
        inputs = json.loads(raw_json)
        client_id = post.get("client_id", "").strip() or inputs.get("client_id", "")
        return client_id, inputs

    # Structured visual wizard / form builder
    company_name = post.get("company_name", "").strip()
    trade_name = post.get("trade_name", "").strip() or company_name
    website_url = post.get("website_url", "").strip()
    industry = post.get("industry", "").strip()
    offer_desc = post.get("offer_description", "").strip()
    target_customer = post.get("target_customer", "").strip()
    value_props = [v.strip() for v in post.get("value_propositions", "").splitlines() if v.strip()]
    if not value_props and offer_desc:
        value_props = [offer_desc]
    services_list = [s.strip() for s in post.get("services_extracted", "").splitlines() if s.strip()]
    if not services_list and offer_desc:
        services_list = [offer_desc]

    target_markets = [m.strip() for m in post.get("target_markets", "México").split(",") if m.strip()]
    primary_market = post.get("primary_market", "México").strip()

    client_id = post.get("client_id", "").strip()
    if not client_id and company_name:
        import re
        client_id = re.sub(r"[^a-zA-Z0-9_-]", "-", company_name.lower().strip()).strip("-")
    client_id = client_id or "nuevo-cliente"

    marketing_obj = post.get("marketing_objective", "").strip() or None
    monthly_budget = post.get("monthly_budget", "").strip() or None
    sales_cycle = post.get("sales_cycle", "").strip() or None
    languages = [lang.strip() for lang in post.get("languages", "es-MX").split(",") if lang.strip()]

    channels = [c.strip() for c in post.get("channels", "Meta Ads, Email Marketing").split(",") if c.strip()]
    voice_tone = post.get("brand_voice_tone", "professional/corporate").strip()
    voice_tokens = [t.strip() for t in post.get("brand_voice_tokens", "profesional, confiable, orientado a resultados").split(",") if t.strip()]

    inputs = {
        "client_id": client_id,
        "quick_start_form": {
            "company_name": company_name or trade_name or client_id,
            "website_url": website_url,
            "industry": industry,
            "offer_description": offer_desc,
            "target_markets": target_markets,
            "primary_market": primary_market,
            "target_customer": target_customer,
            "marketing_objective": marketing_obj,
            "monthly_budget": monthly_budget,
            "sales_cycle": sales_cycle,
            "languages": languages,
            "notes": post.get("notes", "").strip(),
        },
        "scraper_output": {
            "scrape_status": "manual_entry",
            "meta_description": offer_desc,
            "about_text_excerpt": offer_desc,
            "services_extracted": services_list,
            "value_propositions": value_props,
            "primary_cta": post.get("primary_cta", "Agendar llamada de diagnóstico").strip(),
            "locations_detected": target_markets,
            "visual_identity": {
                "top_5_hex": [post.get("primary_hex", "#0E6B5C").strip()] if post.get("primary_hex") else [],
                "heading_font": post.get("heading_font", "").strip() or None,
                "body_font": post.get("body_font", "").strip() or None,
                "logo": {"url": post.get("logo_url", "").strip() or None},
            },
            "brand_voice": {
                "detected_language": "es",
                "vocabulary_register": voice_tone,
                "proposed_voice_tokens": voice_tokens,
                "sample_sentences": [offer_desc] if offer_desc else [],
            },
            "company_context": {
                "channels_recommended": channels,
                "social_links_found": {},
            },
        },
        "operator_notes": post.get("operator_notes", "").strip() or f"Cliente incorporado vía Asistente Interactivo de Consola para {client_id}.",
    }
    return client_id, inputs


@login_required
def run_new(request):
    if request.method == "POST":
        try:
            client_id, inputs = _build_inputs_from_form(request.POST)
        except json.JSONDecodeError as e:
            messages.error(request, f"El JSON de entrada no es válido: {e}")
            return render(request, "nueva.html", {
                "inputs_json": request.POST.get("inputs_json", ""),
                "client_id": request.POST.get("client_id", ""),
            })
        except Exception as e:
            messages.error(request, f"Error al procesar los datos del cliente: {e}")
            return render(request, "nueva.html", {
                "inputs_json": request.POST.get("inputs_json", ""),
                "client_id": request.POST.get("client_id", ""),
            })

        if not client_id:
            messages.error(request, "Falta el identificador del cliente o el nombre de la empresa.")
            return render(request, "nueva.html", {
                "inputs_json": request.POST.get("inputs_json", ""),
                "client_id": "",
            })

        session_id = f"run-{time.strftime('%Y%m%d-%H%M%S')}"
        services.start_run(
            client_id,
            inputs,
            auto_approve=bool(request.POST.get("auto_approve")),
            session_id=session_id,
        )
        messages.success(request, f"Corrida {session_id} iniciada con éxito para «{client_id}».")
        return redirect("sesion", session_id=session_id)

    sample = _SAMPLE_INPUT.read_text(encoding="utf-8") if _SAMPLE_INPUT.exists() else "{}"
    return render(request, "nueva.html", {
        "inputs_json": sample,
        "client_id": "",
    })


@login_required
def proposal_view(request, client_id: str, doc_type: str = "deck"):
    """Render standalone HTML presentation deck or detail report in browser."""
    try:
        html_doc, _ = services.get_client_proposal(client_id, doc_type=doc_type)
        return HttpResponse(html_doc, content_type="text/html; charset=utf-8")
    except Exception as e:
        messages.error(request, f"Error al generar propuesta: {e}")
        return redirect("panel")


@login_required
def proposal_download(request, client_id: str, doc_type: str = "deck"):
    """Download the standalone proposal as an HTML attachment."""
    try:
        html_doc, filename = services.get_client_proposal(client_id, doc_type=doc_type)
        resp = HttpResponse(html_doc, content_type="text/html; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        messages.error(request, f"Error al descargar propuesta: {e}")
        return redirect("panel")


@login_required
def proposal_generate(request, client_id: str):
    """Trigger proposal export to exports/ directory."""
    try:
        res = services.compile_and_export_proposal(client_id)
        messages.success(
            request,
            f"Propuesta generada para {client_id}: {res['presentation_filename']} y {res['detail_filename']}."
        )
    except Exception as e:
        messages.error(request, f"Error al compilar propuesta: {e}")
    volver = request.GET.get("volver", "")
    if volver:
        return redirect("sesion", session_id=volver)
    return redirect("panel")


@login_required
@require_POST
def clean_test_data(request):
    """Delete previous test sessions and client blocks from Firestore to start clean."""
    try:
        count = services.clean_all_test_sessions()
        messages.success(request, f"Se eliminaron {count} corridas de prueba anteriores. La base de datos está limpia desde 0.")
    except Exception as e:
        messages.error(request, f"Error al limpiar datos: {e}")
    return redirect("panel")


