#!/usr/bin/env bash
# Aplica todas las migraciones SQL del directorio db/ en orden alfabético.
# Lee la conexión de DATABASE_URL (ya sea desde .env o ya exportada en el shell).

set -euo pipefail
cd "$(dirname "$0")/.."

# Cargar .env si existe
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . .env
    set +a
fi

: "${DATABASE_URL:?DATABASE_URL no está definido — revisa .env}"

PSQL="${PSQL:-psql}"
# Si psql no está en PATH, intentar el de PostgreSQL 17
if ! command -v "$PSQL" >/dev/null 2>&1; then
    PSQL="/c/Program Files/PostgreSQL/17/bin/psql.exe"
fi

echo "Aplicando migraciones a $PGDATABASE@$PGHOST..."
for f in db/*.sql; do
    echo "  → $f"
    "$PSQL" "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done
echo "OK"
