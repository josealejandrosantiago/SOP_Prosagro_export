"""Simulación de viaje — calidad de la fruta en frío (réplica del tablero Power BI).

Layout del tablero:
  Fila 1: Volumen de exportación por lote (semana) | Volumen semanal (tendencia)
  Fila 2: Eventos 100% apilados por lote (semana)  | Eventos de la semana (agregado)
  Fila 3: Severidad (Antracnosis) por lote          | Escala de evaluación (0-5)

Todo se filtra por una semana seleccionada y se discrimina por 'zona-lote'
(zona EXTERNA, ej. 124-101). Fuente: hoja 'Simulación Viaje'.
"""
from __future__ import annotations

from conexion import get_conn

BUEN_ESTADO = "BUEN ESTADO"

ESCALA_EVALUACION = [
    "0 — Ausencia de síntomas.",
    "1 — Lesiones muy pequeñas, puntuales (menos del 1% de la superficie afectada).",
    "2 — Pequeñas lesiones coalescentes (1-5% de la superficie afectada).",
    "3 — Lesiones moderadas (6-25% de la superficie afectada).",
    "4 — Lesiones grandes y numerosas (26-50% de la superficie afectada).",
    "5 — Más del 50% de la superficie afectada, pudrición severa.",
]


def anios() -> list[int]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT anio FROM prosagro.simulacion_viaje ORDER BY anio DESC")
        return [r[0] for r in cur.fetchall()]


def semanas(anio: int) -> list[int]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT semana FROM prosagro.simulacion_viaje WHERE anio=%s ORDER BY semana",
            (anio,),
        )
        return [r[0] for r in cur.fetchall()]


# ── zona interna → externa (124-101) para mostrar como en el Power BI ────────
_ZONA_LOTE = (
    "COALESCE(z.codigo_externo::text, s.zona) || '-' || s.lote"
)

# Filtro de zona por nombre → código interno
ZONAS_FILTRO = {"Urrao": "02", "San José": "01", "Oriente": "03"}


def _where_zona_lote(zona: str | None, lote: str | None) -> tuple[str, list]:
    """Devuelve el fragmento WHERE extra + params para filtrar por zona/lote."""
    frag, params = "", []
    if zona:
        frag += " AND s.zona = %s"
        params.append(ZONAS_FILTRO.get(zona, zona))
    if lote:
        frag += " AND s.lote = %s"
        params.append(lote)
    return frag, params


def lotes_de(anio: int, semana: int, zona: str | None = None, lote: str | None = None) -> list[str]:
    """Lista maestra de zona-lote de la semana (para alinear las 3 gráficas)."""
    fz, pz = _where_zona_lote(zona, lote)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT {_ZONA_LOTE} AS zona_lote
            FROM prosagro.simulacion_viaje s
            LEFT JOIN prosagro.zonas z ON z.codigo_interno = s.zona
            WHERE s.anio=%s AND s.semana=%s {fz}
            ORDER BY zona_lote
            """,
            (anio, semana, *pz),
        )
        return [r[0] for r in cur.fetchall()]


def lotes_disponibles(anio: int, semana: int, zona: str | None = None) -> list[str]:
    """Lotes (solo el número) para el selector, filtrados por zona."""
    fz, pz = _where_zona_lote(zona, None)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""SELECT DISTINCT s.lote FROM prosagro.simulacion_viaje s
                WHERE s.anio=%s AND s.semana=%s {fz} ORDER BY s.lote""",
            (anio, semana, *pz),
        )
        return [r[0] for r in cur.fetchall()]


