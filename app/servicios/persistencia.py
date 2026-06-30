"""Persistencia del parser output a la BD prosagro.

`persistir_informe` se encarga de:
  - Hacer UPSERT por trazabilidad sobre `ingresos`.
  - Reemplazar (DELETE + INSERT) las filas de `fruta_export` y `fruta_nacional`
    asociadas a las trazabilidades del informe — así reprocesar el mismo
    Excel deja la BD igual que la primera carga.
  - Todo en una sola transacción para no dejar inconsistencias.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from conexion import get_conn

if TYPE_CHECKING:
    from ingesta.parser_maquila import InformeMaquila


def persistir_informe(
    informe: "InformeMaquila",
    flags_export: dict[str, bool],
    user: dict | None = None,
) -> dict:
    """Inserta/actualiza el informe completo y devuelve un resumen.

    flags_export: dict trazabilidad → bool (True = fruta de exportación).
    user: dict del usuario logueado (id, email, nombre, rol) — para audit.
    """
    nuevos = 0
    actualizados = 0

    with get_conn() as conn, conn.cursor() as cur:
        # 1) Upsert ingresos
        for i in informe.ingresos:
            fe_flag = bool(flags_export.get(i.trazabilidad, True))
            cur.execute(
                """
                INSERT INTO prosagro.ingresos
                    (trazabilidad, semana, anio, fecha_ingreso, no_cargue, zona, lote,
                     consec_int, canastillas, peso_neto, conductor, placa, finaliza,
                     fruta_export_flag)
                VALUES (%(traz)s, %(semana)s, %(anio)s, %(fecha)s, %(carg)s, %(zona)s,
                        %(lote)s, %(consec)s, %(canast)s, %(peso)s, %(cond)s, %(placa)s,
                        %(finaliza)s, %(fe)s)
                ON CONFLICT (trazabilidad) DO UPDATE
                    SET fruta_export_flag = EXCLUDED.fruta_export_flag,
                        canastillas       = EXCLUDED.canastillas,
                        peso_neto         = EXCLUDED.peso_neto,
                        conductor         = EXCLUDED.conductor,
                        placa             = EXCLUDED.placa,
                        actualizado_en    = now()
                RETURNING (xmax = 0) AS inserted
                """,
                {
                    "traz": i.trazabilidad,
                    "semana": i.semana,
                    "anio": i.anio,
                    "fecha": i.fecha_ingreso,
                    "carg": i.no_cargue,
                    "zona": i.zona,
                    "lote": i.lote,
                    "consec": i.consec_int,
                    "canast": i.canastillas,
                    "peso": i.peso_neto,
                    "cond": i.conductor,
                    "placa": i.placa,
                    "finaliza": i.finaliza,
                    "fe": fe_flag,
                },
            )
            inserted = cur.fetchone()[0]
            if inserted:
                nuevos += 1
            else:
                actualizados += 1

        # 2) Resolver trazabilidad → ingreso_id
        trazas = [i.trazabilidad for i in informe.ingresos]
        cur.execute(
            "SELECT trazabilidad, id FROM prosagro.ingresos WHERE trazabilidad = ANY(%s)",
            (trazas,),
        )
        traz_to_id: dict[str, int] = dict(cur.fetchall())

        # 3) Limpiar export/nacional anteriores de esas trazas
        ids = list(traz_to_id.values())
        if ids:
            cur.execute(
                "DELETE FROM prosagro.fruta_export WHERE ingreso_id = ANY(%s)", (ids,)
            )
            cur.execute(
                "DELETE FROM prosagro.fruta_nacional WHERE ingreso_id = ANY(%s)", (ids,)
            )

        # 4) Insert fruta_export
        if informe.export:
            cur.executemany(
                """
                INSERT INTO prosagro.fruta_export
                    (ingreso_id, trazabilidad, semana, anio, dia_sem, fecha_ingreso,
                     fecha_procesamiento, no_cargue, presentacion_caja, calibre_desc,
                     calibre_num, id_calibre, cant_cajas, total_kg_netos,
                     productor_nombre, producto, ica, ggn, predio, categoria)
                VALUES (%(iid)s, %(traz)s, %(semana)s, %(anio)s, %(dia)s, %(fi)s,
                        %(fp)s, %(no)s, %(pres)s, %(cdesc)s, %(cnum)s, %(idc)s,
                        %(cantc)s, %(kg)s, %(pn)s, %(prod)s, %(ica)s, %(ggn)s,
                        %(pre)s, %(cat)s)
                """,
                [
                    {
                        "iid": traz_to_id[f.trazabilidad],
                        "traz": f.trazabilidad,
                        "semana": f.semana,
                        "anio": f.anio,
                        "dia": f.dia_sem,
                        "fi": f.fecha_ingreso,
                        "fp": f.fecha_procesamiento,
                        "no": f.no_cargue,
                        "pres": f.presentacion_caja,
                        "cdesc": f.calibre_desc,
                        "cnum": f.calibre_num,
                        "idc": f.id_calibre,
                        "cantc": f.cant_cajas,
                        "kg": f.total_kg_netos,
                        "pn": f.productor_nombre,
                        "prod": f.producto,
                        "ica": f.ica,
                        "ggn": f.ggn,
                        "pre": f.predio,
                        "cat": f.categoria,
                    }
                    for f in informe.export
                    if f.trazabilidad in traz_to_id
                ],
            )

        # 5) Insert fruta_nacional
        if informe.nacional:
            cur.executemany(
                """
                INSERT INTO prosagro.fruta_nacional
                    (ingreso_id, trazabilidad, semana, anio, dia_sem, fecha_ingreso,
                     fecha_procesamiento, no_cargue, lote_proceso, merma,
                     cant_kilos_descarte, simulacion_kg)
                VALUES (%(iid)s, %(traz)s, %(semana)s, %(anio)s, %(dia)s, %(fi)s,
                        %(fp)s, %(no)s, %(lp)s, %(me)s, %(des)s, %(sim)s)
                """,
                [
                    {
                        "iid": traz_to_id[f.trazabilidad],
                        "traz": f.trazabilidad,
                        "semana": f.semana,
                        "anio": f.anio,
                        "dia": f.dia_sem,
                        "fi": f.fecha_ingreso,
                        "fp": f.fecha_procesamiento,
                        "no": f.no_cargue,
                        "lp": f.lote_proceso,
                        "me": f.merma,
                        "des": f.cant_kilos_descarte,
                        "sim": f.simulacion_kg,
                    }
                    for f in informe.nacional
                    if f.trazabilidad in traz_to_id
                ],
            )

        conn.commit()

    return {
        "ingresos": len(informe.ingresos),
        "export": len(informe.export),
        "nacional": len(informe.nacional),
        "nuevos": nuevos,
        "actualizados": actualizados,
    }


def semanas_cargadas() -> list[dict]:
    """Devuelve resumen de semanas ya cargadas (para la pantalla inicial)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT i.anio,
                   i.semana,
                   COUNT(*)                                          AS ingresos,
                   COUNT(*) FILTER (WHERE i.fruta_export_flag)       AS export_flag,
                   COALESCE(SUM(i.peso_neto), 0)                     AS peso_total,
                   MIN(i.fecha_ingreso)                              AS desde,
                   MAX(i.fecha_ingreso)                              AS hasta
            FROM prosagro.ingresos i
            GROUP BY i.anio, i.semana
            ORDER BY i.anio DESC, i.semana DESC
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def eliminar_semana(anio: int, semana: int) -> int:
    """Borra todas las trazas de la semana (CASCADE limpia export/nacional/kg_consolidado)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM prosagro.kg_consolidado
            WHERE anio = %s AND semana = %s
            """,
            (anio, semana),
        )
        cur.execute(
            """
            DELETE FROM prosagro.ingresos
            WHERE anio = %s AND semana = %s
            """,
            (anio, semana),
        )
        n = cur.rowcount
        conn.commit()
    return n
