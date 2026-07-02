"""Servicio de liquidación GGN / ICA por contenedor.

Reemplaza frmGGN del VBA CORRIGIENDO su bug: allá el costo por ICA
sobre-escribía el costo por GGN (líneas 227-245). Acá se calculan SEPARADOS y
se suman.

Lógica: para las trazas de exportación (categoría C1) de un contenedor armado
'Completo' en un rango de fechas, si el productor NO tiene su propio GGN/ICA
vigente, se le cobra la certificación al precio vigente de precio_certificacion.
"""
from __future__ import annotations

import datetime as dt

from conexion import get_conn


def liquidacion_por_contenedor(contenedor: str) -> list[dict]:
    """Devuelve el detalle de liquidación GGN/ICA de un contenedor.

    Usa costo_total_ggn y costo_total_ica ya calculados por el motor SOP en
    kg_consolidado (que los guarda SEPARADOS)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT
                e.contenedor_codigo,
                k.trazabilidad,
                k.zona, k.lote,
                k.nombre_finca,
                k.propietario,
                k.documento,
                k.ggn, k.ica,
                k.kg_expo_real,
                k.fecha_procesamiento,
                k.costo_total_ggn,
                k.costo_total_ica,
                (k.costo_total_ggn + k.costo_total_ica) AS costo_certif_total
            FROM prosagro.kg_consolidado k
            JOIN prosagro.fruta_export e ON e.trazabilidad = k.trazabilidad
            WHERE e.contenedor_codigo = %s
              AND e.categoria = 'C1'
            ORDER BY k.propietario, k.trazabilidad
            """,
            (contenedor,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def liquidacion_por_rango(fecha_desde: dt.date, fecha_hasta: dt.date) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT
                k.propietario, k.documento, k.zona, k.lote, k.nombre_finca,
                k.ggn, k.ica,
                SUM(k.kg_expo_real)       AS kg_expo,
                SUM(k.costo_total_ggn)    AS costo_ggn,
                SUM(k.costo_total_ica)    AS costo_ica,
                SUM(k.costo_total_ggn + k.costo_total_ica) AS costo_total
            FROM prosagro.kg_consolidado k
            WHERE k.fecha_procesamiento BETWEEN %s AND %s
            GROUP BY k.propietario, k.documento, k.zona, k.lote, k.nombre_finca, k.ggn, k.ica
            HAVING SUM(k.costo_total_ggn + k.costo_total_ica) > 0
            ORDER BY costo_total DESC
            """,
            (fecha_desde, fecha_hasta),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def contenedores_disponibles() -> list[str]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT codigo FROM prosagro.contenedores ORDER BY codigo")
        return [r[0] for r in cur.fetchall()]
