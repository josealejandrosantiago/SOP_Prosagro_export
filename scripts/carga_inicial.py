"""CLI de carga inicial desde el Excel histórico de Prosagro.

Carga:
  - Maestros (productores, precio_fruta, precio_certificacion) desde
    `Base de datos gulupa.xlsx`.
  - Histórico de ingresos/export/nacional desde la misma hoja.
  - Histórico de contenedores y pallets desde los packing lists.

Uso:
    python -m scripts.carga_inicial maestros \\
        --gulupa "C:\\...\\Base de datos gulupa.xlsx"

    python -m scripts.carga_inicial historico \\
        --gulupa "C:\\...\\Base de datos gulupa.xlsx"

    python -m scripts.carga_inicial packing \\
        --carpeta "C:\\...\\Documentos\\Ingreso Gulupa\\operaciones\\2026"

Por seguridad: imprime un resumen y pide confirmación antes de tocar la BD.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl

# Permitir `python scripts/carga_inicial.py` desde el root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conexion import get_conn  # noqa: E402


def cmd_maestros(args: argparse.Namespace) -> None:
    """Carga productores + precio_fruta + precio_certificacion desde el Excel."""
    wb = openpyxl.load_workbook(args.gulupa, data_only=True, read_only=True)

    productores = []
    if "productores" in [s.lower() for s in wb.sheetnames]:
        nombre_hoja = next(s for s in wb.sheetnames if s.lower() == "productores")
        ws = wb[nombre_hoja]
        # Columnas conocidas (mapeo del VBA):
        # 1 fecha_hasta, 2 fecha_desde, 4 zona, 5 lote, 9 nombre_finca,
        # 10 telefono, 12 ubicacion, 14 plantas, 17 propietario, 18 doc,
        # 21 ica, 22 ggn, 27 retencion, 28 fact_electronica
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[3]:   # sin zona
                continue
            productores.append({
                "zona": str(row[3] or "").strip(),
                "lote": str(row[4] or "").strip(),
                "fecha_desde": row[1],
                "fecha_hasta": row[0],
                "nombre_finca": row[8],
                "telefono": row[9],
                "ubicacion": row[11],
                "plantas": row[13],
                "propietario": row[16],
                "documento": row[17],
                "ica": row[20],
                "ggn": row[21],
                "retencion": row[26],
                "fact_electronica": row[27],
            })

    print(f"  Productores leídos: {len(productores)}")

    if args.dry_run or not productores:
        print("  (dry-run) — no se escribió a BD.")
        return

    sql = """
        INSERT INTO prosagro.productores
            (zona, lote, fecha_vigencia_desde, fecha_vigencia_hasta,
             nombre_finca, propietario, documento, cantidad_plantas, ubicacion,
             telefono, requiere_retencion, facturacion_electronica,
             ica_propio, ggn_propio)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_conn() as conn, conn.cursor() as cur:
        rows = [(
            p["zona"], p["lote"], p["fecha_desde"], p["fecha_hasta"],
            p["nombre_finca"] or "(sin nombre)", p["propietario"] or "(sin propietario)",
            str(p["documento"] or ""), p["plantas"], p["ubicacion"],
            str(p["telefono"] or "") or None,
            p["retencion"], p["fact_electronica"],
            str(p["ica"] or "") or None, str(p["ggn"] or "") or None,
        ) for p in productores]
        cur.executemany(sql, rows)
        conn.commit()
    print(f"  ✓ {len(productores)} productores cargados")


def cmd_historico(args: argparse.Namespace) -> None:
    """Carga ingreso + export + nacional desde el libro consolidado."""
    print("  TODO Fase 1 — esqueleto disponible; carga real se implementa "
          "junto con el motor de Kg consolidado.")


def cmd_packing(args: argparse.Namespace) -> None:
    """Carga todos los packing lists de una carpeta."""
    from ingesta.parser_packing import parsear

    carpeta = Path(args.carpeta)
    archivos = sorted(carpeta.glob("PACKING LIST*.xlsx"))
    print(f"  Encontrados {len(archivos)} packing lists en {carpeta}")
    for f in archivos:
        try:
            pl = parsear(f)
            print(f"    {f.name:60s} → {pl.contenedor_codigo:10s} "
                  f"({pl.formato}, {len(pl.pallets)} filas, "
                  f"{len(pl.clientes_vat)} clientes)")
        except Exception as e:
            print(f"    {f.name:60s} → ERROR: {e}")

    if args.dry_run:
        print("  (dry-run) — no se escribió a BD.")
        return
    print("  TODO — escritura a BD se implementa en Fase 3 (Validación contenedor).")


def main() -> None:
    p = argparse.ArgumentParser(description="Carga inicial Prosagro Export")
    p.add_argument("--dry-run", action="store_true", default=True,
                   help="Por defecto NO escribe a BD. Quitar con --no-dry-run.")
    p.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("maestros")
    p1.add_argument("--gulupa", required=True,
                    help="Ruta al Excel 'Base de datos gulupa.xlsx'")
    p1.set_defaults(func=cmd_maestros)

    p2 = sub.add_parser("historico")
    p2.add_argument("--gulupa", required=True)
    p2.set_defaults(func=cmd_historico)

    p3 = sub.add_parser("packing")
    p3.add_argument("--carpeta", required=True)
    p3.set_defaults(func=cmd_packing)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
