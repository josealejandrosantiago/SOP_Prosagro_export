-- ============================================================================
-- seed_maestros.sql
-- Datos base de catálogo. Idempotente — usa ON CONFLICT.
-- ============================================================================

SET search_path TO prosagro, public;

-- Zonas — mapeo de codigo_interno (lo que viene en la trazabilidad) a
-- codigo_externo (lo que entrega la maquila). Tomado del módulo Predio.
INSERT INTO zonas (codigo_interno, codigo_externo, nombre, fruta_dominante) VALUES
    ('01', 123, 'Gulupa San José',  'gulupa'),
    ('02', 122, 'Gulupa Urrao',     'gulupa'),
    ('03', 124, 'Gulupa Oriente',   'gulupa'),
    ('04', 125, 'Uchuva',           'uchuva'),
    ('06', 127, 'Sweet Mango',      'mango')
ON CONFLICT (codigo_interno) DO UPDATE
    SET codigo_externo  = EXCLUDED.codigo_externo,
        nombre          = EXCLUDED.nombre,
        fruta_dominante = EXCLUDED.fruta_dominante;

-- Frutas — códigos artículo/bodega PyA tomados de frmCuentasyfacturacion.
INSERT INTO frutas (codigo, nombre, articulo_pya_expo, articulo_pya_nal, bodega_pya_expo, bodega_pya_nal) VALUES
    ('GUL', 'Gulupa', 'FGU1001', 'FGU1001', 'EXGULUPA', 'NLGU'),
    ('UCH', 'Uchuva', 'FUC1003', 'FUC1003', 'EXUC',     'NLUC')
ON CONFLICT (codigo) DO UPDATE
    SET nombre            = EXCLUDED.nombre,
        articulo_pya_expo = EXCLUDED.articulo_pya_expo,
        articulo_pya_nal  = EXCLUDED.articulo_pya_nal,
        bodega_pya_expo   = EXCLUDED.bodega_pya_expo,
        bodega_pya_nal    = EXCLUDED.bodega_pya_nal;

-- Monedas
INSERT INTO monedas (codigo, nombre, simbolo) VALUES
    ('COP', 'Peso colombiano', '$'),
    ('USD', 'Dólar EE. UU.',   'US$'),
    ('EUR', 'Euro',            '€')
ON CONFLICT (codigo) DO UPDATE
    SET nombre  = EXCLUDED.nombre,
        simbolo = EXCLUDED.simbolo;

-- Calendario de pagos del año en curso. Sólo marca los viernes como pago.
-- Los festivos los actualiza ops desde la UI.
DO $$
DECLARE
    d DATE := DATE '2025-01-01';
    fin DATE := DATE '2027-12-31';
BEGIN
    WHILE d <= fin LOOP
        INSERT INTO calendario_pagos (fecha, dia_semana, es_dia_pago, descripcion)
        VALUES (
            d,
            EXTRACT(DOW FROM d)::SMALLINT + 1,   -- DOW: 0 dom .. 6 sab → 1 dom .. 7 sab
            EXTRACT(DOW FROM d) = 5,             -- viernes
            CASE WHEN EXTRACT(DOW FROM d) = 5 THEN 'Pago viernes' ELSE NULL END
        )
        ON CONFLICT (fecha) DO NOTHING;
        d := d + INTERVAL '1 day';
    END LOOP;
END $$;

-- Concepto de costo — base mínima. Ops puede crear más desde la UI.
INSERT INTO concepto_costo (codigo, nombre, categoria) VALUES
    ('FLETE_MAR',       'Flete marítimo',                'LOGISTICA'),
    ('FLETE_TERR',      'Flete terrestre origen',        'LOGISTICA'),
    ('THC_ORIGEN',      'Terminal handling origen',      'LOGISTICA'),
    ('THC_DESTINO',     'Terminal handling destino',     'LOGISTICA'),
    ('SEGURO',          'Seguro de carga',               'LOGISTICA'),
    ('CONTENEDOR',      'Contenedor / pickup',           'LOGISTICA'),
    ('CERT_FITO',       'Certificado fitosanitario',     'CERTIFICACION'),
    ('CERT_ORIGEN',     'Certificado de origen',         'CERTIFICACION'),
    ('GGN_CERT',        'Certificación GLOBALG.A.P.',    'CERTIFICACION'),
    ('ICA_CERT',        'Trámite ICA',                   'CERTIFICACION'),
    ('ASHOFRUCOL',      'Impuesto Asohofrucol',          'IMPUESTO'),
    ('RETEFUENTE',      'Retención en la fuente',        'IMPUESTO')
ON CONFLICT (codigo) DO NOTHING;

-- Usuario placeholder. La app reemplaza '__SET_BY_APP__' por el hash bcrypt
-- de APP_PASSWORD_HASH (variable del .env) en su primer arranque.
INSERT INTO usuarios (email, nombre, password_hash, rol, activo)
VALUES ('analistadedatos@gruposanjose.com.co', 'Jose Alejandro Santiago', '__SET_BY_APP__', 'admin', TRUE)
ON CONFLICT (email) DO NOTHING;
