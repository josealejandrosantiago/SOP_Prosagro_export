"""Servicio de liquidación a productores.

Reúne la lógica de negocio que en el VBA estaba repartida en:
  - frmLiquidarproductores.CommandButton2 → detalle por productor/semana.
  - frmInicio.CommandButton8            → informe de pago (agrupado por fecha
                                          de pago × documento × propietario).

Todo se calcula sobre `kg_consolidado` (que ya trae costos, ashofrucol y
retención en la fuente calculados por el motor SOP).

Reglas del negocio preservadas:
  - %export = kg_expo_real / kg_total.
  - Nacional+deshidratación se muestran juntos (kg_nacional + kg_merma).
  - valor_a_girar = costo_total − ashofrucol − retencion_fuente.
  - El productor de pago es `propietario` (dueño de la finca), no el nombre
    comercial de la finca.
"""
from __future__ import annotations

from conexion import get_conn


def anios_disponibles() -> list[int]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT anio FROM prosagro.kg_consolidado ORDER BY anio DESC")
        return [r[0] for r in cur.fetchall()]


def semanas_de_anio(anio: int) -> list[int]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT semana FROM prosagro.kg_consolidado WHERE anio = %s ORDER BY semana",
            (anio,),
        )
        return [r[0] for r in cur.fetchall()]


def productores_de_semana(anio: int, semana: int) -> list[dict]:
    """Lista de productores (propietario + documento + teléfono) con movimiento
    en la semana, con su total a girar."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT propietario,
                   MAX(documento)                      AS documento,
                   MAX(telefono)                       AS telefono,
                   COUNT(*)                            AS lotes,
                   SUM(kg_total)                       AS kg_total,
                   SUM(kg_expo_real)                   AS kg_expo,
                   SUM(costo_total_expo + costo_total_nal + costo_total_desh) AS costo_total,
                   SUM(ashofrucol)                     AS ashofrucol,
                   SUM(retencion_fuente)               AS retencion,
                   SUM(costo_total_expo + costo_total_nal + costo_total_desh
                       - ashofrucol - retencion_fuente) AS valor_girar
            FROM prosagro.kg_consolidado
            WHERE anio = %s AND semana = %s AND propietario IS NOT NULL
            GROUP BY propietario
            ORDER BY valor_girar DESC
            """,
            (anio, semana),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def detalle_productor(anio: int, semana: int, propietario: str) -> list[dict]:
    """Detalle lote por lote de un productor en una semana — la tabla que va
    en el PDF de liquidación."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT
                trazabilidad,
                zona,
                lote,
                nombre_finca,
                fecha_ingreso,
                fecha_procesamiento,
                fecha_pago,
                canastillas,
                kg_total,
                kg_expo_real,
                CASE WHEN kg_total > 0 THEN kg_expo_real / kg_total ELSE 0 END AS pct_expo,
                precio_expo,
                costo_total_expo,
                (kg_nacional + kg_merma)                                  AS kg_nal_desh,
                CASE WHEN kg_total > 0 THEN (kg_nacional + kg_merma) / kg_total ELSE 0 END AS pct_nal_desh,
                precio_nal,
                (costo_total_nal + costo_total_desh)                      AS costo_nal_desh,
                (costo_total_expo + costo_total_nal + costo_total_desh)    AS costo_total,
                ashofrucol,
                retencion_fuente,
                (costo_total_expo + costo_total_nal + costo_total_desh
                 - ashofrucol - retencion_fuente)                         AS valor_girar
            FROM prosagro.kg_consolidado
            WHERE anio = %s AND semana = %s AND propietario = %s
            ORDER BY fecha_ingreso, lote
            """,
            (anio, semana, propietario),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def informe_pago(anio: int, semana_desde: int, semana_hasta: int) -> list[dict]:
    """Replica frmInicio.CommandButton8: agrupa por fecha de pago × documento ×
    propietario y devuelve totales a girar. Sirve para programar los pagos del
    viernes."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT
                fecha_pago,
                propietario,
                MAX(documento)                       AS documento,
                COUNT(*)                             AS lotes,
                SUM(costo_total_expo)                AS costo_expo,
                SUM(costo_total_nal)                 AS costo_nal,
                SUM(costo_total_desh)                AS costo_desh,
                SUM(costo_total_expo + costo_total_nal + costo_total_desh) AS costo_total,
                SUM(ashofrucol)                      AS ashofrucol,
                SUM(retencion_fuente)                AS retencion,
                SUM(costo_total_expo + costo_total_nal + costo_total_desh
                    - ashofrucol - retencion_fuente) AS valor_girar
            FROM prosagro.kg_consolidado
            WHERE anio = %s AND semana BETWEEN %s AND %s
              AND fecha_pago IS NOT NULL AND propietario IS NOT NULL
            GROUP BY fecha_pago, propietario
            ORDER BY fecha_pago, valor_girar DESC
            """,
            (anio, semana_desde, semana_hasta),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def totales_semana(anio: int, semana: int) -> dict:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*)                             AS trazas,
                COUNT(DISTINCT propietario)          AS productores,
                COALESCE(SUM(kg_total), 0)           AS kg_total,
                COALESCE(SUM(kg_expo_real), 0)       AS kg_expo,
                COALESCE(SUM(costo_total_expo + costo_total_nal + costo_total_desh), 0) AS costo_total,
                COALESCE(SUM(ashofrucol), 0)         AS ashofrucol,
                COALESCE(SUM(retencion_fuente), 0)   AS retencion,
                COALESCE(SUM(costo_total_expo + costo_total_nal + costo_total_desh
                             - ashofrucol - retencion_fuente), 0) AS valor_girar
            FROM prosagro.kg_consolidado
            WHERE anio = %s AND semana = %s
            """,
            (anio, semana),
        )
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, cur.fetchone()))
