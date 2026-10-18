#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Levanta el ambiente de pruebas de Niddo: Postgres local + schema + datos
# ficticios + la app en http://localhost:5055 con el login de QA habilitado.
#
#   bash qa/levantar.sh          # levanta todo (resetea la base cada vez)
#   bash qa/levantar.sh --parar  # baja la app y Postgres
#
# No toca nada externo: sin RESEND/GROQ/VAPID/Mercado Pago configurados, esas
# integraciones quedan apagadas y la app solo lo registra en el log.
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PG_BIN="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)}"
PG_DATA="${PG_DATA:-/var/lib/niddo-qa-pg}"
PG_PORT="${PG_PORT:-54329}"
APP_PORT="${APP_PORT:-5055}"
VENV="${VENV:-$HOME/.venv-niddo}"
LOG_DIR="${LOG_DIR:-$RAIZ/qa/.salida}"
DB_URL="postgresql://niddo@localhost:$PG_PORT/niddo_qa"

como_pg() {  # initdb/pg_ctl no corren como root
  if [ "$(id -u)" = 0 ]; then su postgres -c "$*"; else bash -c "$*"; fi
}

if [ "${1:-}" = "--parar" ]; then
  pkill -f "flask --app app run --port $APP_PORT" 2>/dev/null || true
  como_pg "$PG_BIN/pg_ctl -D $PG_DATA stop -m fast" 2>/dev/null || true
  echo "Ambiente de pruebas detenido."; exit 0
fi

mkdir -p "$LOG_DIR"

# ── Postgres ──────────────────────────────────────────────────────────────────
if [ ! -f "$PG_DATA/PG_VERSION" ]; then
  [ "$(id -u)" = 0 ] && { id postgres >/dev/null 2>&1 || useradd -m postgres; }
  mkdir -p "$PG_DATA"; [ "$(id -u)" = 0 ] && chown postgres "$PG_DATA"
  como_pg "$PG_BIN/initdb -D $PG_DATA -U niddo --auth=trust -E UTF8 >/dev/null"
fi
if ! pg_isready -h /tmp -p "$PG_PORT" >/dev/null 2>&1; then
  como_pg "$PG_BIN/pg_ctl -D $PG_DATA -o '-p $PG_PORT -k /tmp' -l $PG_DATA/log start >/dev/null"
  for _ in $(seq 20); do pg_isready -h /tmp -p "$PG_PORT" >/dev/null 2>&1 && break; sleep 0.5; done
fi

PSQL="psql -h /tmp -p $PG_PORT -U niddo -q -v ON_ERROR_STOP=1"
pkill -f "flask --app app run --port $APP_PORT" 2>/dev/null || true  # suelta las conexiones
for base in niddo_qa niddo_tests; do
  $PSQL -d postgres -c "DROP DATABASE IF EXISTS $base WITH (FORCE)" >/dev/null
  $PSQL -d postgres -c "CREATE DATABASE $base" >/dev/null
  $PSQL -d "$base" -f "$RAIZ/schema.sql" >/dev/null
  for m in "$RAIZ"/migraciones/*.sql; do [ -f "$m" ] && $PSQL -d "$base" -f "$m" >/dev/null; done
done
$PSQL -d niddo_qa -f "$RAIZ/qa/seed.sql" >/dev/null
echo "Base niddo_qa lista (schema + migraciones + seed). Base niddo_tests vacía para tests/test_db.py."

# ── Python ────────────────────────────────────────────────────────────────────
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -U pip setuptools wheel
fi
"$VENV/bin/pip" install -q -r "$RAIZ/requirements-dev.txt"

# ── Chromium para los E2E ─────────────────────────────────────────────────────
# Primero el oficial de Playwright; si la red no deja bajarlo (el workspace de
# Claude bloquea su CDN), uno empaquetado en npm, que sí está permitido.
QA_CHROMIUM="${QA_CHROMIUM:-$HOME/.qa-chromium/chromium}"
if [ ! -x "$QA_CHROMIUM" ] && ! "$VENV/bin/python" -m playwright install chromium >/dev/null 2>&1; then
  mkdir -p "$HOME/.qa-chromium"
  ( cd "$HOME/.qa-chromium"
    [ -f package.json ] || echo '{"name":"qa-chromium","version":"1.0.0","private":true}' > package.json
    npm install --silent @sparticuz/chromium >/dev/null
    p=$(node -e "const c=require('@sparticuz/chromium');(c.default||c).executablePath().then(console.log)")
    cp "$p" "$QA_CHROMIUM" )
fi

# ── App ───────────────────────────────────────────────────────────────────────
pkill -f "flask --app app run --port $APP_PORT" 2>/dev/null || true
cd "$RAIZ"
env -i PATH="$VENV/bin:$PATH" HOME="$HOME" \
  NIDDO_LOCAL=1 NIDDO_QA_LOGIN=1 \
  DATABASE_URL="$DB_URL" \
  SECRET_KEY=qa-local-no-secreto \
  AUTH0_DOMAIN=qa.invalid AUTH0_CLIENT_ID=qa AUTH0_CLIENT_SECRET=qa \
  NIDDO_URL="http://localhost:$APP_PORT" \
  NIDDO_CIFRADO_KEY="$("$VENV/bin/python" -c 'import base64;print(base64.urlsafe_b64encode(b"q"*32).decode())')" \
  nohup "$VENV/bin/flask" --app app run --port "$APP_PORT" > "$LOG_DIR/app.log" 2>&1 &

for _ in $(seq 40); do
  curl -sf -o /dev/null "http://localhost:$APP_PORT/" && break; sleep 0.5
done
curl -sf -o /dev/null "http://localhost:$APP_PORT/" || { echo "La app no levantó; ver $LOG_DIR/app.log"; tail -20 "$LOG_DIR/app.log"; exit 1; }

cat <<EOF
App de pruebas en http://localhost:$APP_PORT
Entrar como:  /qa/login/admin · /qa/login/superadmin · /qa/login/pendiente · /qa/login/vecino · /qa/login/vecino2
Log de la app: $LOG_DIR/app.log
EOF
