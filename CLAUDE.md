# CLAUDE.md

Guía para trabajar en Niddo con Claude Code. Niddo es una plataforma web para
administrar consorcios (edificios en propiedad horizontal) en Argentina: el
administrador carga gastos, genera la liquidación de expensas y registra
cobros; el vecino ve lo que debe, paga, reclama y reserva amenities.

Todo lo que se escriba en este repo (código, comentarios, commits, PRs, issues)
va en **español rioplatense**, como el resto del proyecto.

## Reglas de trabajo (obligatorias)

1. **Nunca mergear a `main` sin el OK explícito de Santiago o de su socio**
   para ese PR. Mergear a `main` es deployar a producción (Vercel publica cada
   push a `main`). El OK vale si llega por el chat con Claude o como
   comentario/aprobación en el PR desde una cuenta de founder (`niddo1998` o
   `novick43-stack`). Detalle completo en `docs/qa/RUNBOOK.md` §6.1 y §6.2.
2. **Trabajar siempre en una rama y entrar por PR.** Nunca pushear directo a
   `main`. Ramas `fix/<n>-<slug>` para bugs y `feat/<n>-<slug>` para backlog
   (o la rama que indique la sesión). Un PR por issue, usando el template de
   `.github/pull_request_template.md`.
3. **Correr los tests antes de cada push.** Como mínimo los unitarios; si el
   cambio toca base, rutas o pantallas, la suite completa (`bash qa/correr.sh`).
   No pushear en rojo.

Además, del runbook de QA: no tocar la base de producción ni la de Neon
principal, no crear/editar/borrar datos reales, no configurar secretos, nada
de pagos reales ni mails a direcciones reales. Ante reglas de negocio
ambiguas, migraciones, auth/permisos, pagos o mails: preguntar primero.

## Stack

- **Backend:** Python 3.12 (CI) + Flask 2.3, todo en un monolito `app.py`
  (~8.000 líneas, ~160 rutas).
- **Base:** Postgres en **Neon** (proyecto Niddo-SP, São Paulo) vía `psycopg` 3.
  `db.py` imita la API de supabase-py (`supabase.table(...).select(...).eq(...).execute()`)
  y la traduce a SQL: la app nació sobre Supabase y las consultas se mantienen
  en ese idioma.
- **Auth:** Auth0 (Authlib, OIDC). Roles en sesión: `admin` y `vecino`;
  superadmin es un admin con `es_superadmin` en la base.
- **Frontend:** templates Jinja (`templates/`) + JS y CSS sin framework ni build
  (`static/`). PWA con service worker y Web Push (`pywebpush`, claves VAPID).
- **Integraciones:** Resend (mails), Groq Vision (lectura de comprobantes),
  Mercado Pago Checkout Pro (apagado por ahora), ReportLab/PyMuPDF (PDF),
  openpyxl (Excel).
- **Deploy:** Vercel (`vercel.json`, entrada `api/index.py`, región `gru1`).
  Los avisos programados los dispara GitHub Actions (`.github/workflows/avisos.yml`)
  contra `/api/cron/diario` y `/api/cron/cada-hora`.

## Estructura

```
app.py                  La app Flask: config, auth, pertenencia de datos y todas las rutas/API
db.py                   Capa de acceso a Postgres con interfaz tipo supabase-py
recurrentes.py          Cálculo de períodos de gastos recurrentes (puro, testeable)
liquidacion_pdf.py      PDF de la liquidación (recibe dicts, devuelve bytes)
excel_niddo.py          Formato de todos los .xlsx (exportes y plantillas de carga masiva)
mercadopago_niddo.py    Cliente de Mercado Pago (no conoce la base)
cifrado.py              Fernet para secretos guardados (token de Mercado Pago)
api/index.py            Entry point de Vercel (importa `app`)
templates/              Jinja: landing, login, dashboards admin/vecino, superadmin, legales
static/                 JS, CSS, íconos, manifest y service worker
schema.sql              Esquema completo de la base (con esto se levanta una base nueva)
supabase_schema_vN.sql  Historia de migraciones de la época de Supabase (v2 → v24)
tests/                  Tests unitarios con un doble de la base (conftest.py) + test_db.py contra Postgres real
qa/                     Ambiente de pruebas: levantar.sh, correr.sh, seed.sql y E2E con Playwright (qa/e2e/)
docs/qa/                RUNBOOK.md (cómo trabaja Claude) y MATRIZ.md (flujos a recorrer)
docs/superpowers/       Specs y planes de features
.github/                Template de PR, templates de issues, workflows de QA y avisos
```

Los módulos chicos viven fuera de `app.py` a propósito: son la lógica
determinística que se prueba sin base. Seguir ese criterio para lógica nueva
con riesgo.

