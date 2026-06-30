-- ============================================================================
-- 04_fruta.sql
-- Ingreso de fruta de la maquila, segregación en exportación y nacional,
-- consolidado por trazabilidad y proyección de fruta.
--
-- Replica las hojas "ingreso gulupa", "fruta export", "fruta nacional" y
-- "Kg consolidado" del Excel base de datos.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Cada fila es un "cargue" (camionado) que recibe la maquila.
-- La trazabilidad tiene formato: "2026 006 697 02 06"
--   anio | mm | no_cargue | zona | lote
-- ---------------------------------------------------------------------------
CREATE TABLE ingresos (
    id                  BIGSERIAL PRIMARY KEY,
    trazabilidad        TEXT NOT NULL UNIQUE,
    semana              SMALLINT NOT NULL,
    anio                SMALLINT NOT NULL,
    fecha_ingreso       DATE NOT NULL,
    no_cargue           INTEGER NOT NULL,
    zona                TEXT NOT NULL REFERENCES zonas(codigo_interno),
    lote                TEXT NOT NULL,
    consec_int          TEXT NOT NULL,            -- '02 06' p.ej.
    canastillas         INTEGER NOT NULL DEFAULT 0,
    peso_neto           NUMERIC(12,2) NOT NULL,   -- kg total ingresados
    conductor           TEXT,
    placa               TEXT,
    finaliza            TEXT,                     -- 'S' / 'N' — del reporte maquila
    fruta_export_flag   BOOLEAN NOT NULL DEFAULT TRUE,  -- ¡regla clave! No toda fruta es export.
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ingresos_anio_semana   ON ingresos (anio, semana);
CREATE INDEX idx_ingresos_fecha         ON ingresos (fecha_ingreso);
CREATE INDEX idx_ingresos_zona_lote     ON ingresos (zona, lote);

-- ---------------------------------------------------------------------------
-- Fruta de exportación por cargue × calibre. Múltiples filas por cargue.
-- categoria: 'C1' (export normal), 'C2' (export categoría 2, pasa a nacional),
-- 'AJUSTE' (cuando calibre=N/A — ajuste administrativo).
-- ---------------------------------------------------------------------------
CREATE TABLE fruta_export (
    id                       BIGSERIAL PRIMARY KEY,
    ingreso_id               BIGINT NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
    trazabilidad             TEXT NOT NULL,
    semana                   SMALLINT NOT NULL,
    anio                     SMALLINT NOT NULL,
    dia_sem                  TEXT,
    fecha_ingreso            DATE NOT NULL,
    fecha_procesamiento      DATE NOT NULL,
    no_cargue                INTEGER NOT NULL,
    presentacion_caja        TEXT,                            -- 'Cartón Genérica', etc.
    calibre_desc             TEXT,                            -- 'Calibre 30 Europa-EUR30'
    calibre_num              TEXT,                            -- '30', 'M', 'N/A'
    id_calibre               TEXT,                            -- 'EUR30', 'EUR26', ...
    cant_cajas               NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_kg_netos           NUMERIC(12,2) NOT NULL DEFAULT 0,
    productor_nombre         TEXT,                            -- 'PROSAGRO EXPORT SAS'
    producto                 TEXT,                            -- 'Gulupa', 'Uchuva', ...
    ica                      TEXT,
    ggn                      TEXT,
    predio                   TEXT,
    categoria                TEXT NOT NULL DEFAULT 'C1',      -- 'C1' | 'C2' | 'AJUSTE'
    -- cruce con packing list (se llena después):
    contenedor_codigo        TEXT,                            -- 'OP-326'
    pallet_no                INTEGER,
    armado_completo          TEXT,                            -- 'Completo' | 'Incompleto'
    estado_cruce             TEXT NOT NULL DEFAULT 'PENDIENTE',
    finaliza_clasificacion   TEXT,
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_fexport_traza            ON fruta_export (trazabilidad);
CREATE INDEX idx_fexport_no_cargue        ON fruta_export (no_cargue);
CREATE INDEX idx_fexport_calibre_num      ON fruta_export (calibre_num);
CREATE INDEX idx_fexport_contenedor       ON fruta_export (contenedor_codigo);
CREATE INDEX idx_fexport_estado_cruce     ON fruta_export (estado_cruce);
CREATE INDEX idx_fexport_anio_semana      ON fruta_export (anio, semana);

-- ---------------------------------------------------------------------------
-- Fruta nacional (descarte) y simulación. La hoja "Nal" del Excel.
-- simulacion = kg de fruta categoría 26 (EUR26) que se mueven a nacional
-- total_nacional = cant_kilos_descarte + simulacion
-- ---------------------------------------------------------------------------
CREATE TABLE fruta_nacional (
    id                       BIGSERIAL PRIMARY KEY,
    ingreso_id               BIGINT NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
    trazabilidad             TEXT NOT NULL,
    semana                   SMALLINT NOT NULL,
    anio                     SMALLINT NOT NULL,
    dia_sem                  TEXT,
    fecha_ingreso            DATE NOT NULL,
    fecha_procesamiento      DATE NOT NULL,
    no_cargue                INTEGER NOT NULL,
    lote_proceso             TEXT,                            -- 'Lote 6', 'Lote 34', ...
    merma                    NUMERIC(12,2) NOT NULL DEFAULT 0,
    cant_kilos_descarte      NUMERIC(12,2) NOT NULL DEFAULT 0,
    simulacion_kg            NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_nacional           NUMERIC(12,2) GENERATED ALWAYS AS (cant_kilos_descarte + simulacion_kg) STORED,
    finaliza_clasificacion   TEXT,
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_fnal_traza         ON fruta_nacional (trazabilidad);
CREATE INDEX idx_fnal_anio_semana   ON fruta_nacional (anio, semana);

-- ---------------------------------------------------------------------------
-- Consolidado por trazabilidad — replica la hoja "Kg consolidado" con TODA
-- la información financiera y de envíos para una trazabilidad.
--
-- Esta tabla se RECONSTRUYE corriendo el motor SOP (lo que la macro hace al
-- presionar CommandButton1_Click): empareja ingresos + export + nacional +
-- productores + precios + calendario y calcula todo.
--
-- Mantenerla como tabla física (no vista) permite:
--   1) Auditar el snapshot del cálculo en el momento de la liquidación.
--   2) Marcar filas como "ya consecutivada en PyA" (consecutivo_pya).
--   3) Indexar para tableros rápidos.
-- ---------------------------------------------------------------------------
CREATE TABLE kg_consolidado (
    id                       BIGSERIAL PRIMARY KEY,
    trazabilidad             TEXT NOT NULL UNIQUE,
    fecha_ingreso            DATE NOT NULL,
    semana                   SMALLINT NOT NULL,
    anio                     SMALLINT NOT NULL,
    zona                     TEXT NOT NULL,
    lote                     TEXT NOT NULL,
    -- volúmenes:
    kg_total                 NUMERIC(12,2) NOT NULL,
    kg_expo_real             NUMERIC(12,2) NOT NULL DEFAULT 0,
    kg_expo_ajustado         NUMERIC(12,2) NOT NULL DEFAULT 0,    -- los N/A (ajustes administrativos)
    kg_nacional              NUMERIC(12,2) NOT NULL DEFAULT 0,
    kg_categoria_2           NUMERIC(12,2) NOT NULL DEFAULT 0,
    kg_merma                 NUMERIC(12,2) NOT NULL DEFAULT 0,
    canastillas              INTEGER NOT NULL DEFAULT 0,
    -- predio / propietario al momento de procesar:
    nombre_finca             TEXT,
    propietario              TEXT,
    documento                TEXT,
    cantidad_plantas         INTEGER,
    ubicacion                TEXT,
    -- proceso y precios vigentes:
    fecha_procesamiento      DATE,
    precio_expo              NUMERIC(12,2),
    precio_nal               NUMERIC(12,2),
    precio_desh              NUMERIC(12,2),
    -- costos:
    costo_total_expo         NUMERIC(14,2) NOT NULL DEFAULT 0,
    costo_total_nal          NUMERIC(14,2) NOT NULL DEFAULT 0,
    costo_total_desh         NUMERIC(14,2) NOT NULL DEFAULT 0,
    costo_total_ggn          NUMERIC(14,2) NOT NULL DEFAULT 0,
    costo_total_ica          NUMERIC(14,2) NOT NULL DEFAULT 0,    -- ¡SEPARADO! corrige el bug del VBA
    -- certificación referencia:
    ggn                      TEXT,
    ica                      TEXT,
    -- fechas de pago:
    dias_pago                INTEGER,
    fecha_pago               DATE,
    -- contabilidad/operativo:
    fruta_export_flag        BOOLEAN NOT NULL DEFAULT TRUE,
    doc_soporte              TEXT,
    transportadora           TEXT,
    requiere_retencion       TEXT,
    retencion_fuente         NUMERIC(14,2) DEFAULT 0,
    ashofrucol               NUMERIC(14,2) DEFAULT 0,
    facturacion_electronica  TEXT,
    telefono                 TEXT,
    -- consecutivos PyA:
    consecutivo_pya_expo     INTEGER,
    consecutivo_pya_nal      INTEGER,
    procesado_flag           BOOLEAN NOT NULL DEFAULT FALSE,
    observaciones            TEXT,
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_kgc_anio_semana      ON kg_consolidado (anio, semana);
CREATE INDEX idx_kgc_fecha_pago       ON kg_consolidado (fecha_pago);
CREATE INDEX idx_kgc_propietario      ON kg_consolidado (propietario);
CREATE INDEX idx_kgc_documento        ON kg_consolidado (documento);
CREATE INDEX idx_kgc_zona_lote        ON kg_consolidado (zona, lote);
CREATE INDEX idx_kgc_export_flag      ON kg_consolidado (fruta_export_flag);
