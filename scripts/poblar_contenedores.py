"""Crea/actualiza los registros en `contenedores` a partir de las asignaciones
que ya trae `fruta_export` (col # Contenedor del Excel).

Los contenedores históricos (OP-246+, LOC-, TNLC-, EXP-, AR-) ya vienen armados
en el Excel, así que se marcan armado_completo=TRUE con sus totales de cajas/kg
y pallets calculados desde fruta_export.

No toca los códigos que NO son contenedores reales (Ajustes, Caja ICA,
Contramuestra, Desperdicio, Simulación).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
except AttributeError:
    pass

from conexion import get_conn

# Sólo códigos que son contenedores reales de exportación
PATRON = r"^(OP|LOC|TNLC|EXP|AR)-?[0-9]"


def poblar() -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT contenedor_codigo,
                   ROUND(SUM(cant_cajas))::int          AS cajas,
                   ROUND(SUM(total_kg_netos))::numeric  AS kg,
                   COUNT(DISTINCT pallet_no) FILTER (WHERE pallet_no IS NOT NULL) AS pallets,
                   MIN(fecha_procesamiento)             AS desde,
                   MAX(fecha_procesamiento)             AS hasta
            FROM prosagro.fruta_export
            WHERE contenedor_codigo ~ '{PATRON}'
            GROUP BY contenedor_codigo
            ORDER BY contenedor_codigo
            """
        )
        rows = cur.fetchall()

        creados = 0
        actualizados = 0
        for codigo, cajas, kg, pallets, desde, hasta in rows:
            cur.execute(
                "SELECT id FROM prosagro.contenedores WHERE codigo = %s", (codigo,)
            )
            existe = cur.fetchone()
            if existe:
                # No pisar los que tienen packing list cargado (OP-327/328);
                # solo asegurar armado_completo=TRUE y totales si están en 0.
                cur.execute(
                    """
                    UPDATE prosagro.contenedores
                       SET armado_completo = TRUE,
                           total_cajas   = GREATEST(total_cajas, %s),
                           fecha_cargue  = COALESCE(fecha_cargue, %s),
                           actualizado_en = now()
                     WHERE codigo = %s
                    """,
                    (cajas or 0, hasta, codigo),
                )
                actualizados += 1
            else:
                cur.execute(
                    """
                    INSERT INTO prosagro.contenedores
                        (codigo, fecha_inicio, fecha_cargue, total_pallets,
                         total_cajas, armado_completo, observaciones)
                    VALUES (%s, %s, %s, %s, %s, TRUE, 'Histórico (asignado en Excel)')
                    """,
                    (codigo, desde, hasta, pallets or 0, cajas or 0),
                )
                creados += 1
        conn.commit()
    return {"total": len(rows), "creados": creados, "actualizados": actualizados}


if __name__ == "__main__":
    r = poblar()
    print(f"Contenedores procesados: {r['total']}  (nuevos: {r['creados']}, actualizados: {r['actualizados']})")
