-- ============================================================================
-- 05_calidad_proyeccion.sql
-- Causales de rechazo (reportes calidad Binlab) y proyección de fruta.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Causales de rechazo. La macro lee xlsx de la maquila (hoja "Evaluación de
-- Calidad"), encuentra la trazabilidad por no_cargue y carga 3 bloques:
-- defectos menores, mayores y críticos.
-- ---------------------------------------------------------------------------
CREATE TABLE causales_rechazo (
    id                BIGSERIAL PRIMARY KEY,
    fecha             DATE NOT NULL,
    trazabilidad      TEXT NOT NULL,
    causal            TEXT NOT NULL,
    porcentaje        NUMERIC(7,4) NOT NULL,            -- % del descarte que esa causal explica
    kg_nacional       NUMERIC(12,2) NOT NULL,           -- cantidad de fruta nacional de esa traza
    kg_con_causal     NUMERIC(12,2) GENERATED ALWAYS AS (porcentaje * kg_nacional) STORED,
    zona              TEXT NOT NULL,
    lote              TEXT NOT NULL,
    severidad         TEXT NOT NULL,                    -- 'MENOR' | 'MAYOR' | 'CRITICO'
    contenedor_codigo TEXT,                             -- si la causal viene de evaluación contenedor
    archivo_origen    TEXT,                             -- nombre del xlsx que la trajo
    creado_en         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_causales_traza      ON causales_rechazo (trazabilidad);
CREATE INDEX idx_causales_severidad  ON causales_rechazo (severidad);
CREATE INDEX idx_causales_zona_lote  ON causales_rechazo (zona, lote);

-- ---------------------------------------------------------------------------
-- Proyección de fruta. La macro CommandButton17 mantiene esta tabla.
-- Para cada (zona, lote, anio, semana) registra:
--   - lo pronosticado (kg total, kg expo, costo, semana_pago estimada)
--   - lo real (cuando la semana se procesa)
-- y permite recalcular la proyección de pagos a futuro.
-- ---------------------------------------------------------------------------
CREATE TABLE proyeccion_fruta (
    id                          BIGSERIAL PRIMARY KEY,
    zona                        TEXT NOT NULL,
    lote                        TEXT NOT NULL,
    anio                        SMALLINT NOT NULL,
    semana                      SMALLINT NOT NULL,
    kg_total_pronosticado       NUMERIC(12,2),
    kg_expo_pronosticado        NUMERIC(12,2),
    costo_pronosticado          NUMERIC(14,2),
    semana_pago_pronosticada    SMALLINT,
    kg_total_real               NUMERIC(12,2),
    kg_expo_real                NUMERIC(12,2),
    costo_real                  NUMERIC(14,2),
    semana_pago_real            SMALLINT,
    productor                   TEXT,
    creado_en                   TIMESTAMPTZ DEFAULT now(),
    actualizado_en              TIMESTAMPTZ DEFAULT now(),
    UNIQUE (zona, lote, anio, semana)
);
