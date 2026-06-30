-- ============================================================================
-- 06_contenedores.sql
-- Contenedores, pallets, detalle de pallets, distribución a clientes y
-- simulación de viaje.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Contenedor (operación de exportación). Código: 'OP-326' o 'TNLC-313'.
-- ---------------------------------------------------------------------------
CREATE TABLE contenedores (
    id                BIGSERIAL PRIMARY KEY,
    codigo            TEXT NOT NULL UNIQUE,             -- 'OP-326'
    warehouse         TEXT,                             -- 'TNLC'
    fecha_inicio      DATE,
    fecha_cargue      DATE,
    eta               DATE,
    naviera           TEXT,
    puerto_origen     TEXT,
    puerto_destino    TEXT,
    icoterm           TEXT,
    marca             TEXT,
    tracker_codigo    TEXT,
    armado_completo   BOOLEAN NOT NULL DEFAULT FALSE,
    total_pallets     INTEGER NOT NULL DEFAULT 0,
    total_cajas       INTEGER NOT NULL DEFAULT 0,
    observaciones     TEXT,
    creado_en         TIMESTAMPTZ DEFAULT now(),
    actualizado_en    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_contenedores_fecha_cargue ON contenedores (fecha_cargue);

-- ---------------------------------------------------------------------------
-- Pallets que componen un contenedor (lo del RESUMEN CONTENEDOR).
-- ---------------------------------------------------------------------------
CREATE TABLE pallets_contenedor (
    id                    BIGSERIAL PRIMARY KEY,
    contenedor_id         BIGINT NOT NULL REFERENCES contenedores(id) ON DELETE CASCADE,
    no_pallet             INTEGER NOT NULL,
    presentacion          TEXT,                         -- '2KG', '4KG'
    calibre_dominante     TEXT,                         -- '40', 'M', '30/32/M'
    total_cajas           INTEGER NOT NULL DEFAULT 0,
    certificado_grasp     BOOLEAN DEFAULT FALSE,        -- el flag del packing list TNLC
    observaciones         TEXT,
    creado_en             TIMESTAMPTZ DEFAULT now(),
    actualizado_en        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (contenedor_id, no_pallet)
);

-- ---------------------------------------------------------------------------
-- Detalle por pallet (lo del DETALLE POR PALLET del packing list).
-- Cada fila vincula un pallet a un (predio, ICA, GGN, no_cargue, cajas).
-- Cuando hacemos el cruce contra fruta_export, llenamos fruta_export_id.
-- ---------------------------------------------------------------------------
CREATE TABLE pallets_detalle (
    id                BIGSERIAL PRIMARY KEY,
    contenedor_id     BIGINT NOT NULL REFERENCES contenedores(id) ON DELETE CASCADE,
    pallet_id         BIGINT NOT NULL REFERENCES pallets_contenedor(id) ON DELETE CASCADE,
    fruta_export_id   BIGINT REFERENCES fruta_export(id),
    predio            TEXT,
    ica               TEXT,
    ggn               TEXT,
    no_cargue         INTEGER NOT NULL,
    cajas             NUMERIC(10,2) NOT NULL,
    kg                NUMERIC(12,2),
    calibre           TEXT,
    cliente_id        BIGINT REFERENCES clientes(id),    -- packing list nuevo trae CLIENTE
    estado_cruce      TEXT NOT NULL DEFAULT 'PENDIENTE', -- 'PENDIENTE' | 'CRUZADO' | 'ANULADO'
    archivo_origen    TEXT,                              -- nombre del packing list
    creado_en         TIMESTAMPTZ DEFAULT now(),
    actualizado_en    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_palletsdet_contenedor   ON pallets_detalle (contenedor_id);
CREATE INDEX idx_palletsdet_no_cargue    ON pallets_detalle (no_cargue);
CREATE INDEX idx_palletsdet_estado       ON pallets_detalle (estado_cruce);

-- ---------------------------------------------------------------------------
-- Distribución de pallets a clientes. Hoy se hace en frmDistribucionContenedor
-- arrastrando pallets desde "disponibles" a "asignados por cliente".
-- ---------------------------------------------------------------------------
CREATE TABLE distribucion_contenedor (
    id                  BIGSERIAL PRIMARY KEY,
    contenedor_id       BIGINT NOT NULL REFERENCES contenedores(id) ON DELETE CASCADE,
    pallet_id           BIGINT NOT NULL REFERENCES pallets_contenedor(id) ON DELETE CASCADE,
    cliente_id          BIGINT NOT NULL REFERENCES clientes(id),
    tipo_negociacion    TEXT,                            -- 'EN FIRME', 'CONSIGNACION', 'PROGRAMA', ...
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (contenedor_id, pallet_id)
);

-- ---------------------------------------------------------------------------
-- Simulación de viaje. Hoy se carga manual y se completa volumen desde
-- Kg consolidado (CommandButton19 de la macro transportes).
-- ---------------------------------------------------------------------------
CREATE TABLE simulacion_viaje (
    id              BIGSERIAL PRIMARY KEY,
    contenedor_id   BIGINT REFERENCES contenedores(id),
    zona            TEXT NOT NULL,
    lote            TEXT NOT NULL,
    anio            SMALLINT NOT NULL,
    semana          SMALLINT NOT NULL,
    volumen         NUMERIC(12,2) NOT NULL DEFAULT 0,
    ubicacion       TEXT,
    creado_en       TIMESTAMPTZ DEFAULT now(),
    actualizado_en  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sim_zona_lote     ON simulacion_viaje (zona, lote);
CREATE INDEX idx_sim_anio_semana   ON simulacion_viaje (anio, semana);
