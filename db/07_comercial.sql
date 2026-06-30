-- ============================================================================
-- 07_comercial.sql
-- Precios estimados y reales de venta al cliente, liquidaciones.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Precio estimado de venta — se captura cuando se distribuye el contenedor.
-- ---------------------------------------------------------------------------
CREATE TABLE precio_estimado_venta (
    id                           BIGSERIAL PRIMARY KEY,
    contenedor_id                BIGINT NOT NULL REFERENCES contenedores(id) ON DELETE CASCADE,
    cliente_id                   BIGINT NOT NULL REFERENCES clientes(id),
    pallet_id                    BIGINT REFERENCES pallets_contenedor(id),
    precio_estimado              NUMERIC(12,4) NOT NULL,
    moneda                       TEXT NOT NULL DEFAULT 'USD' REFERENCES monedas(codigo),
    cajas                        NUMERIC(10,2),
    fecha_recogida_estimada      DATE,
    requiere_reclamacion         BOOLEAN DEFAULT FALSE,
    observaciones                TEXT,
    creado_en                    TIMESTAMPTZ DEFAULT now(),
    actualizado_en               TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pev_contenedor ON precio_estimado_venta (contenedor_id);
CREATE INDEX idx_pev_cliente    ON precio_estimado_venta (cliente_id);

-- ---------------------------------------------------------------------------
-- Precio real de venta — cuando llega la liquidación del cliente.
-- Guardamos el PDF de la liquidación para auditoría (y para OCR futuro).
-- ---------------------------------------------------------------------------
CREATE TABLE precio_real_venta (
    id                       BIGSERIAL PRIMARY KEY,
    contenedor_id            BIGINT NOT NULL REFERENCES contenedores(id) ON DELETE CASCADE,
    cliente_id               BIGINT NOT NULL REFERENCES clientes(id),
    pallet_id                BIGINT REFERENCES pallets_contenedor(id),
    tipo_documento           TEXT,                                 -- 'NE', 'CR', 'NC', ...
    consecutivo_ne           TEXT,
    cajas                    NUMERIC(10,2),
    precio_unitario          NUMERIC(12,4) NOT NULL,
    moneda                   TEXT NOT NULL DEFAULT 'USD' REFERENCES monedas(codigo),
    fecha_recogida_real      DATE,
    pdf_liquidacion_url      TEXT,                                 -- ruta Azure Blob / SharePoint
    pdf_liquidacion_local    TEXT,                                 -- ruta local mientras tanto
    observaciones            TEXT,
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_prv_contenedor ON precio_real_venta (contenedor_id);
CREATE INDEX idx_prv_cliente    ON precio_real_venta (cliente_id);
