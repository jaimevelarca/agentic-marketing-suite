# Sesión 2026-08-19 (2ª del día) — Fase 6b: diseño, sin código

**Objetivo:** arrancar la Fase 6b (GitHub Actions con WIF, IAP frente a la
consola, stack `prod` con compuerta de corrida de humo) planeándola primero.

**Resultado: sesión de diseño. El árbol de trabajo quedó limpio — no se tocó
código ni infra.** Lo que sí quedó cerrado son tres decisiones de arquitectura y
una propuesta de diseño completa, pendiente de la aprobación de Jaime.

## Verificaciones técnicas (contra docs y contra el venv, no de memoria)

- **IAP directo sobre Cloud Run es GA desde marzo 2026**: sin balanceador, sin
  dominio, sin certificado y sin costo adicional
  ([docs](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)).
  Se habilita con `--iap` + `run.invoker` al agente de servicio de IAP.
- El `pulumi-gcp` **9.34.1** que ya está fijado en `infra/` expone
  `cloudrunv2.Service(iap_enabled=...)` y `iap.WebCloudRunServiceIamMember`.
  No hace falta subir versión ni salirse de Pulumi.
- `js@qhhe.net` tiene `roles/resourcemanager.folderAdmin` sobre el folder QHHE
  (274831265727) ⇒ puede crear el project de producción sin pedir nada a nadie.

## Decisiones tomadas por Jaime

1. **Aislamiento de `prod`: project GCP aparte** —
   `agentic-marketing-suite-prod` en el folder QHHE, mismo billing. El programa
   Pulumi no cambia de forma; el stack `prod` solo apunta `gcp:project` a otro
   lado, conserva Firestore `(default)` y los nombres sin prefijo. **Cero cambios
   en `suite/`.** Costo fijo extra ≈ USD 9–12/mes (segundo Cloud SQL micro).
   *Descartado:* un solo project con nombres prefijados + base Firestore nombrada
   (obligaba a hilar un id de base por `suite/infra/clients.py`, config y tests,
   y compartía radio de impacto).
2. **Promoción a `prod`: etiqueta git `v*`** — el merge a `main` despliega `dev`
   solo; un tag `v1.2.3` promueve **el mismo digest ya probado en `dev`**, nunca
   una reconstrucción.
3. **IAP en ambos stacks, conservando el login de Django** — IAP con acceso para
   `js@qhhe.net`, se retira el invoker `allUsers`, y el login de Django queda
   como segundo factor (además `django.contrib.auth` necesita usuario para admin
   y auditoría). *Descartado:* confiar en el encabezado
   `X-Goog-Authenticated-User-Email` — más código y un bug de confianza en el
   encabezado se vuelve elusión de autenticación si algún día se quita IAP.

## Diseño propuesto (PENDIENTE DE APROBACIÓN — no se escribió spec)

1. **Identidad.** Cada stack crea su propio Workload Identity Pool + proveedor
   OIDC y una SA `pulumi-deployer`. La condición de atributo del proveedor fija
   `assertion.repository == 'jaimevelarca/agentic-marketing-suite'`; en `prod`
   además `assertion.ref.startsWith('refs/tags/v')`, de modo que el project de
   producción no se puede desplegar desde una rama. GitHub no guarda **ningún**
   secreto: `PULUMI_CONFIG_PASSPHRASE` pasa a Secret Manager (`pulumi-passphrase`)
   y el workflow lo lee ya autenticado. Pulumi administra el contenedor del
   secreto y su IAM, no el valor — la versión se siembra a mano desde el vault
   para que la frase nunca entre al estado de Pulumi. Ambos stacks siguen
   compartiendo `gs://agentic-marketing-suite-pulumi-state`.
2. **Imágenes.** `deploy/cloudbuild.yaml` y `web/cloudbuild.yaml` dejan de
   publicar `:latest` (solo SHA). `infra/__main__.py` deja de fijar la cadena de
   imagen y lee dos configs de stack (`consoleImage`, `orchestratorImage`) que CI
   pone al **digest** resuelto — esto elimina el "rodar el servicio a mano" que
   documenta `infra/README.md`. Artifact Registry sigue siendo **un solo repo** en
   el project de `dev` (almacén compartido de artefactos); las SAs de `prod` y su
   agente de servicio de Cloud Run reciben `artifactregistry.reader`. El programa
   crea el repo solo en el project dueño.
3. **Compuerta de humo** (`scripts/smoke_check.py`, Python y no bash, para que su
   lógica se pruebe fuera de línea), tras cada `pulumi up`:
   (a) el Job `suite-orchestrator` corre con override `SUITE_LLM_PROVIDER=fixture`
   y client id `smoke-<sha>` → exit 0, sin gasto de Gemini;
   (b) la URL de la consola responde **302 a `accounts.google.com`** — una sola
   prueba que demuestra a la vez que el servicio vive y que IAP está aplicando;
   (c) el digest de la revisión viva es el que acabamos de desplegar.
   Un fallo en `prod` revierte re-corriendo `pulumi up` con el digest anterior
   (leído de una salida de stack `deployed_*_image` nueva) — sin repartir tráfico
   a mano, así Pulumi nunca queda a la deriva.
4. **Pruebas nuevas** (fuera de línea, sobre las 234 en verde): que ningún
   workflow use llave de larga vida, que exista `id-token: write`, que el
   workflow de `prod` dispare solo con tags, que `:latest` ya no aparezca en
   `infra/`, y la lógica de `smoke_check.py`.

## Riesgos anotados para la ejecución

- El primer `pulumi up prod` probablemente necesite ADC de `js@qhhe.net`
  (`gcloud auth application-default login`) — paso interactivo de Jaime. El stack
  `dev` sigue con ADC de `jaimevelarca@gmail.com`.
- La SA `pulumi-deployer` de `prod` necesita un rol sobre la **cuenta de billing**
  para el recurso de presupuesto. Si ese permiso se bloquea, el presupuesto pasa a
  ser opcional por stack en vez de dejar a CI fallando por deriva.
- Presupuesto propuesto: MXN 2,000 en `dev`, MXN 4,000 en `prod` (monto como
  config de stack).

## Corrección al ROADMAP

La tabla de decisiones y la Fase 6 decían *"stacks `dev`/`prod` in the one
project"*. Con la decisión 1 eso quedó **falso** y habría desorientado a la
siguiente sesión, así que se corrigió en `ROADMAP.md`.

## Punto de entrada de la siguiente sesión

Retomar en la **compuerta de aprobación**: presentarle a Jaime el diseño de
arriba; con su visto bueno, escribir el spec en `docs/superpowers/specs/` y de ahí
el plan en `docs/superpowers/plans/` (skill `superpowers:writing-plans`) antes de
tocar código. Nada de 6b está implementado todavía.
