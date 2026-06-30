-- ============================================================================
-- 08_costos.sql
-- Costos logísticos pronosticados y reales por contenedor.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Concepto de costo (catálogo). En la macro: hoja "Concepto costos".
-- ---------------------------------------------------------------------------
CREATE TABLE concepto_costo (
    id              BIGSERIAL PRIMARY KEY,
    codigo          TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    categoria       TEXT,                     -- 'LOGISTICA', 'CERTIFICACION', 'INSUMO', 'IMPUESTO', ...
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Costos logísticos pronosticados (presupuesto). En la macro: frmCostos.
-- Pueden ser por contenedor o mensuales (en cuyo caso se prorratea).
-- ---------------------------------------------------------------------------
CREATE TABLE costo_logistico_pronosticado (
    id                  BIGSERIAL PRIMARY KEY,
    contenedor_id       BIGINT REFERENCES contenedores(id) ON DELETE CASCADE,
    concepto_id         BIGINT NOT NULL REFERENCES concepto_costo(id),
    proveedor_id        BIGINT REFERENCES proveedores(id),
    naviera             TEXT,
    puerto_origen       TEXT,
    puerto_destino      TEXT,
    icoterm             TEXT,
    moneda              TEXT NOT NULL DEFAULT 'COP' REFERENCES monedas(codigo),
    valor               NUMERIC(14,2) NOT NULL,
    trm_registro        NUMERIC(12,4),
    fecha_registro      DATE NOT NULL,
    es_mensual          BOOLEAN NOT NULL DEFAULT FALSE,
    mes                 SMALLINT,
    anio                SMALLINT,
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clp_contenedor ON costo_logistico_pronosticado (contenedor_id);
CREATE INDEX idx_clp_concepto   ON costo_logistico_pronosticado (concepto_id);

-- ---------------------------------------------------------------------------
-- Costos logísticos reales — cuando llega la factura del proveedor logístico.
-- ---------------------------------------------------------------------------
CREATE TABLE costo_logistico_real (
    id                  BIGSERIAL PRIMARY KEY,
    contenedor_id       BIGINT REFERENCES contenedores(id) ON DELETE CASCADE,
    concepto_id         BIGINT NOT NULL REFERENCES concepto_costo(id),
    proveedor_id        BIGINT REFERENCES proveedores(id),
    factura             TEXT,
    fecha_factura       DATE,
    moneda              TEXT NOT NULL DEFAULT 'COP' REFERENCES monedas(codigo),
    valor               NUMERIC(14,2) NOT NULL,
    trm_pago            NUMERIC(12,4),
    valor_cop           NUMERIC(14,2) GENERATED ALWAYS AS
        (CASE WHEN trm_pago IS NULL THEN valor ELSE valor * trm_pago END) STORED,
    archivo_factura_url TEXT,
    estado_cruce        TEXT NOT NULL DEFAULT 'PENDIENTE',  -- 'PENDIENTE' | 'CRUZADO' | 'ANULADO'
    pronosticado_id     BIGINT REFERENCES costo_logistico_pronosticado(id),
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT now(),
    actualizado_en      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clr_contenedor ON costo_logistico_real (contenedor_id);
CREATE INDEX idx_clr_concepto   ON costo_logistico_real (concepto_id);
CREATE INDEX idx_clr_estado     ON costo_logistico_real (estado_cruce);

-- ---------------------------------------------------------------------------
-- Insumos. Lo dejamos esqueleto — el usuario va a redefinir con su persona.
-- ---------------------------------------------------------------------------
CREATE TABLE insumos (
    id                  BIGSERIAL PRIMARY KEY,
    codigo              TEXT NOT NULL UNIQUE,
    nombre              TEXT NOT NULL,
    unidad_medida       TEXT,
    activo              BOOLEAN DEFAULT TRUE,
    creado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE inventario_insumos (
    id                  BIGSERIAL PRIMARY KEY,
    insumo_id           BIGINT NOT NULL REFERENCES insumos(id),
    fecha               DATE NOT NULL,
    tipo_movimiento     TEXT NOT NULL,            -- 'INGRESO' | 'CONSUMO' | 'AJUSTE'
    cantidad            NUMERIC(12,2) NOT NULL,
    valor_unitario      NUMERIC(12,2),
    contenedor_id       BIGINT REFERENCES contenedores(id),
    observaciones       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_inv_insumo  ON inventario_insumos (insumo_id);
CREATE INDEX idx_inv_fecha   ON inventario_insumos (fecha);
