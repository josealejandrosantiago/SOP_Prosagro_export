-- ============================================================================
-- 02_terceros.sql
-- Productores (dueños de fincas / lotes), clientes (compradores en el exterior),
-- proveedores (logística, certificaciones, etc.) y usuarios de la app.
-- ============================================================================

SET search_path TO prosagro, public;

-- ---------------------------------------------------------------------------
-- Productores y predios. La macro VBA combina ambos en la hoja "Productores"
-- (zona + lote + fecha de vigencia). Acá los separamos para soportar el caso
-- frecuente de "mismo lote cambia de propietario / certificación".
--
-- Una FINCA (predio) tiene zona + lote físico. Su PROPIETARIO puede cambiar en
-- el tiempo. La macro distingue "nombre_finca" del "dueño_finca" para el caso
-- en que la finca tiene un nombre comercial distinto al del propietario legal.
-- ---------------------------------------------------------------------------
CREATE TABLE productores (
    id                       BIGSERIAL PRIMARY KEY,
    zona                     TEXT NOT NULL REFERENCES zonas(codigo_interno),
    lote                     TEXT NOT NULL,
    fecha_vigencia_desde     DATE NOT NULL,
    fecha_vigencia_hasta     DATE,                 -- NULL = vigente
    nombre_finca             TEXT NOT NULL,        -- usado para los reportes
    propietario              TEXT NOT NULL,        -- a quién se le paga
    documento                TEXT NOT NULL,        -- cédula / NIT
    cantidad_plantas         INTEGER,
    ubicacion                TEXT,                 -- 'Urrao', 'Oriente', ...
    telefono                 TEXT,
    requiere_retencion       TEXT,                 -- 'Si' | 'No'
    facturacion_electronica  TEXT,                 -- 'Si' | 'No'
    ica_propio               TEXT,                 -- registro ICA del productor (si lo tiene)
    ggn_propio               TEXT,                 -- número GLOBALG.A.P. (si lo tiene)
    tiene_grasp              BOOLEAN DEFAULT FALSE,-- nueva regla packing list
    observaciones            TEXT,
    creado_en                TIMESTAMPTZ DEFAULT now(),
    actualizado_en           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_productores_zona_lote        ON productores (zona, lote);
CREATE INDEX idx_productores_vigencia         ON productores (fecha_vigencia_desde, fecha_vigencia_hasta);
CREATE INDEX idx_productores_documento        ON productores (documento);
CREATE INDEX idx_productores_propietario_trgm ON productores USING gin (propietario gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Clientes (compradores en el exterior — AARTSEN, BUD HOLAND, GAIA, etc.).
-- Sale del packing list nuevo (col CLIENTE) y del bloque VAT/CUSTOMER.
-- ---------------------------------------------------------------------------
CREATE TABLE clientes (
    id           BIGSERIAL PRIMARY KEY,
    nombre       TEXT NOT NULL,
    vat          TEXT,                              -- 'NL005470110B01', etc.
    pais         TEXT,
    correo       TEXT,
    activo       BOOLEAN DEFAULT TRUE,
    creado_en    TIMESTAMPTZ DEFAULT now(),
    actualizado_en TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_clientes_nombre_trgm ON clientes USING gin (nombre gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Proveedores (navieras, transportadoras, certificadoras, etc.).
-- ---------------------------------------------------------------------------
CREATE TABLE proveedores (
    id             BIGSERIAL PRIMARY KEY,
    nit            TEXT UNIQUE,
    nombre         TEXT NOT NULL,
    tipo           TEXT,                            -- 'NAVIERA', 'TRANSPORTE', 'CERTIFICADORA', ...
    activo         BOOLEAN DEFAULT TRUE,
    creado_en      TIMESTAMPTZ DEFAULT now(),
    actualizado_en TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Usuarios de la app. Placeholder simple hasta migrar a Azure AD (jue-vie).
-- ---------------------------------------------------------------------------
CREATE TABLE usuarios (
    id             BIGSERIAL PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    nombre         TEXT NOT NULL,
    password_hash  TEXT NOT NULL,                   -- bcrypt
    rol            TEXT NOT NULL DEFAULT 'admin',   -- 'admin', 'ops', 'lectura'
    activo         BOOLEAN DEFAULT TRUE,
    ultimo_login   TIMESTAMPTZ,
    creado_en      TIMESTAMPTZ DEFAULT now(),
    actualizado_en TIMESTAMPTZ DEFAULT now()
);
