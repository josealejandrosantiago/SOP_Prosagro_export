-- ============================================================================
-- 00_extensiones.sql
-- Extensiones de PostgreSQL y configuración base.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;       -- gen_random_uuid(), crypt() para hash de claves
CREATE EXTENSION IF NOT EXISTS unaccent;       -- normalización de nombres de productores
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- búsqueda parcial en nombres / fincas

-- Schema único por ahora. Si en algún momento separamos GUI/comercial/contable
-- podemos mover tablas a otros schemas.
CREATE SCHEMA IF NOT EXISTS prosagro;
SET search_path TO prosagro, public;
