"""Motor de contenedores — carga packing list y cruza con fruta_export.

Replica `frmInicio.CommandButton20` del VBA con el mismo algoritmo:
  Para cada fila de fruta_export sin contenedor asignado (con fecha de proceso
  en el mes/año del contenedor o el mes anterior), busca en `pallets_detalle`
  un pallet con mismo no_cargue y calibre. Si el match existe:
    - cant_cajas_export > cajas_pallet → divide la fila de fruta_export:
        la original toma cajas_pallet (queda cuadrada con el pallet),
        crea una nueva con el saldo para seguir cruzando.
    - cant_cajas_export = cajas_pallet → cruce directo.
  En ambos casos:
    - actualiza contenedor, pallet, predio, ICA, GGN en fruta_export
    - marca el pallet como 'CRUZADO'.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from conexion import get_conn
from ingesta.parser_packing import parsear as parsear_packing

if TYPE_CHECKING:
    from ingesta.parser_packing import PackingList

CONT_RE = re.compile(r"OP-?(\d+)", re.IGNORECASE)


# ───────────────────────── Carga del packing list a BD ──────────────────────
def cargar_packing_list(ruta: str | Path) -> dict:
    """Parsea el xlsx y persiste el contenedor + pallets + detalles a BD.

    Idempotente: si el contenedor ya existe lo actualiza; pallets/detalles los
    reemplaza (DELETE + INSERT) para que reprocesar el mismo archivo no
    duplique.
    """
    pl = parsear_packing(ruta)
    if not pl.contenedor_codigo:
        raise ValueError(f"El archivo {ruta} no tiene contenedor_codigo")

    archivo_nombre = Path(ruta).name

    with get_conn() as conn, conn.cursor() as cur:
        # Upsert contenedor
        cur.execute(
            """
            INSERT INTO prosagro.contenedores
                (codigo, warehouse, fecha_inicio, fecha_cargue, eta,
                 total_pallets, total_cajas, observaciones)
            VALUES (%(c)s, %(wh)s, %(fi)s, %(fc)s, %(eta)s, %(tp)s, %(tc)s, %(obs)s)
            ON CONFLICT (codigo) DO UPDATE
                SET warehouse      = COALESCE(EXCLUDED.warehouse,      contenedores.warehouse),
                    fecha_inicio   = COALESCE(EXCLUDED.fecha_inicio,   contenedores.fecha_inicio),
                    fecha_cargue   = COALESCE(EXCLUDED.fecha_cargue,   contenedores.fecha_cargue),
                    eta            = COALESCE(EXCLUDED.eta,            contenedores.eta),
                    total_pallets  = COALESCE(EXCLUDED.total_pallets,  contenedores.total_pallets),
                    total_cajas    = COALESCE(EXCLUDED.total_cajas,    contenedores.total_cajas),
                    actualizado_en = now()
            RETURNING id
            """,
            {
                "c": pl.contenedor_codigo,
                "wh": pl.warehouse,
                "fi": pl.fecha,
                "fc": pl.fecha,
                "eta": pl.eta,
                "tp": pl.total_pallets or 0,
                "tc": pl.total_cajas or 0,
                "obs": f"Cargado desde {archivo_nombre}",
            },
        )
        contenedor_id = cur.fetchone()[0]

        # Limpiar pallets + detalles anteriores (reproceso limpio)
        cur.execute(
            "DELETE FROM prosagro.pallets_detalle  WHERE contenedor_id = %s",
            (contenedor_id,),
        )
        cur.execute(
            "DELETE FROM prosagro.pallets_contenedor WHERE contenedor_id = %s",
            (contenedor_id,),
        )

        # Agrupar por no_pallet para crear pallets_contenedor
        pallets_distintos: dict[int, dict] = {}
        for det in pl.pallets:
            if det.no_pallet not in pallets_distintos:
                pallets_distintos[det.no_pallet] = {
                    "no_pallet": det.no_pallet,
                    "presentacion": det.presentacion_caja,
                    "calibre_dominante": det.calibre,
                    "total_cajas": det.total_cajas_pallet or 0,
                    "certificado_grasp": det.certificado_grasp,
                }
            elif (
                det.total_cajas_pallet
                and not pallets_distintos[det.no_pallet]["total_cajas"]
            ):
                pallets_distintos[det.no_pallet]["total_cajas"] = det.total_cajas_pallet

        pallet_ids: dict[int, int] = {}
        for no_p, info in sorted(pallets_distintos.items()):
            cur.execute(
                """
                INSERT INTO prosagro.pallets_contenedor
                    (contenedor_id, no_pallet, presentacion, calibre_dominante,
                     total_cajas, certificado_grasp)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    contenedor_id,
                    info["no_pallet"],
                    info["presentacion"],
                    info["calibre_dominante"],
                    info["total_cajas"],
                    info["certificado_grasp"],
                ),
            )
            pallet_ids[no_p] = cur.fetchone()[0]

        # Insertar pallets_detalle (una fila por línea del packing list)
        for det in pl.pallets:
            cur.execute(
                """
                INSERT INTO prosagro.pallets_detalle
                    (contenedor_id, pallet_id, predio, ica, ggn, no_cargue,
                     cajas, calibre, archivo_origen, estado_cruce)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE')
                """,
                (
                    contenedor_id,
                    pallet_ids[det.no_pallet],
                    det.predio,
                    det.ica,
                    det.ggn,
                    det.no_cargue,
                    det.cajas,
                    det.calibre,
                    archivo_nombre,
                ),
            )

        conn.commit()

    return {
        "contenedor_id":  contenedor_id,
        "contenedor":     pl.contenedor_codigo,
        "pallets":        len(pallets_distintos),
        "detalle_filas":  len(pl.pallets),
        "total_cajas":    pl.total_cajas,
        "warehouse":      pl.warehouse,
    }


