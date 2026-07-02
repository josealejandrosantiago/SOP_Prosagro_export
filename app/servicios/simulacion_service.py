"""Simulación de viaje — calidad de la fruta en frío.

Alimenta el tablero con las 3 gráficas que determinan qué tan bien/mal llega la
fruta y cuánto afecta a los contenedores:
  1. VOLUMEN    — volumen de exportación (real) por semana.
  2. INCIDENCIA — % de muestras con eventos/defectos (no 'BUEN ESTADO') por semana.
  3. SEVERIDAD  — severidad promedio de los defectos por semana.
Fuente: hoja 'Simulación Viaje' (tabla prosagro.simulacion_viaje).
"""
from __future__ import annotations

from conexion import get_conn

BUEN_ESTADO = "BUEN ESTADO"


def anios() -> list[int]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT anio FROM prosagro.simulacion_viaje ORDER BY anio DESC")
        return [r[0] for r in cur.fetchall()]


def volumen_por_semana(anio: int) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT semana, ROUND(SUM(volumen)::numeric, 0) AS volumen
            FROM prosagro.simulacion_viaje
            WHERE anio = %s
            GROUP BY semana ORDER BY semana
            """,
            (anio,),
        )
        return [{"semana": r[0], "volumen": float(r[1] or 0)} for r in cur.fetchall()]


def incidencia_por_semana(anio: int) -> list[dict]:
    """% de eventos con defecto sobre el total de muestra, por semana."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT semana,
                   ROUND((SUM(cantidad_evento) FILTER (WHERE UPPER(evento) <> %s)
                          / NULLIF(SUM(cantidad_evento), 0) * 100)::numeric, 2) AS incidencia_pct
            FROM prosagro.simulacion_viaje
            WHERE anio = %s AND evento IS NOT NULL
            GROUP BY semana ORDER BY semana
            """,
            (BUEN_ESTADO, anio),
        )
        return [{"semana": r[0], "incidencia_pct": float(r[1] or 0)} for r in cur.fetchall()]


def severidad_por_semana(anio: int) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT semana, ROUND(AVG(severidad_promedio)::numeric, 3) AS severidad
            FROM prosagro.simulacion_viaje
            WHERE anio = %s AND severidad_promedio IS NOT NULL
            GROUP BY semana ORDER BY semana
            """,
            (anio,),
        )
        return [{"semana": r[0], "severidad": float(r[1] or 0)} for r in cur.fetchall()]


def eventos_top(anio: int, limite: int = 12) -> list[dict]:
    """Top de eventos/defectos por cantidad (excluye BUEN ESTADO)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT evento,
                   COUNT(*) AS muestras,
                   ROUND(SUM(cantidad_evento)::numeric, 0) AS cantidad,
                   ROUND(AVG(porcentaje)::numeric, 4) AS pct_promedio
            FROM prosagro.simulacion_viaje
            WHERE anio = %s AND evento IS NOT NULL AND UPPER(evento) <> %s
            GROUP BY evento
            ORDER BY cantidad DESC NULLS LAST
            LIMIT %s
            """,
            (anio, BUEN_ESTADO, limite),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def detalle(anio: int, semana: int | None = None) -> list[dict]:
    q = """
        SELECT fecha_inspeccion, zona, lote, semana, tipo_muestra, evento,
               cantidad_muestra, cantidad_evento, porcentaje, severidad_promedio,
               volumen, ubicacion
        FROM prosagro.simulacion_viaje
        WHERE anio = %s
    """
    params = [anio]
    if semana is not None:
        q += " AND semana = %s"
        params.append(semana)
    q += " ORDER BY semana, zona, lote LIMIT 1000"
    with get_conn() as c, c.cursor() as cur:
        cur.execute(q, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def kpis(anio: int) -> dict:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT ROUND(SUM(volumen)::numeric, 0) AS volumen,
                   ROUND((SUM(cantidad_evento) FILTER (WHERE UPPER(evento) <> %s)
                          / NULLIF(SUM(cantidad_evento), 0) * 100)::numeric, 2) AS incidencia,
                   ROUND(AVG(severidad_promedio)::numeric, 3) AS severidad,
                   COUNT(DISTINCT semana) AS semanas
            FROM prosagro.simulacion_viaje WHERE anio = %s
            """,
            (BUEN_ESTADO, anio),
        )
        r = cur.fetchone()
    return {
        "volumen": float(r[0] or 0),
        "incidencia": float(r[1] or 0),
        "severidad": float(r[2] or 0),
        "semanas": r[3] or 0,
    }
