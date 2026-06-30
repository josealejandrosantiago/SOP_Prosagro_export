-- ============================================================================
-- 03_vigencias_precios.sql
-- Precios de compra al productor y precios de certificación (GGN/ICA).
-- Ambos se vigencian con fecha_desde/fecha_hasta — al ingresar un cargue se
-- busca el registro vigente para esa fecha.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Precio de fruta por zona + lote + período de vigencia.
-- En la macro: hoja "precio fruta" (Hoja8).
--   col  1 = zona            (codigo_externo en VBA)
--   col  2 = lote
--   col  3 = fecha_desde
--   col  4 = fecha_hasta (vacío = vigente)
--   col  6 = precio_nal
--   col  7 = precio_desh
--   col 10 = precio_expo
--   col 12 = dias_pago
--   col 13 = consolidar_canastillas (Si/No)
--   col 14 = pagar_canastillas (Si/No)
-- ---------------------------------------------------------------------------
CREATE TABLE precio_fruta (
    id                       BIGSERIAL PRIMARY KEY,
    zona                     TEXT NOT NULL REFERENCES zonas(codigo_interno),
    lote                     TEXT NOT NULL,
    fecha_vigencia_desde     DATE NOT NULL,
    fecha_vigencia_hasta     DATE,
    precio_expo              NUMERIC(12,2) NOT NULL,
    precio_nal               NUMERIC(12,2) NOT NULL,
    precio_desh              NUMERIC(12,2) NOT NULL,
    dias_pago                INTEGER NOT NULL,
    consolidar_canastillas   BOOLEAN DEFAULT FALSE,
    pagar_canastillas        BOOLEAN DEFAULT FALSE,
    moneda                   TEXT NOT NULL DEFAULT 'COP' REFERENCES monedas(codigo),
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_precio_fruta_zona_lote ON precio_fruta (zona, lote);
CREATE INDEX idx_precio_fruta_vigencia  ON precio_fruta (fecha_vigencia_desde, fecha_vigencia_hasta);

-- ---------------------------------------------------------------------------
-- Precios de certificación (GGN / ICA). El bug del VBA actual sobre-escribe
-- el costo GGN con el costo ICA: acá los modelamos como dos columnas
-- independientes para poder sumarlos correctamente.
-- ---------------------------------------------------------------------------
CREATE TABLE precio_certificacion (
    id                       BIGSERIAL PRIMARY KEY,
    zona                     TEXT NOT NULL REFERENCES zonas(codigo_interno),
    lote                     TEXT NOT NULL,
    fecha_vigencia_desde     DATE NOT NULL,
    fecha_vigencia_hasta     DATE,
    precio_ggn               NUMERIC(12,2) NOT NULL DEFAULT 0,
    precio_ica               NUMERIC(12,2) NOT NULL DEFAULT 0,
    ica_referencia           TEXT,                                -- ICA del lote / zona
    ggn_referencia           TEXT,                                -- GGN del predio
    moneda                   TEXT NOT NULL DEFAULT 'COP' REFERENCES monedas(codigo),
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pc_zona_lote ON precio_certificacion (zona, lote);
CREATE INDEX idx_pc_vigencia  ON precio_certificacion (fecha_vigencia_desde, fecha_vigencia_hasta);