# ───────────────────────── Cruce con fruta_export ───────────────────────────
def cruzar_contenedor(
    codigo: str,
    permitir_mes_anterior: bool = True,
) -> dict:
    """Replica CommandButton20: cruza pallets del contenedor con fruta_export.

    Algoritmo:
      1. Toma todas las filas de pallets_detalle del contenedor con estado_cruce='PENDIENTE'.
      2. Para cada fila de pallets_detalle, busca filas de fruta_export que:
         - tengan el mismo no_cargue
         - tengan el mismo calibre_num
         - contenedor_codigo IS NULL (aún no asignado)
         - fecha_procesamiento esté en el mismo mes/año del contenedor o el mes anterior
      3. Si cant_cajas_export > cajas_pallet:
           - duplica la fila de fruta_export
           - una toma las cajas del pallet y el cruce
           - la otra queda con el saldo (cant_cajas_export - cajas_pallet)
         Si iguales → cruce directo en la misma fila.
      4. Marca pallets_detalle.estado_cruce='CRUZADO' y fruta_export.estado_cruce='CRUZADO'.
    """
    warnings_acc: Counter[str] = Counter()
    cruces = 0
    divisiones = 0
    pallets_cruzados = 0
    pallets_sin_match = 0

    with get_conn() as conn, conn.cursor() as cur:
        # Datos del contenedor
        cur.execute(
            """
            SELECT id, codigo, fecha_cargue, fecha_inicio
            FROM prosagro.contenedores WHERE codigo = %s
            """,
            (codigo,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Contenedor {codigo} no existe en BD")
        contenedor_id, codigo, fecha_cargue, fecha_inicio = row
        ref_fecha = fecha_cargue or fecha_inicio or dt.date.today()

        # Mes/año esperado del cargue
        mes_objetivo = ref_fecha.month
        anio_objetivo = ref_fecha.year
        # Mes anterior (si permitido)
        if mes_objetivo == 1:
            mes_anterior, anio_anterior = 12, anio_objetivo - 1
        else:
            mes_anterior, anio_anterior = mes_objetivo - 1, anio_objetivo

        # Pallets pendientes
        cur.execute(
            """
            SELECT id, no_cargue, calibre, cajas, predio, ica, ggn, pallet_id
            FROM prosagro.pallets_detalle
            WHERE contenedor_id = %s AND estado_cruce = 'PENDIENTE'
            ORDER BY pallet_id, id
            """,
            (contenedor_id,),
        )
        pendientes = cur.fetchall()

        for det_id, no_cargue, calibre, cajas_pallet, predio, ica, ggn, pallet_id in pendientes:
            cajas_pallet = float(cajas_pallet or 0)
            if cajas_pallet <= 0:
                continue

            calibre_norm = (calibre or "").strip()
            # Buscar candidatos en fruta_export
            where_fecha = "AND EXTRACT(MONTH FROM e.fecha_procesamiento) = %s AND EXTRACT(YEAR FROM e.fecha_procesamiento) = %s"
            params_fecha = [mes_objetivo, anio_objetivo]
            if permitir_mes_anterior:
                where_fecha = (
                    "AND ((EXTRACT(MONTH FROM e.fecha_procesamiento) = %s AND EXTRACT(YEAR FROM e.fecha_procesamiento) = %s) "
                    "OR  (EXTRACT(MONTH FROM e.fecha_procesamiento) = %s AND EXTRACT(YEAR FROM e.fecha_procesamiento) = %s))"
                )
                params_fecha = [mes_objetivo, anio_objetivo, mes_anterior, anio_anterior]

            cur.execute(
                f"""
                SELECT e.id, e.cant_cajas, e.total_kg_netos
                FROM prosagro.fruta_export e
                WHERE e.no_cargue = %s
                  AND TRIM(COALESCE(e.calibre_num, '')) = %s
                  AND e.contenedor_codigo IS NULL
                  {where_fecha}
                ORDER BY e.id
                LIMIT 1
                """,
                [no_cargue, calibre_norm, *params_fecha],
            )
            candidato = cur.fetchone()
            if not candidato:
                pallets_sin_match += 1
                warnings_acc[f"sin match no_cargue={no_cargue} calibre={calibre_norm}"] += 1
                continue

            exp_id, cant_cajas_exp, total_kg_exp = candidato
            cant_cajas_exp = float(cant_cajas_exp or 0)
            total_kg_exp = float(total_kg_exp or 0)
            kg_por_caja = (total_kg_exp / cant_cajas_exp) if cant_cajas_exp > 0 else 0

            if cant_cajas_exp > cajas_pallet:
                # Dividir fila: la original toma cajas_pallet, una nueva queda con el saldo
                divisiones += 1
                saldo_cajas = cant_cajas_exp - cajas_pallet
                saldo_kg = saldo_cajas * kg_por_caja

                # Copiar fila completa a una nueva
                cur.execute(
                    """
                    INSERT INTO prosagro.fruta_export
                        (ingreso_id, trazabilidad, semana, anio, dia_sem, fecha_ingreso,
                         fecha_procesamiento, no_cargue, presentacion_caja, calibre_desc,
                         calibre_num, id_calibre, cant_cajas, total_kg_netos,
                         productor_nombre, producto, ica, ggn, predio, categoria,
                         estado_cruce)
                    SELECT ingreso_id, trazabilidad, semana, anio, dia_sem, fecha_ingreso,
                           fecha_procesamiento, no_cargue, presentacion_caja, calibre_desc,
                           calibre_num, id_calibre, %s, %s,
                           productor_nombre, producto, ica, ggn, predio, categoria,
                           'PENDIENTE'
                    FROM prosagro.fruta_export
                    WHERE id = %s
                    """,
                    (saldo_cajas, saldo_kg, exp_id),
                )

                # La original ahora cuadra con el pallet
                cur.execute(
                    """
                    UPDATE prosagro.fruta_export
                       SET cant_cajas        = %s,
                           total_kg_netos    = %s,
                           contenedor_codigo = %s,
                           pallet_no         = (SELECT no_pallet FROM prosagro.pallets_contenedor WHERE id = %s),
                           predio            = COALESCE(%s, predio),
                           ica               = COALESCE(%s, ica),
                           ggn               = COALESCE(%s, ggn),
                           armado_completo   = 'Completo',
                           estado_cruce      = 'CRUZADO',
                           actualizado_en    = now()
                     WHERE id = %s
                    """,
                    (
                        cajas_pallet,
                        cajas_pallet * kg_por_caja,
                        codigo,
                        pallet_id,
                        predio,
                        ica,
                        ggn,
                        exp_id,
                    ),
                )
            else:
                # Cruce directo (iguales o cajas_exp < cajas_pallet — caso raro)
                cur.execute(
                    """
                    UPDATE prosagro.fruta_export
                       SET contenedor_codigo = %s,
                           pallet_no         = (SELECT no_pallet FROM prosagro.pallets_contenedor WHERE id = %s),
                           predio            = COALESCE(%s, predio),
                           ica               = COALESCE(%s, ica),
                           ggn               = COALESCE(%s, ggn),
                           armado_completo   = 'Completo',
                           estado_cruce      = 'CRUZADO',
                           actualizado_en    = now()
                     WHERE id = %s
                    """,
                    (codigo, pallet_id, predio, ica, ggn, exp_id),
                )

            # Marcar pallet detalle como cruzado
            cur.execute(
                """
                UPDATE prosagro.pallets_detalle
                   SET estado_cruce    = 'CRUZADO',
                       fruta_export_id = %s,
                       actualizado_en  = now()
                 WHERE id = %s
                """,
                (exp_id, det_id),
            )
            cruces += 1
            pallets_cruzados += 1

        # Marcar contenedor como armado_completo si todos los pallets están cruzados
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE estado_cruce = 'CRUZADO'),
                COUNT(*)
            FROM prosagro.pallets_detalle
            WHERE contenedor_id = %s
            """,
            (contenedor_id,),
        )
        cruzados, total = cur.fetchone()
        if total > 0 and cruzados == total:
            cur.execute(
                """
                UPDATE prosagro.contenedores
                   SET armado_completo = TRUE, actualizado_en = now()
                 WHERE id = %s
                """,
                (contenedor_id,),
            )

        conn.commit()

    return {
        "contenedor":       codigo,
        "pallets_cruzados": pallets_cruzados,
        "pallets_sin_match": pallets_sin_match,
        "cruces":            cruces,
        "filas_divididas":   divisiones,
        "warnings":          dict(warnings_acc),
    }


def resumen_contenedor(codigo: str) -> dict:
    """Devuelve totales después del cruce."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.codigo,
                c.armado_completo,
                c.total_pallets,
                c.total_cajas,
                COUNT(DISTINCT pd.id) AS detalle_filas,
                COUNT(DISTINCT pd.id) FILTER (WHERE pd.estado_cruce = 'CRUZADO') AS detalle_cruzadas,
                COUNT(DISTINCT pc.id) AS pallets_total,
                (SELECT COUNT(*) FROM prosagro.fruta_export e WHERE e.contenedor_codigo = c.codigo) AS filas_export,
                (SELECT COALESCE(SUM(cant_cajas), 0) FROM prosagro.fruta_export e WHERE e.contenedor_codigo = c.codigo) AS cajas_export,
                (SELECT COALESCE(SUM(total_kg_netos), 0) FROM prosagro.fruta_export e WHERE e.contenedor_codigo = c.codigo) AS kg_export
            FROM prosagro.contenedores c
            LEFT JOIN prosagro.pallets_contenedor pc ON pc.contenedor_id = c.id
            LEFT JOIN prosagro.pallets_detalle    pd ON pd.contenedor_id = c.id
            WHERE c.codigo = %s
            GROUP BY c.codigo, c.armado_completo, c.total_pallets, c.total_cajas
            """,
            (codigo,),
        )
        r = cur.fetchone()
    if not r:
        return {}
    return {
        "codigo":           r[0],
        "armado_completo":  r[1],
        "total_pallets":    r[2],
        "total_cajas":      r[3],
        "detalle_filas":    r[4],
        "detalle_cruzadas": r[5],
        "pallets_total":    r[6],
        "filas_export":     r[7],
        "cajas_export":     float(r[8] or 0),
        "kg_export":        float(r[9] or 0),
    }
