"""Distribución de contenedores a clientes.

Reemplaza frmDistribucionContenedor: asignar pallets de un contenedor a los
clientes que los reciben. Guarda en distribucion_contenedor.
"""
from __future__ import annotations

from conexion import get_conn


def contenedores() -> list[str]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT codigo FROM prosagro.contenedores ORDER BY codigo DESC")
        return [r[0] for r in cur.fetchall()]


def clientes() -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, nombre, pais FROM prosagro.clientes WHERE activo ORDER BY nombre")
        return [{"id": r[0], "nombre": r[1], "pais": r[2]} for r in cur.fetchall()]


def distribucion_de(codigo: str) -> list[dict]:
    """Pallets del contenedor con el cliente asignado (o sin asignar)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT p.no_pallet, p.total_cajas, p.calibre_dominante,
                   cl.nombre AS cliente, d.tipo_negociacion
            FROM prosagro.pallets_contenedor p
            JOIN prosagro.contenedores co ON co.id = p.contenedor_id
            LEFT JOIN prosagro.distribucion_contenedor d ON d.pallet_id = p.id
            LEFT JOIN prosagro.clientes cl ON cl.id = d.cliente_id
            WHERE co.codigo = %s
            ORDER BY p.no_pallet
            """,
            (codigo,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def resumen_por_cliente(codigo: str) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT cl.nombre AS cliente, cl.pais,
                   COUNT(*) AS pallets,
                   COALESCE(SUM(p.total_cajas), 0) AS cajas,
                   MAX(d.tipo_negociacion) AS tipo_negociacion
            FROM prosagro.distribucion_contenedor d
            JOIN prosagro.contenedores co ON co.id = d.contenedor_id
            JOIN prosagro.pallets_contenedor p ON p.id = d.pallet_id
            JOIN prosagro.clientes cl ON cl.id = d.cliente_id
            WHERE co.codigo = %s
            GROUP BY cl.nombre, cl.pais
            ORDER BY cajas DESC
            """,
            (codigo,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def asignar_pallet(codigo: str, no_pallet: int, cliente_id: int, tipo_neg: str | None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM prosagro.contenedores WHERE codigo = %s", (codigo,))
        cont = cur.fetchone()
        if not cont:
            return
        cont_id = cont[0]
        cur.execute(
            """INSERT INTO prosagro.pallets_contenedor (contenedor_id, no_pallet)
               VALUES (%s,%s) ON CONFLICT (contenedor_id, no_pallet) DO NOTHING""",
            (cont_id, no_pallet),
        )
        cur.execute(
            "SELECT id FROM prosagro.pallets_contenedor WHERE contenedor_id=%s AND no_pallet=%s",
            (cont_id, no_pallet),
        )
        pallet_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO prosagro.distribucion_contenedor
                 (contenedor_id, pallet_id, cliente_id, tipo_negociacion)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (contenedor_id, pallet_id)
               DO UPDATE SET cliente_id=EXCLUDED.cliente_id,
                             tipo_negociacion=EXCLUDED.tipo_negociacion,
                             actualizado_en=now()""",
            (cont_id, pallet_id, cliente_id, tipo_neg),
        )
        conn.commit()


def totales_por_cliente_global() -> list[dict]:
    """Cuántos pallets/cajas ha recibido cada cliente en total."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT cl.nombre, cl.pais,
                   COUNT(*) AS pallets,
                   COALESCE(SUM(p.total_cajas),0) AS cajas,
                   COUNT(DISTINCT co.codigo) AS contenedores
            FROM prosagro.distribucion_contenedor d
            JOIN prosagro.clientes cl ON cl.id = d.cliente_id
            JOIN prosagro.pallets_contenedor p ON p.id = d.pallet_id
            JOIN prosagro.contenedores co ON co.id = d.contenedor_id
            GROUP BY cl.nombre, cl.pais
            ORDER BY cajas DESC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
