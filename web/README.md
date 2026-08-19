# web/ — Consola de revisión (Django)

La superficie humana de la suite: tablero de corridas, revisión de bloques con
**Aprobar / Devolver / Bloquear** (con nota y rastro de auditoría por usuario),
reanudación de corridas en pausa y formulario de nueva corrida. Todo el dato de
dominio vive en Firestore vía `suite/infra` — la base de Django (SQLite local,
`DATABASE_URL` Postgres en producción) solo guarda usuarios y sesiones web.

## Correr en local (contra el Firestore de dev)

```bash
uv sync --extra dev --extra web --extra adk
.venv/bin/python web/manage.py migrate
.venv/bin/python web/manage.py createsuperuser   # una vez

SUITE_LLM_PROVIDER=fixture SUITE_BACKEND=gcp \
GCP_PROJECT_ID=agentic-marketing-suite \
  .venv/bin/python web/manage.py runserver
# → http://127.0.0.1:8000/  (acceso con el usuario creado)
```

Con `SUITE_LLM_PROVIDER=gemini` la corrida usa Gemini en Vertex (≈ USD 0.77 por
corrida completa); con `fixture` es gratuita e inmediata.

## Flujo

1. **Nueva corrida** — identificador del cliente + JSON de incorporación
   (el identificador de la corrida manda; un `client_id` dentro del JSON no lo
   sustituye).
2. La corrida se pausa en cada compuerta humana; el tablero la muestra
   **en pausa** con los bloques pendientes.
3. **Revisar** el bloque → Aprobar (verde reservado a compuertas) / Devolver /
   Bloquear, con nota. La decisión queda en la bitácora de auditoría del bloque
   con tu usuario.
4. **Reanudar corrida** — continúa hasta la siguiente compuerta o el final.

Nota conocida: al reanudar, el estado «en pausa» puede tardar una recarga en
reflejar el bloque pendiente (la pausa y su estado se persisten en dos
escrituras). Recarga la página.

## Producción (fase 6 del plan)

Cloud Run + Cloud SQL (`DATABASE_URL`), `DJANGO_SECRET_KEY` desde Secret
Manager, `DJANGO_DEBUG=0`, IAP al frente. Ver `ROADMAP.md`.
