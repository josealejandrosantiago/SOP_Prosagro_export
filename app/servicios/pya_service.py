"""Emisión de documentos a PyA (SAG ERP).

Reemplaza frmCuentasyfacturacion (cuentas por cobrar + factura electrónica) del
VBA, que generaba archivos planos SIIGO. Acá:
  - `generar_cuentas_cobro()` construye las filas tipo DR (una expo + una
    nacional por productor) igual que el VBA, aplicando la regla clave:
    precio unitario expo = (costo_expo + costo_desh) / kg_expo.
  - Se guardan en `pya_documento_emitido` con estado PENDIENTE.
  - `exportar_plano()` devuelve el CSV para cargar a PyA mientras no esté la API.
  - Cuando haya PYA_API_BASE + credenciales, `enviar_a_pya()` hace el POST real.

Códigos maestros confirmados: artículo Gulupa=FGU1001, Uchuva=FUC1003;
bodegas EXGULUPA/EXUC (expo) y NLGU/NLUC (nacional); prefijo DSSE, centro P3.
"""
from __future__ import annotations

import csv
import io
import os

from conexion import get_conn

ART = {"gulupa": ("FGU1001", "EXGULUPA", "NLGU"), "uchuva": ("FUC1003", "EXUC", "NLUC")}


def _fruta_de_zona(zona: str) -> str:
    # zonas 01/02/03/05 = gulupa; 04 = uchuva; 06 = mango (tratado como gulupa por defecto)
    return "uchuva" if zona == "04" else "gulupa"


def generar_cuentas_cobro(
    anio: int, semana: int, consecutivo_inicial: int, tipo: str = "DR_CXC",
) -> list[dict]:
    """Construye las filas de cuentas por cobrar (o factura electrónica) para la
    semana. tipo='DR_CXC' (fact_elect='No') o 'FE_COMPRA' (fact_elect='Si').

    Regla del VBA: por productor emite hasta 2 filas (expo + nacional). El
    precio unitario expo mete la deshidratación dentro:
        precio_expo_pya = (costo_expo + costo_desh) / kg_expo.
    """
    fe_flag = "No" if tipo == "DR_CXC" else "Si"
    filas: list[dict] = []
    consec = consecutivo_inicial

    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT trazabilidad, zona, documento, propietario, fecha_procesamiento,
                   fecha_pago, kg_expo_real, kg_nacional,
                   costo_total_expo, costo_total_nal, costo_total_desh, precio_nal, semana, anio
            FROM prosagro.kg_consolidado
            WHERE anio = %s AND semana = %s
              AND COALESCE(facturacion_electronica, 'No') = %s
              AND documento IS NOT NULL
            ORDER BY documento, fecha_procesamiento
            """,
            (anio, semana, fe_flag),
        )
        rows = cur.fetchall()

    for (traza, zona, doc, prop, fproc, fpago, kg_expo, kg_nal,
         c_expo, c_nal, c_desh, p_nal, sem, an) in rows:
        fruta = _fruta_de_zona(zona)
        articulo, bod_expo, bod_nal = ART[fruta]
        kg_expo = float(kg_expo or 0)
        c_expo = float(c_expo or 0); c_desh = float(c_desh or 0)
        # Fila exportación
        if c_expo > 0 and kg_expo > 0:
            precio_expo = round((c_expo + c_desh) / kg_expo, 2)
            filas.append({
                "tipo": tipo, "prefijo": "DSSE", "consecutivo": consec,
                "fecha_emision": fproc, "fecha_pago": fpago, "nit_tercero": doc,
                "fruta": fruta, "articulo_pya": articulo, "bodega_pya": bod_expo,
                "cantidad": round(kg_expo, 2), "precio_unitario": precio_expo,
                "valor_total": round(kg_expo * precio_expo, 2),
                "descripcion": f"SEM {sem} {an}", "centro_costo": "P3",
                "trazabilidad_ref": traza, "linea": "EXPORTACION",
            })
        # Fila nacional
        kg_nal = float(kg_nal or 0); c_nal = float(c_nal or 0)
        if c_nal > 0 and kg_nal > 0:
            filas.append({
                "tipo": tipo, "prefijo": "DSSE", "consecutivo": consec,
                "fecha_emision": fproc, "fecha_pago": fpago, "nit_tercero": doc,
                "fruta": fruta, "articulo_pya": articulo, "bodega_pya": bod_nal,
                "cantidad": round(kg_nal, 2), "precio_unitario": float(p_nal or 0),
                "valor_total": round(kg_nal * float(p_nal or 0), 2),
                "descripcion": f"SEM {sem} {an}", "centro_costo": "P3",
                "trazabilidad_ref": traza, "linea": "NACIONAL",
            })
        consec += 1
    return filas


def persistir_documentos(filas: list[dict]) -> int:
    """Guarda las filas en pya_documento_emitido (estado PENDIENTE)."""
    if not filas:
        return 0
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO prosagro.pya_documento_emitido
                (tipo, prefijo, consecutivo, fecha_emision, fecha_pago, nit_tercero,
                 fruta_codigo, articulo_pya, bodega_pya, cantidad, precio_unitario,
                 valor_total, descripcion, centro_costo, trazabilidad_ref,
                 moneda, estado)
            VALUES (%(tipo)s, %(prefijo)s, %(consecutivo)s, %(fecha_emision)s,
                    %(fecha_pago)s, %(nit_tercero)s,
                    CASE WHEN %(fruta)s='gulupa' THEN 'GUL' ELSE 'UCH' END,
                    %(articulo_pya)s, %(bodega_pya)s, %(cantidad)s, %(precio_unitario)s,
                    %(valor_total)s, %(descripcion)s, %(centro_costo)s,
                    %(trazabilidad_ref)s, 'COP', 'PENDIENTE')
            """,
            filas,
        )
        conn.commit()
    return len(filas)


def exportar_plano(filas: list[dict]) -> bytes:
    """CSV plano estilo SIIGO/PyA para carga manual mientras no esté la API."""
    out = io.StringIO()
    campos = ["tipo", "prefijo", "consecutivo", "fecha_emision", "fecha_pago",
              "nit_tercero", "articulo_pya", "bodega_pya", "cantidad",
              "precio_unitario", "valor_total", "descripcion", "centro_costo",
              "trazabilidad_ref", "linea"]
    w = csv.DictWriter(out, fieldnames=campos, extrasaction="ignore", delimiter=";")
    w.writeheader()
    for f in filas:
        r = dict(f)
        for k in ("fecha_emision", "fecha_pago"):
            if r.get(k):
                r[k] = r[k].strftime("%d/%m/%Y")
        w.writerow(r)
    return out.getvalue().encode("utf-8-sig")


def enviar_a_pya(filas: list[dict]) -> dict:
    """POST a la API de PyA si está configurada. Placeholder hasta credenciales."""
    if not os.environ.get("PYA_API_BASE"):
        return {"estado": "SIN_API", "msg": "PYA_API_BASE no configurado — usa exportar_plano()"}
    # TODO: implementar cuando lleguen credenciales/documentación de PyA.
    return {"estado": "PENDIENTE_IMPL", "msg": "API PyA aún no implementada"}
