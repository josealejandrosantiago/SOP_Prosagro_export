-- ============================================================================
-- 11_simulacion_cronograma.sql
-- (a) Enriquece simulacion_viaje con las columnas de calidad de la hoja
--     'Simulación Viaje' (volumen, evento/incidencia, severidad).
-- (b) Cronograma de operaciones (BL, # contenedor, invoice) para la
--     conciliación de facturación.
-- ============================================================================

SET search_path TO prosagro, public;

-- (a) Muestras de simulación de viaje (calidad de la fruta en frío) ----------
ALTER TABLE simulacion_viaje
    ADD COLUMN IF NOT EXISTS fecha_elaboracion   DATE,
    ADD COLUMN IF NOT EXISTS fecha_inspeccion    DATE,
    ADD COLUMN IF NOT EXISTS tipo_muestra        TEXT,
    ADD COLUMN IF NOT EXISTS cantidad_muestra    NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS evento              TEXT,
    ADD COLUMN IF NOT EXISTS cantidad_evento     NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS porcentaje          NUMERIC(9,4),
    ADD COLUMN IF NOT EXISTS severidad_promedio  NUMERIC(9,4);

CREATE INDEX IF NOT EXISTS idx_sim_evento    ON simulacion_viaje (evento);
CREATE INDEX IF NOT EXISTS idx_sim_anio_sem2 ON simulacion_viaje (anio, semana);

-- (b) Cronograma de operaciones (para conciliación de facturas) --------------
CREATE TABLE IF NOT EXISTS cronograma_operaciones (
    id                    BIGSERIAL PRIMARY KEY,
    contenedor_codigo     TEXT NOT NULL,          -- 'OP-219' (Nro contenedor planta)
    importador            TEXT,
    invoice               TEXT,                    -- consecutivo INVOICE (= OP sin prefijo)
    puerto_origen         TEXT,
    fecha_salida_planta   DATE,
    fecha_embarque        DATE,
    fecha_llegada         DATE,
    fecha_buen_arribo     DATE,
    puerto_destino        TEXT,
    semana_llegada        SMALLINT,
    contenedor_fisico     TEXT,                    -- 'HLXU 8781792' (N° CONTENEDOR real)
    empresa_transporte    TEXT,
    vehiculo              TEXT,
    tarifa_flete_terrestre NUMERIC(14,2),
    icoterms_real         TEXT,
    observaciones         TEXT,
    booking               TEXT,
    naviera               TEXT,
    motonave              TEXT,
    bl                    TEXT,                    -- SWB / BL
    maquila               TEXT,
    dias_transito         NUMERIC(6,1),
    semana_salida         SMALLINT,
    icoterm_facturacion   TEXT,
    creado_en             TIMESTAMPTZ DEFAULT now(),
    actualizado_en        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (contenedor_codigo)
);

CREATE INDEX IF NOT EXISTS idx_crono_invoice     ON cronograma_operaciones (invoice);
CREATE INDEX IF NOT EXISTS idx_crono_contfisico  ON cronograma_operaciones (contenedor_fisico);
CREATE INDEX IF NOT EXISTS idx_crono_bl          ON cronograma_operaciones (bl);
