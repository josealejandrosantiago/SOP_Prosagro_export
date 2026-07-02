-- ============================================================================
-- 12_usuarios_permisos.sql
-- Control de acceso por usuario (patrón NexFresh).
-- Con el login Entra ID / Easy Auth la app conoce el correo del usuario. No se
-- guardan claves: la validación la hace Microsoft 365 (misma clave corporativa).
--   usuarios_app     — quién puede entrar + si es admin.
--   permisos_usuario — qué secciones del menú ve cada usuario NO admin.
-- ============================================================================

SET search_path TO prosagro, public;

CREATE TABLE IF NOT EXISTS usuarios_app (
    email     TEXT PRIMARY KEY,
    nombre    TEXT,
    es_admin  BOOLEAN NOT NULL DEFAULT FALSE,
    activo    BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS permisos_usuario (
    email   TEXT NOT NULL,
    seccion TEXT NOT NULL,
    PRIMARY KEY (email, seccion)
);

-- Administrador inicial (Jose) — siempre ve todo y administra
INSERT INTO usuarios_app (email, nombre, es_admin)
VALUES ('analistadedatos@gruposanjose.com.co', 'Jose Alejandro Santiago', TRUE)
ON CONFLICT (email) DO UPDATE SET es_admin = TRUE, activo = TRUE;
