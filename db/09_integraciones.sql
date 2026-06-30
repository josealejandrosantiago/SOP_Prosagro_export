-- ============================================================================
-- 09_integraciones.sql
-- Documentos emitidos a PyA (DR/factura electrónica/factura venta/costos),
-- envíos por Twilio, facturas recibidas (bandeja de correo) y audit log.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Documentos emitidos al ERP PyA. Cada fila es un intento de carga.
-- tipo:
--   'DR_CXC'       — cuenta de cobro al productor (sin fact. electrónica).
--   'FE_COMPRA'    — factura electrónica de compra a productor.
--   'FV'           — factura de venta a cliente del exterior.
--   'COSTO_LOG'    — carga de costo logístico (presupuestado o real).
-- ---------------------------------------------------------------------------
CREATE TABLE pya_documento_emitido (
    id                  BIGSERIAL PRIMARY KEY,
    tipo                TEXT NOT NULL,
    prefijo             TEXT,                     -- 'DSSE', etc.
    consecutivo         INTEGER,
    fecha_emision       DATE NOT NULL,
    fecha_pago          DATE,
    nit_tercero         TEXT,
    fruta_codigo        TEXT REFERENCES frutas(codigo),
    articulo_pya        TEXT,
    bodega_pya          TEXT,
    cantidad            NUMERIC(12,2),
    precio_unitario     NUMERIC(14,4),
    valor_total         NUMERIC(14,2),
    moneda              TEXT REFERENCES monedas(codigo),
    descripcion         TEXT,
    centro_costo        TEXT,                     -- 'P3'
    -- referencias internas:
    trazabilidad_ref    TEXT,
    contenedor_ref      TEXT,
    kg_consolidado_id   BIGINT REFERENCES kg_consolidado(id),
    -- estado del envío:
    payload_json        JSONB,                    -- exacto lo que enviamos
    pya_response        JSONB,                    -- exacto lo que devolvió PyA
    estado              TEXT NOT NULL DEFAULT 'PENDIENTE',  -- PENDIENTE | OK | ERROR | ANULADO
    error_msg           TEXT,
    intentos            INTEGER NOT NULL DEFAULT 0,
    ultimo_intento_en   TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pya_tipo_estado ON pya_documento_emitido (tipo, estado);
CREATE INDEX idx_pya_fecha       ON pya_documento_emitido (fecha_emision);
CREATE INDEX idx_pya_nit         ON pya_documento_emitido (nit_tercero);

-- ---------------------------------------------------------------------------
-- Envíos por Twilio (reportes a productores).
-- Reemplaza el flujo Power Automate actual.
-- ---------------------------------------------------------------------------
CREATE TABLE envio_twilio (
    id                  BIGSERIAL PRIMARY KEY,
    propietario         TEXT NOT NULL,
    telefono            TEXT NOT NULL,
    canal               TEXT NOT NULL DEFAULT 'whatsapp',  -- 'whatsapp' | 'sms'
    tipo_documento      TEXT NOT NULL,                     -- 'LIQUIDACION_SEMANAL' | 'LIQUIDACION_GGN'
    alias_pdf           TEXT NOT NULL,
    url_pdf             TEXT,                              -- SharePoint / blob URL
    mensaje             TEXT,
    payload_json        JSONB,
    twilio_sid          TEXT,
    estado              TEXT NOT NULL DEFAULT 'PENDIENTE', -- PENDIENTE | ENVIADO | ERROR
    error_msg           TEXT,
    intentos            INTEGER NOT NULL DEFAULT 0,
    enviado_en          TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_twilio_estado ON envio_twilio (estado);
CREATE INDEX idx_twilio_tel    ON envio_twilio (telefono);

-- ---------------------------------------------------------------------------
-- Facturas recibidas (bandeja de correo monitoreada).
-- Se cruza con costos_logistico_real o costos de fruta.
-- ---------------------------------------------------------------------------
CREATE TABLE factura_recibida (
    id                  BIGSERIAL PRIMARY KEY,
    correo_origen       TEXT,
    asunto              TEXT,
    fecha_recepcion     TIMESTAMPTZ NOT NULL DEFAULT now(),
    adjunto_nombre      TEXT,
    adjunto_url         TEXT,
    proveedor_id        BIGINT REFERENCES proveedores(id),
    contenedor_ref      TEXT,
    fecha_factura       DATE,
    valor_factura       NUMERIC(14,2),
    moneda              TEXT REFERENCES monedas(codigo),
    estado_cruce        TEXT NOT NULL DEFAULT 'PENDIENTE',
    costo_real_id       BIGINT REFERENCES costo_logistico_real(id),
    pya_doc_id          BIGINT REFERENCES pya_documento_emitido(id),
    payload_xml         TEXT,
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_frec_estado ON factura_recibida (estado_cruce);
CREATE INDEX idx_frec_prov   ON factura_recibida (proveedor_id);
