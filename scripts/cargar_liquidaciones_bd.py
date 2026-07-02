"""Carga la hoja 'Liquidaciones BD' (Costos consolidados.xlsx) a:
  - distribucion_contenedor  (pallets asignados a cada cliente)
  - precio_estimado_venta    (precio estimado + fecha recogida)
  - precio_real_venta        (precio facturado/final + # invoice)

Estructura de la hoja (verificada):
  col1 Contenedor, col2 cliente, col3 Tipo negociación, col4 Pallets asignados
  ('1;5;6'), col5 Cajas ('300;300;300'), col6 Tipo de fruta, col7 Fecha recogida,
  col8 Precio estimado, col9 Precio facturado, col10 Precio final, col11 # ref,
  col12 # invoice, col13 Moneda, col14 Reclamación, col15 Observaciones.
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

import datetime as dt
import openpyxl

from conexion import get_conn

COSTOS = (
    r"C:\Users\LENOVO\OneDrive - Grupo San Jose\Automatización Prosagro Export - "
    r"Base de Datos Prosagro Export 1\01. Prosagro Export\01. Entrada De Datos\Costos consolidados.xlsx"
)


def _s(v):
    return None if v in (None, "") else str(v).strip()


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fecha(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.date() if isinstance(v, dt.datetime) else v
    return None


def _split(v):
    return [x.strip() for x in str(v or "").split(";") if x.strip()]


def cargar():
    wb = openpyxl.load_workbook(COSTOS, data_only=True, read_only=True)
    ws = wb["Liquidaciones BD"]

    with get_conn() as conn, conn.cursor() as cur:
        # Mapas de resolución
        cur.execute("SELECT id, codigo FROM prosagro.contenedores")
        cont_map = {cod: cid for cid, cod in cur.fetchall()}
        cur.execute("SELECT id, UPPER(nombre) FROM prosagro.clientes")
        cli_map = {nom: cid for cid, nom in cur.fetchall()}

        # Limpiar cargas previas (idempotente)
        cur.execute("TRUNCATE prosagro.distribucion_contenedor RESTART IDENTITY")
        cur.execute("TRUNCATE prosagro.precio_estimado_venta RESTART IDENTITY")
        cur.execute("TRUNCATE prosagro.precio_real_venta RESTART IDENTITY")

        n_dist = n_est = n_real = 0
        cli_faltantes = set()
        cont_faltantes = set()

        for row in ws.iter_rows(min_row=2, values_only=True):
            cont_cod = _s(row[0])
            cli_nom = _s(row[1])
            if not cont_cod or not cli_nom:
                continue
            cont_id = cont_map.get(cont_cod)
            if not cont_id:
                cont_faltantes.add(cont_cod)
                continue
            cli_id = cli_map.get(cli_nom.upper())
            if not cli_id:
                # crear cliente al vuelo
                cur.execute(
                    "INSERT INTO prosagro.clientes (nombre, activo) VALUES (%s, TRUE) RETURNING id",
                    (cli_nom,),
                )
                cli_id = cur.fetchone()[0]
                cli_map[cli_nom.upper()] = cli_id
                cli_faltantes.add(cli_nom)

            tipo_neg = _s(row[2])
            pallets = _split(row[3])
            cajas_list = _split(row[4])
            fecha_recogida = _fecha(row[6])
            precio_est = _num(row[7])
            precio_fact = _num(row[8])
            precio_final = _num(row[9])
            referencia = _s(row[10])
            invoice = _s(row[11])
            moneda = (_s(row[12]) or "USD").upper()
            if moneda in ("EURO", "EUROS"):
                moneda = "EUR"
            elif moneda in ("DOLAR", "DOLARES", "USD$"):
                moneda = "USD"
            elif moneda in ("PESOS", "COP$"):
                moneda = "COP"
            if moneda not in ("USD", "EUR", "COP"):
                moneda = "USD"

            # Distribución: una fila por pallet
            for idx, p in enumerate(pallets):
                try:
                    p_int = int(p)
                except ValueError:
                    continue
                # buscar el pallet_id si existe (packing list cargado); si no, NULL
                cur.execute(
                    "SELECT id FROM prosagro.pallets_contenedor WHERE contenedor_id=%s AND no_pallet=%s",
                    (cont_id, p_int),
                )
                pr = cur.fetchone()
                if not pr:
                    # crear el pallet mínimo para poder distribuirlo
                    cur.execute(
                        """INSERT INTO prosagro.pallets_contenedor (contenedor_id, no_pallet, total_cajas)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (contenedor_id, no_pallet) DO UPDATE SET total_cajas=EXCLUDED.total_cajas
                           RETURNING id""",
                        (cont_id, p_int, int(float(cajas_list[idx])) if idx < len(cajas_list) else 0),
                    )
                    pallet_id = cur.fetchone()[0]
                else:
                    pallet_id = pr[0]
                cur.execute(
                    """INSERT INTO prosagro.distribucion_contenedor
                        (contenedor_id, pallet_id, cliente_id, tipo_negociacion)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT (contenedor_id, pallet_id) DO NOTHING""",
                    (cont_id, pallet_id, cli_id, tipo_neg),
                )
                n_dist += 1

            total_cajas = sum(int(float(x)) for x in cajas_list if x.replace(".", "").isdigit())

            # Precio estimado
            if precio_est:
                cur.execute(
                    """INSERT INTO prosagro.precio_estimado_venta
                        (contenedor_id, cliente_id, precio_estimado, moneda, cajas,
                         fecha_recogida_estimada, observaciones)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (cont_id, cli_id, precio_est, moneda, total_cajas, fecha_recogida,
                     _s(row[14])),
                )
                n_est += 1
            # Precio real
            precio_r = precio_final or precio_fact
            if precio_r:
                cur.execute(
                    """INSERT INTO prosagro.precio_real_venta
                        (contenedor_id, cliente_id, tipo_documento, consecutivo_ne,
                         cajas, precio_unitario, moneda, fecha_recogida_real, observaciones)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (cont_id, cli_id, "FV", invoice, total_cajas, precio_r, moneda,
                     fecha_recogida, referencia),
                )
                n_real += 1

        conn.commit()
    wb.close()
    return {
        "distribucion": n_dist, "precio_estimado": n_est, "precio_real": n_real,
        "clientes_creados": len(cli_faltantes), "contenedores_no_encontrados": sorted(cont_faltantes)[:10],
    }


if __name__ == "__main__":
    r = cargar()
    print(f"Distribución: {r['distribucion']} pallets")
    print(f"Precio estimado: {r['precio_estimado']} filas")
    print(f"Precio real: {r['precio_real']} filas")
    print(f"Clientes creados al vuelo: {r['clientes_creados']}")
    if r["contenedores_no_encontrados"]:
        print(f"Contenedores no encontrados (muestra): {r['contenedores_no_encontrados']}")
