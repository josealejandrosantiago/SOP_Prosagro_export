-- ============================================================================
-- 10_audit.sql
-- Tabla de auditoría — quién/cuándo/qué cambió.
-- Aplica al menos a kg_consolidado, productores, precio_fruta y
-- pya_documento_emitido (las que más impactan la liquidación).
-- ============================================================================

SET search_path TO prosagro, public;

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tabla           TEXT NOT NULL,
    registro_id     BIGINT NOT NULL,
    accion          TEXT NOT NULL,           -- 'INSERT' | 'UPDATE' | 'DELETE'
    usuario_id      BIGINT REFERENCES usuarios(id),
    usuario_email   TEXT,                    -- snapshot por si el usuario se borra después
    valores_antes   JSONB,
    valores_despues JSONB,
    cambios         JSONB,                   -- diff
    ip              TEXT,
    creado_en       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_tabla_registro ON audit_log (tabla, registro_id);
CREATE INDEX idx_audit_usuario        ON audit_log (usuario_id);
CREATE INDEX idx_audit_fecha          ON audit_log (creado_en);