## Comandos

Instalar dependencias (en un venv; `qa/` usa `~/.venv-niddo` por defecto):

```bash
python3 -m venv ~/.venv-niddo
~/.venv-niddo/bin/pip install -U pip setuptools wheel
~/.venv-niddo/bin/pip install -r requirements-dev.txt
```

Correr la app en local (necesita un `.env` armado desde `.env.example`):

```bash
python app.py                 # http://localhost:3500, modo debug
```

Ambiente de pruebas completo (Postgres local + schema + seed + app en
`http://localhost:5055` con login de QA, sin Auth0 ni integraciones externas):

```bash
bash qa/levantar.sh           # levanta (resetea la base cada vez)
bash qa/levantar.sh --parar   # baja todo
```

Entrar sin Auth0: `/qa/login/admin`, `/qa/login/superadmin`,
`/qa/login/pendiente`, `/qa/login/vecino`, `/qa/login/vecino2`.

Tests:

```bash
# Unitarios (rápidos, sin base real) — mínimo antes de cada push
~/.venv-niddo/bin/python -m pytest -q -p no:cacheprovider -p no:playwright tests

# Un archivo o un test puntual
~/.venv-niddo/bin/python -m pytest -q -p no:playwright tests/test_prorrateo.py -k nombre

# Las tres capas (unitarios + Postgres real + E2E en navegador), igual que CI
bash qa/correr.sh             # deja el resumen en qa/.salida/resumen.txt
```

El workflow `QA` (`.github/workflows/qa.yml`) corre `bash qa/correr.sh` en cada
PR y en cada push a `main`; tiene que estar verde para mergear.

## Entidades del dominio

Tablas principales (ver `schema.sql`):

- **administradores**: cuentas de administración. Pasan por solicitud y
  aprobación (`estado`); `es_superadmin` marca a los dueños del sitio.
- **consorcios**: el edificio. Pertenece a un administrador; guarda datos
  bancarios, configuración de liquidación y vencimientos.
- **unidades_funcionales** (UF): departamentos/cocheras del consorcio, con
  coeficientes de prorrateo (m², ambientes, %, partes iguales) y saldo inicial.
- **vecinos** y **vecinos_unidades**: propietarios/inquilinos y su relación con
  las UF. **solicitudes_vinculacion**: pedidos de un vecino para asociarse a una UF.
- **proveedores** y **gastos**: lo que se paga en el consorcio (con rubro,
  comprobante y gastos recurrentes/extraordinarios). **comprobantes_gastos**:
  adjuntos.
- **liquidaciones**, **liquidacion_rubros**, **liquidacion_items**,
  **liquidacion_prorrateo**: la liquidación mensual de expensas y cuánto le toca
  a cada UF. Tiene página pública por `token_publico` (QR del PDF).
- **cobros**: lo que debe y paga cada UF por período (mora, segundo
  vencimiento). **avisos_pago**: el vecino informa que pagó. **medios_pago**:
  cómo pagar en cada consorcio.
- **amenities** y **reservas_amenities**: espacios comunes y sus reservas.
- **reclamos** y **reclamo_mensajes**: reclamos del vecino y su conversación.
- **mensajes**: chat 1 a 1 administrador ↔ vecino.
- **comunicados** y **comunicados_leidos**; **votaciones** y **votos**;
  **archivos_consorcio**.
- **push_suscripciones**, **envio_programado**, **resumen_envios**: avisos push
  y mails programados.
- **superadmin_auditoria**, **roadmap_estado**, **secciones_vistas**: soporte
  del panel de superadmin y del onboarding.

## Convenciones y cosas a cuidar

- **Pertenencia de los datos:** `require_auth` solo dice quién sos. Que el
  consorcio, la liquidación o el cobro sean tuyos lo chequean los helpers de la
  sección «Pertenencia de los datos» de `app.py`. Toda ruta nueva que reciba un
  id tiene que pasar por ahí (lo cubren `tests/test_pertenencia*.py`).
- `require_superadmin` responde 404 (no 403) a quien no tiene permiso.
- Las consultas usan el idioma de `db.py`; no escribir SQL suelto en `app.py`.
- **Cambios de esquema:** van en archivos nuevos `migraciones/NNN_nombre.sql`
  (lo dice `schema.sql` y `qa/levantar.sh` ya los aplica). Son de la lista de
  «preguntar primero» y se aplican en producción solo con instrucción aparte.
  Ojo: `schema.sql` refleja el estado hasta v23; lo de `supabase_schema_v24.sql`
  (p. ej. `liquidaciones.token_publico`) todavía no está incorporado.
- Los tests de regresión van primero: el test tiene que fallar antes del fix.
- Comentarios y docstrings explican el *porqué*, en español, con el tono del
  código existente.
