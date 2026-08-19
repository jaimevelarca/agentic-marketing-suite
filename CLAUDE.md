# ai-mkt-suite — orientación para Claude / agentes

**Qué es:** la **AI Marketing Suite** de QHHE (QueHueva) — un DAG de **6 capas /
19 agentes** (`suite/orchestration/pipeline.py`) que corre el ciclo de marketing
digital de un cliente (inteligencia → estrategia → planeación → producción →
distribución → analítica). Un cliente se siembra con **un** JSON de onboarding en
`suite/inputs/<client>.json`; la corrida produce ~19 JSON entregables en
`suite/runs/<run>/`. Sobre esas corridas construimos la **propuesta al cliente**.

## Entregables por cliente (dos, de marca adaptada)
- **PITCH:** `qhhe-plan-revision/dist/Plan_<Cliente>_QHHE_<YYYYMMDD>.html` —
  scrollytelling de 9 actos (build.py, un solo archivo, sin conexión).
- **PROPUESTA v0 DETALLADA:** `qhhe-plan-revision/dist/Detalle_<Cliente>_QHHE_<YYYYMMDD>.html`
  (+ `.pdf`) — anexo autocontenido en español (make_detail.py) que embebe los PNG
  renderizados por Nano Banana.

## Proceso repetible → **usa la skill `qhhe-client-proposal`**
1. Brand intake (scrape del sitio → identidad visual + voz). 2. Seed
`suite/inputs/<client>.json`. 3. Corre la suite → JSON en `suite/runs/`. 4. Render
Nano Banana (`render_visuals.py --all` → `dist/renders/`). 5. Autoría del pitch
(skill `qhhe-scrollytelling`) + del detalle (`make_detail.py`). 6. Compuerta humana.
> Hoy `render_visuals.py` y `make_detail.py` están cableados al piloto Alonso (run
> dir, nombre de salida, marca, claves `vis-ayc-*`); parametrízalos por cliente
> antes de reusar. La skill `qhhe-client-proposal` lo detalla.

## Herramientas / rutas clave
- Suite/DAG: `suite/orchestration/pipeline.py`, entrypoint `job_entrypoint.py`.
- Offline: `PYTHONPATH=suite SUITE_LLM_PROVIDER=fixture SUITE_BACKEND=memory python -m orchestration.demo`.
- Validar: `INPUT_FILE=suite/inputs/<client>.json SUITE_LLM_PROVIDER=fixture python suite/scripts/validate_pipeline.py`.
- Live GCP: `AGENT_ID= AUTO_APPROVE=true suite/scripts/run_live.sh`.
- Generadores del cliente (en `qhhe-plan-revision/`): `render_visuals.py` (Nano
  Banana/Vertex), `make_detail.py` (anexo), `build.py`+`presentation.toml`+`theme.toml` (pitch).
- Venv (FUERA del Drive): `$HOME/.venvs/ai-mkt-suite/bin/python` (Python 3.12, uv).

## RESTRICCIONES DURAS
- **Español es-MX profesional, SIN ANGLICISMOS** en todo lo orientado al cliente.
- **Venv fuera del Drive:** solo `$HOME/.venvs/ai-mkt-suite`; nunca `uv venv` en el
  repo; caches fuera del Drive (`PYTHONPYCACHEPREFIX`). Tooling: uv, Python 3.12.
- **Secretos:** local → vault off-Drive `~/.agent_dispatcher/secrets.env`
  (`ANTHROPIC_API_KEY_<CLIENTE>`; Alonso = `ANTHROPIC_API_KEY_AYCIA`); live → GCP
  Secret Manager (secreto `anthropic-api-key`). **NUNCA imprimir la key.**
- **GCP:** renders/despliegue en el project `alonsoycia-489019` (Vertex vía ADC).
- **Nombres:** `<Tipo>_<Cliente>_QHHE_<YYYYMMDD>.{html,pdf}`.
- **Compuerta de revisión:** nada se publica sin aprobación; todo «pendiente de
  revisión»; la máquina nunca se autoaprueba. Verde acento `#1ebe82` reservado a compuertas humanas.
- **Marca provisional** si faltan hex/fuentes/logo: placeholders etiquetados +
  compuerta pidiendo el paquete de marca del cliente.
