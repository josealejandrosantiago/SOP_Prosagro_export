"""SOP — costeo y rentabilidad por contenedor.

Replica el corazón de la Macro 2 (frmInicio.CommandButton2): para cada
contenedor (operación OP-xxx) arma el costo total desglosado y lo enfrenta al
ingreso de venta para sacar la rentabilidad.

Componentes del costo por contenedor:
  1. Costo de fruta       = Σ (kg_export × precio_expo de la traza)   [C1]
  2. Costo certificación  = Σ (parte proporcional del costo GGN/ICA de la traza)
  3. Costos logísticos    = Σ costo_logistico_pronosticado/real del contenedor
  4. Insumos              = Σ inventario_insumos (consumo) del contenedor
Ingreso de venta:
  - Estimado = Σ precio_estimado_venta (× cajas/kg según moneda)
  - Real     = Σ precio_real_venta

Nota: costo de fruta y certificación ya se pueden calcular (hay datos). Los
costos logísticos, insumos y precios de venta salen en 0 hasta que se carguen
esos módulos — el SOP se completa solo conforme entra la información.
"""
from __future__ import annotations

from conexion import get_conn


def contenedores_sop() -> list[dict]:
    """Resumen SOP de todos los contenedores reales (OP/LOC/TNLC/EXP)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            WITH fruta AS (
                SELECT
                    e.contenedor_codigo AS codigo,
                    SUM(e.total_kg_netos)                                  AS kg_export,
                    SUM(e.cant_cajas)                                      AS cajas,
                    COUNT(DISTINCT e.pallet_no) FILTER (WHERE e.pallet_no IS NOT NULL) AS pallets,
                    SUM(e.total_kg_netos * COALESCE(k.precio_expo, 0))     AS costo_fruta,
                    SUM(e.total_kg_netos
                        * CASE WHEN k.kg_expo_real > 0
                               THEN (k.costo_total_ggn + k.costo_total_ica) / k.kg_expo_real
                               ELSE 0 END)                                 AS costo_certif
                FROM prosagro.fruta_export e
                LEFT JOIN prosagro.kg_consolidado k ON k.trazabilidad = e.trazabilidad
                WHERE e.contenedor_codigo ~ '^(OP|LOC|TNLC|EXP)-?[0-9]'
                  AND e.categoria = 'C1'
                GROUP BY e.contenedor_codigo
            ),
            logistica AS (
                SELECT contenedor_id, SUM(valor) AS costo_log
                FROM prosagro.costo_logistico_pronosticado GROUP BY contenedor_id
            ),
            logistica_real AS (
                SELECT contenedor_id, SUM(valor_cop) AS costo_log_real
                FROM prosagro.costo_logistico_real GROUP BY contenedor_id
            ),
            venta_est AS (
                SELECT contenedor_id, SUM(precio_estimado * COALESCE(cajas,0)) AS ingreso_est
                FROM prosagro.precio_estimado_venta GROUP BY contenedor_id
            ),
            venta_real AS (
                SELECT contenedor_id, SUM(precio_unitario * COALESCE(cajas,0)) AS ingreso_real
                FROM prosagro.precio_real_venta GROUP BY contenedor_id
            )
            SELECT
                co.codigo,
                co.fecha_cargue,
                co.armado_completo,
                f.kg_export, f.cajas, f.pallets,
                f.costo_fruta, f.costo_certif,
                COALESCE(l.costo_log, 0)        AS costo_logistico,
                COALESCE(lr.costo_log_real, 0)  AS costo_logistico_real,
                COALESCE(ve.ingreso_est, 0)     AS ingreso_estimado,
                COALESCE(vr.ingreso_real, 0)    AS ingreso_real,
                (f.costo_fruta + f.costo_certif + COALESCE(l.costo_log,0)) AS costo_total
            FROM prosagro.contenedores co
            JOIN fruta f ON f.codigo = co.codigo
            LEFT JOIN logistica l       ON l.contenedor_id = co.id
            LEFT JOIN logistica_real lr ON lr.contenedor_id = co.id
            LEFT JOIN venta_est ve      ON ve.contenedor_id = co.id
            LEFT JOIN venta_real vr      ON vr.contenedor_id = co.id
            ORDER BY co.codigo
            """
        )
        cols = [d[0] for d in cur.description]
        filas = [dict(zip(cols, r)) for r in cur.fetchall()]

    for f in filas:
        kg = float(f["kg_export"] or 0)
        f["costo_por_kg"] = (float(f["costo_total"] or 0) / kg) if kg else 0
        f["costo_por_caja"] = (float(f["costo_total"] or 0) / float(f["cajas"])) if f["cajas"] else 0
        ing = float(f["ingreso_real"] or 0) or float(f["ingreso_estimado"] or 0)
        f["margen"] = ing - float(f["costo_total"] or 0)
        f["rentabilidad_pct"] = (f["margen"] / ing) if ing else None
    return filas


def detalle_sop(codigo: str) -> dict:
    """Desglose de costos + trazas de un contenedor."""
    resumen = next((c for c in contenedores_sop() if c["codigo"] == codigo), None)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT e.trazabilidad, e.zona, e.lote, e.predio, e.calibre_num,
                   SUM(e.cant_cajas)      AS cajas,
                   SUM(e.total_kg_netos)  AS kg,
                   MAX(k.precio_expo)     AS precio_expo,
                   SUM(e.total_kg_netos * COALESCE(k.precio_expo,0)) AS costo_fruta
            FROM prosagro.fruta_export e
            LEFT JOIN prosagro.kg_consolidado k ON k.trazabilidad = e.trazabilidad
            WHERE e.contenedor_codigo = %s AND e.categoria = 'C1'
            GROUP BY e.trazabilidad, e.zona, e.lote, e.predio, e.calibre_num
            ORDER BY e.zona, e.lote, e.calibre_num
            """,
            (codigo,),
        )
        cols = [d[0] for d in cur.description]
        trazas = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"resumen": resumen, "trazas": trazas}


def totales_globales() -> dict:
    filas = contenedores_sop()
    return {
        "contenedores": len(filas),
        "kg_export": sum(float(f["kg_export"] or 0) for f in filas),
        "costo_total": sum(float(f["costo_total"] or 0) for f in filas),
        "costo_fruta": sum(float(f["costo_fruta"] or 0) for f in filas),
        "costo_certif": sum(float(f["costo_certif"] or 0) for f in filas),
        "costo_logistico": sum(float(f["costo_logistico"] or 0) for f in filas),
        "ingreso_real": sum(float(f["ingreso_real"] or 0) for f in filas),
        "margen": sum(float(f["margen"] or 0) for f in filas),
    }
