"""Ventas: precios estimados/reales de venta y plano de facturación a PyA.

Reemplaza frmPrecioEstimado / frmAsignarPrecios / frmArchivosPlanoFacturacion.
Los precios estimados y reales viven en precio_estimado_venta / precio_real_venta.
El plano de facturación de venta se genera para cargar a PyA (por ahora CSV;
API cuando lleguen credenciales).
"""
from __future__ import annotations

import csv
import io

from conexion import get_conn


def contenedores() -> list[str]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT codigo FROM prosagro.contenedores ORDER BY codigo DESC")
        return [r[0] for r in cur.fetchall()]


def precios_estimados(codigo: str) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT cl.nombre AS cliente, pe.precio_estimado, pe.moneda, pe.cajas,
                   pe.fecha_recogida_estimada, pe.observaciones
            FROM prosagro.precio_estimado_venta pe
            JOIN prosagro.contenedores co ON co.id = pe.contenedor_id
            JOIN prosagro.clientes cl ON cl.id = pe.cliente_id
            WHERE co.codigo = %s
            ORDER BY cl.nombre
            """,
            (codigo,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def precios_reales(codigo: str) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT cl.nombre AS cliente, pr.tipo_documento, pr.consecutivo_ne,
                   pr.cajas, pr.precio_unitario, pr.moneda,
                   pr.fecha_recogida_real, pr.observaciones
            FROM prosagro.precio_real_venta pr
            JOIN prosagro.contenedores co ON co.id = pr.contenedor_id
            JOIN prosagro.clientes cl ON cl.id = pr.cliente_id
            WHERE co.codigo = %s
            ORDER BY cl.nombre
            """,
            (codigo,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def registrar_precio_real(codigo: str, cliente_id: int, cajas: float,
                          precio_unitario: float, moneda: str,
                          consecutivo_ne: str | None, observaciones: str | None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM prosagro.contenedores WHERE codigo=%s", (codigo,))
        cont = cur.fetchone()
        if not cont:
            return
        cur.execute(
            """INSERT INTO prosagro.precio_real_venta
                (contenedor_id, cliente_id, tipo_documento, consecutivo_ne, cajas,
                 precio_unitario, moneda, observaciones)
               VALUES (%s,%s,'FV',%s,%s,%s,%s,%s)""",
            (cont[0], cliente_id, consecutivo_ne, cajas, precio_unitario, moneda, observaciones),
        )
        conn.commit()


def resumen_ventas() -> list[dict]:
    """Ingreso estimado por contenedor (moneda original)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT co.codigo, pe.moneda,
                   COUNT(DISTINCT pe.cliente_id) AS clientes,
                   SUM(pe.cajas)                 AS cajas,
                   SUM(pe.precio_estimado * COALESCE(pe.cajas,0)) AS ingreso_estimado
            FROM prosagro.precio_estimado_venta pe
            JOIN prosagro.contenedores co ON co.id = pe.contenedor_id
            GROUP BY co.codigo, pe.moneda
            ORDER BY co.codigo DESC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def plano_facturacion(codigo: str) -> bytes:
    """CSV plano de facturación de venta para cargar a PyA."""
    filas = precios_reales(codigo) or precios_estimados(codigo)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["contenedor", "cliente", "cajas", "precio_unitario", "moneda", "referencia"])
    for f in filas:
        w.writerow([
            codigo, f.get("cliente"), f.get("cajas"),
            f.get("precio_unitario") or f.get("precio_estimado"),
            f.get("moneda"), f.get("consecutivo_ne") or "",
        ])
    return out.getvalue().encode("utf-8-sig")