def volumen_por_lote(anio: int, semana: int, zona: str | None = None, lote: str | None = None) -> list[dict]:
    fz, pz = _where_zona_lote(zona, lote)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_ZONA_LOTE} AS zona_lote,
                   ROUND(SUM(s.volumen)::numeric, 0) AS volumen
            FROM prosagro.simulacion_viaje s
            LEFT JOIN prosagro.zonas z ON z.codigo_interno = s.zona
            WHERE s.anio=%s AND s.semana=%s {fz}
            GROUP BY zona_lote
            HAVING SUM(s.volumen) > 0
            ORDER BY zona_lote
            """,
            (anio, semana, *pz),
        )
        return [{"zona_lote": r[0], "volumen": float(r[1] or 0)} for r in cur.fetchall()]


def volumen_semanal(anio: int, zona: str | None = None, lote: str | None = None) -> list[dict]:
    fz, pz = _where_zona_lote(zona, lote)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.semana, ROUND(SUM(s.volumen)::numeric, 0) AS volumen
            FROM prosagro.simulacion_viaje s
            WHERE s.anio=%s {fz}
            GROUP BY s.semana HAVING SUM(s.volumen) > 0 ORDER BY s.semana
            """,
            (anio, *pz),
        )
        return [{"semana": r[0], "volumen": float(r[1] or 0)} for r in cur.fetchall()]


def eventos_por_lote(anio: int, semana: int, zona: str | None = None, lote: str | None = None) -> list[dict]:
    """% de cada evento por lote (para barras 100% apiladas)."""
    fz, pz = _where_zona_lote(zona, lote)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_ZONA_LOTE} AS zona_lote, s.evento,
                   SUM(s.cantidad_evento) AS cantidad
            FROM prosagro.simulacion_viaje s
            LEFT JOIN prosagro.zonas z ON z.codigo_interno = s.zona
            WHERE s.anio=%s AND s.semana=%s AND s.evento IS NOT NULL {fz}
            GROUP BY zona_lote, s.evento
            ORDER BY zona_lote
            """,
            (anio, semana, *pz),
        )
        return [{"zona_lote": r[0], "evento": r[1], "cantidad": float(r[2] or 0)} for r in cur.fetchall()]


def eventos_semanal(anio: int, semana: int) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT evento, SUM(cantidad_evento) AS cantidad
            FROM prosagro.simulacion_viaje
            WHERE anio=%s AND semana=%s AND evento IS NOT NULL
            GROUP BY evento
            """,
            (anio, semana),
        )
        return [{"evento": r[0], "cantidad": float(r[1] or 0)} for r in cur.fetchall()]


def severidad_por_lote(anio: int, semana: int, evento: str = "ANTRACNOSIS",
                       zona: str | None = None, lote: str | None = None) -> list[dict]:
    """Severidad promedio por lote (del evento indicado)."""
    fz, pz = _where_zona_lote(zona, lote)
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_ZONA_LOTE} AS zona_lote,
                   ROUND(AVG(s.severidad_promedio)::numeric, 1) AS severidad
            FROM prosagro.simulacion_viaje s
            LEFT JOIN prosagro.zonas z ON z.codigo_interno = s.zona
            WHERE s.anio=%s AND s.semana=%s
              AND s.severidad_promedio IS NOT NULL
              AND (UPPER(s.evento) = %s OR %s = '') {fz}
            GROUP BY zona_lote
            HAVING AVG(s.severidad_promedio) > 0
            ORDER BY zona_lote
            """,
            (anio, semana, evento.upper(), evento, *pz),
        )
        return [{"zona_lote": r[0], "severidad": float(r[1] or 0)} for r in cur.fetchall()]


def eventos_disponibles(anio: int, semana: int) -> list[str]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT evento FROM prosagro.simulacion_viaje
               WHERE anio=%s AND semana=%s AND evento IS NOT NULL
               AND UPPER(evento) <> %s ORDER BY evento""",
            (anio, semana, BUEN_ESTADO),
        )
        return [r[0] for r in cur.fetchall()]


def totales_semana(anio: int, semana: int) -> dict:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT ROUND(SUM(volumen)::numeric,0) AS volumen,
                   ROUND((SUM(cantidad_evento) FILTER (WHERE UPPER(evento) <> %s)
                          / NULLIF(SUM(cantidad_evento),0) * 100)::numeric, 2) AS incidencia,
                   ROUND(AVG(severidad_promedio)::numeric, 2) AS severidad
            FROM prosagro.simulacion_viaje WHERE anio=%s AND semana=%s
            """,
            (BUEN_ESTADO, anio, semana),
        )
        r = cur.fetchone()
    return {"volumen": float(r[0] or 0), "incidencia": float(r[1] or 0), "severidad": float(r[2] or 0)}
