"""Servicio de causales de rechazo.

Persiste el parser_calidad cruzando el no_cargue contra kg_consolidado para
obtener la trazabilidad, zona, lote y kg nacional (base del cálculo
kg_con_causal = porcentaje × kg_nacional), tal como el VBA CommandButton21.
"""
from __future__ import annotations

from pathlib import Path

from conexion import get_conn
from ingesta.parser_calidad import parsear


def cargar_reporte(ruta: str | Path) -> dict:
    """Carga un reporte de calidad a la tabla causales_rechazo. Idempotente por
    (trazabilidad + causal + severidad)."""
    rep = parsear(ruta)
    if not rep.no_cargue or not rep.causales:
        return {"causales": 0, "avisos": rep.avisos + ["Sin no_cargue o sin causales"]}

    with get_conn() as conn, conn.cursor() as cur:
        # Buscar la traza en kg_consolidado por no_cargue (vía ingresos)
        cur.execute(
            """
            SELECT k.trazabilidad, k.zona, k.lote, k.kg_nacional
            FROM prosagro.kg_consolidado k
            JOIN prosagro.ingresos i ON i.trazabilidad = k.trazabilidad
            WHERE i.no_cargue = %s
            ORDER BY k.fecha_ingreso DESC
            LIMIT 1
            """,
            (rep.no_cargue,),
        )
        row = cur.fetchone()
        if not row:
            return {"causales": 0, "avisos": [f"no_cargue {rep.no_cargue} no está en kg_consolidado"]}
        traza, zona, lote, kg_nal = row
        kg_nal = float(kg_nal or 0)

        insertadas = 0
        for c in rep.causales:
            cur.execute(
                """
                INSERT INTO prosagro.causales_rechazo
                    (fecha, trazabilidad, causal, porcentaje, kg_nacional,
                     zona, lote, severidad, archivo_origen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (c.fecha, traza, c.causal, c.porcentaje, kg_nal, zona, lote,
                 c.severidad, rep.archivo),
            )
            insertadas += 1
        conn.commit()
    return {"causales": insertadas, "trazabilidad": traza, "avisos": rep.avisos}


def resumen(limite: int = 500) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT fecha, trazabilidad, causal, severidad,
                   porcentaje, kg_nacional, kg_con_causal, zona, lote
            FROM prosagro.causales_rechazo
            ORDER BY fecha DESC, trazabilidad
            LIMIT %s
            """,
            (limite,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def resumen_por_causal() -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT causal, severidad,
                   COUNT(*) AS ocurrencias,
                   ROUND(AVG(porcentaje)::numeric, 4) AS pct_promedio,
                   ROUND(SUM(kg_con_causal)::numeric, 0) AS kg_afectados
            FROM prosagro.causales_rechazo
            GROUP BY causal, severidad
            ORDER BY kg_afectados DESC NULLS LAST
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
