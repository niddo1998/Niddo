#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Corre las tres capas de pruebas contra el ambiente de pruebas y deja un
# resumen en qa/.salida/resumen.txt.
#
#   bash qa/correr.sh            # levanta el ambiente y corre todo
#   bash qa/correr.sh --sin-levantar
# ══════════════════════════════════════════════════════════════════════════════
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${VENV:-$HOME/.venv-niddo}"
SALIDA="$RAIZ/qa/.salida"
cd "$RAIZ"

[ "${1:-}" = "--sin-levantar" ] || bash qa/levantar.sh || exit 1
rm -rf "$SALIDA/capturas"; mkdir -p "$SALIDA"
PY="$VENV/bin/python"

echo "── 1/3 Tests unitarios (doble de la base)"
$PY -m pytest -q -p no:cacheprovider -p no:playwright tests --junitxml="$SALIDA/unit.xml" 2>&1 | tee "$SALIDA/unit.txt" | tail -3
U=${PIPESTATUS[0]}

echo "── 2/3 Tests contra Postgres real"
NIDDO_TEST_DATABASE_URL="postgresql://niddo@localhost:${PG_PORT:-54329}/niddo_tests" \
  $PY -m pytest -q -p no:cacheprovider -p no:playwright tests/test_db.py --junitxml="$SALIDA/db.xml" 2>&1 | tee "$SALIDA/db.txt" | tail -3
D=${PIPESTATUS[0]}

echo "── 3/3 E2E en navegador"
$PY -m pytest -q -p no:cacheprovider -p no:playwright -c /dev/null --rootdir qa/e2e qa/e2e --junitxml="$SALIDA/e2e.xml" 2>&1 | tee "$SALIDA/e2e.txt" | tail -3
E=${PIPESTATUS[0]}

{
  echo "Corrida: $(date -Iseconds)  commit: $(git rev-parse --short HEAD)"
  echo "unit: $(tail -1 "$SALIDA/unit.txt")"
  echo "db:   $(tail -1 "$SALIDA/db.txt")"
  echo "e2e:  $(tail -1 "$SALIDA/e2e.txt")"
  echo "capturas: $SALIDA/capturas"
} | tee "$SALIDA/resumen.txt"

[ $U -eq 0 ] && [ $D -eq 0 ] && [ $E -eq 0 ]
