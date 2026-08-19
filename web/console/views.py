"""Vistas de la consola de revisión (es-MX; todo requiere sesión iniciada)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
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


@login_required
def run_new(request):
    if request.method == "POST":
        raw = request.POST.get("inputs_json", "").strip()
        try:
            inputs = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            messages.error(request, f"El JSON de entrada no es válido: {e}")
            return render(request, "nueva.html", {"inputs_json": raw,
                                                  "client_id": request.POST.get("client_id", "")})
        client_id = request.POST.get("client_id", "").strip() or inputs.get("client_id")
        if not client_id:
            messages.error(request, "Falta el identificador del cliente.")
            return render(request, "nueva.html", {"inputs_json": raw, "client_id": ""})
        session_id = f"run-{time.strftime('%Y%m%d-%H%M%S')}"
        services.start_run(client_id, inputs,
                           auto_approve=bool(request.POST.get("auto_approve")),
                           session_id=session_id)
        messages.success(request, f"Corrida {session_id} iniciada.")
        return redirect("sesion", session_id=session_id)
    sample = _SAMPLE_INPUT.read_text(encoding="utf-8") if _SAMPLE_INPUT.exists() else "{}"
    return render(request, "nueva.html", {"inputs_json": sample, "client_id": ""})
