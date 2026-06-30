-- ============================================================================
-- 01_maestros.sql
-- Catálogos base: zonas, frutas, monedas, calendario de pagos.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Zonas geográficas. El sistema VBA actual mapea zonas con dos códigos:
--   - codigo_interno: 01, 02, 03, 04, 06 (lo que aparece en la trazabilidad).
--   - codigo_externo: 123, 122, 124, 125, 127 (lo que viene de la maquila).
-- ---------------------------------------------------------------------------
CREATE TABLE zonas (
    codigo_interno  TEXT PRIMARY KEY,
    codigo_externo  INTEGER NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    fruta_dominante TEXT    NOT NULL,            -- 'gulupa' | 'uchuva' | 'mango' | ...
    creado_en       TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Frutas comercializadas. Cada una tiene su código de artículo y bodega en PyA.
-- ---------------------------------------------------------------------------
CREATE TABLE frutas (
    codigo                TEXT PRIMARY KEY,      -- 'GUL', 'UCH', 'MNG', ...
    nombre                TEXT NOT NULL,
    articulo_pya_expo     TEXT NOT NULL,         -- FGU1001, FUC1003, ...
    articulo_pya_nal      TEXT NOT NULL,
    bodega_pya_expo       TEXT NOT NULL,         -- EXGULUPA, EXUC, ...
    bodega_pya_nal        TEXT NOT NULL,         -- NLGU, NLUC, ...
    activo                BOOLEAN DEFAULT TRUE,
    creado_en             TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Monedas (precios estimados/reales en USD/EUR, costos logísticos en COP/USD).
-- ---------------------------------------------------------------------------
CREATE TABLE monedas (
    codigo   TEXT PRIMARY KEY,        -- 'COP', 'USD', 'EUR'
    nombre   TEXT NOT NULL,
    simbolo  TEXT
);

-- ---------------------------------------------------------------------------
-- Calendario de pagos. La macro VBA actual hardcodea que pago = viernes y
-- "recula" desde fecha_proceso + dias_pago hasta encontrar el viernes anterior
-- o posterior. Acá lo modelamos como tabla para que ops pueda editar.
-- ---------------------------------------------------------------------------
CREATE TABLE calendario_pagos (
    fecha         DATE PRIMARY KEY,
    dia_semana    SMALLINT NOT NULL,   -- 1 dom, 2 lun, ... 7 sab (compatible con VBA Weekday)
    es_dia_pago   BOOLEAN NOT NULL DEFAULT FALSE,
    descripcion   TEXT,                -- 'Festivo', 'Pago viernes', ...
    creado_en     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_calendario_pago_si ON calendario_pagos (fecha) WHERE es_dia_pago;

-- ---------------------------------------------------------------------------
-- Tasa representativa del mercado (TRM) — para registrar costos y ventas en USD/EUR.
-- ---------------------------------------------------------------------------
CREATE TABLE trm (
    fecha     DATE PRIMARY KEY,
    valor     NUMERIC(14,4) NOT NULL,
    fuente    TEXT DEFAULT 'datos.gov.co',
    creado_en TIMESTAMPTZ DEFAULT now()
);
