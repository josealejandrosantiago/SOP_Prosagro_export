#!/usr/bin/env bash
# Crea el usuario y base de datos en Postgres local (corre una sola vez).
# Pide la clave de 'postgres' una vez.
set -euo pipefail

PSQL="${PSQL:-/c/Program Files/PostgreSQL/17/bin/psql.exe}"

read -r -p "Clave del usuario 'postgres' (admin de Postgres): " -s PG_ADMIN_PWD
echo

PGPASSWORD="$PG_ADMIN_PWD" "$PSQL" -U postgres -h localhost -p 5432 <<'SQL'
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prosagro') THEN
        CREATE ROLE prosagro WITH LOGIN PASSWORD 'prosagro';
    END IF;
END $$;

SELECT 'CREATE DATABASE prosagro OWNER prosagro'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'prosagro') \gexec
SQL

echo "Base 'prosagro' lista. Ahora corre: bash scripts/aplicar_migraciones.sh"
