"""Conciliación de facturación — cruce de facturas contra operaciones.

Patrón tomado del SOP NexFresh (allí está casi resuelto). Diferencias en
Prosagro:
  - Las operaciones salen como 'EXP' + consecutivo (el # invoice del cronograma
    = el número de la OP sin prefijo; OP-325 → invoice 325).
  - La hoja 'Cronograma' trae los datos del BL, número de contenedor físico,
    invoice, naviera, puerto, etc. → son las llaves para cruzar las facturas
    que llegan de los proveedores logísticos.

Este servicio expone la tabla de operaciones (cronograma) lista para cruzar y
guarda las facturas recibidas / su match. El parser de PDF/XML de facturas y la
bandeja de correo (Graph) se conectan en Fase 6 (igual que NexFresh).
"""
from __future__ import annotations

from conexion import get_conn


def operaciones() -> list[dict]:
    """Cuadro de operaciones del cronograma con las llaves de cruce."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT co.contenedor_codigo,
                   ('EXP-' || co.invoice)          AS exp,
                   co.invoice,
                   co.contenedor_fisico,
                   co.bl,
                   co.booking,
                   co.naviera,
                   co.motonave,
                   co.puerto_origen,
                   co.puerto_destino,
                   co.fecha_embarque,
                   co.fecha_llegada,
                   co.semana_llegada,
                   co.importador,
                   co.icoterm_facturacion,
                   co.tarifa_flete_terrestre,
                   (SELECT COUNT(*) FROM prosagro.factura_recibida f
                     WHERE f.contenedor_ref = co.contenedor_codigo) AS facturas
            FROM prosagro.cronograma_operaciones co
            ORDER BY co.contenedor_codigo DESC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def buscar_operacion(clave: str) -> list[dict]:
    """Busca una operación por OP, EXP, invoice, contenedor físico o BL."""
    clave = (clave or "").strip()
    if not clave:
        return []
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT contenedor_codigo, ('EXP-'||invoice) AS exp, invoice,
                   contenedor_fisico, bl, naviera, puerto_destino, fecha_llegada
            FROM prosagro.cronograma_operaciones
            WHERE contenedor_codigo ILIKE %s
               OR invoice = %s
               OR contenedor_fisico ILIKE %s
               OR bl ILIKE %s
               OR ('EXP-'||invoice) ILIKE %s
            ORDER BY contenedor_codigo DESC
            """,
            (f"%{clave}%", clave.replace("EXP-", "").replace("OP-", ""),
             f"%{clave}%", f"%{clave}%", f"%{clave}%"),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def facturas_recibidas(estado: str | None = None) -> list[dict]:
    q = """
        SELECT f.id, f.fecha_recepcion, f.asunto, f.adjunto_nombre, p.nombre AS proveedor,
               f.contenedor_ref, f.valor_factura, f.moneda, f.estado_cruce
        FROM prosagro.factura_recibida f
        LEFT JOIN prosagro.proveedores p ON p.id = f.proveedor_id
    """
    params: list = []
    if estado:
        q += " WHERE f.estado_cruce = %s"
        params.append(estado)
    q += " ORDER BY f.fecha_recepcion DESC LIMIT 500"
    with get_conn() as c, c.cursor() as cur:
        cur.execute(q, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def registrar_factura_manual(contenedor_ref: str, valor: float, moneda: str,
                             proveedor_nombre: str | None, adjunto: str | None) -> int:
    """Registra una factura manual y la deja marcada como cruzada contra la
    operación si el contenedor existe en el cronograma."""
    with get_conn() as conn, conn.cursor() as cur:
        prov_id = None
        if proveedor_nombre:
            cur.execute("SELECT id FROM prosagro.proveedores WHERE nombre ILIKE %s LIMIT 1",
                        (f"%{proveedor_nombre}%",))
            r = cur.fetchone()
            prov_id = r[0] if r else None
        cur.execute("SELECT 1 FROM prosagro.cronograma_operaciones WHERE contenedor_codigo = %s",
                    (contenedor_ref,))
        estado = "CRUZADO" if cur.fetchone() else "PENDIENTE"
        cur.execute(
            """INSERT INTO prosagro.factura_recibida
                (contenedor_ref, valor_factura, moneda, proveedor_id, adjunto_nombre, estado_cruce)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (contenedor_ref, valor, moneda, prov_id, adjunto, estado),
        )
        fid = cur.fetchone()[0]
        conn.commit()
    return fid


def resumen() -> dict:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM prosagro.cronograma_operaciones")
        ops = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE estado_cruce='CRUZADO') FROM prosagro.factura_recibida")
        fr = cur.fetchone()
    return {"operaciones": ops, "facturas": fr[0], "cruzadas": fr[1]}
