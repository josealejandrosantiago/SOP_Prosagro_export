"""Motor SOP — reconstruye `kg_consolidado` a partir de ingresos/export/nacional
+ maestros (productores, precio_fruta, calendario_pagos).

Replica la lógica del VBA `frmInicio.CommandButton1_Click` con dos diferencias
intencionales:
  1. `costo_total_ggn` y `costo_total_ica` se guardan separados (corrige el bug
     de `frmGGN` que los sobre-escribía).
  2. Si una fila de fruta_export tiene categoria='AJUSTE' (calibre N/A en el
     Excel original), el kg se compensa automáticamente en fruta nacional —
     no requiere que el operador lo restará manualmente.

El motor es IDEMPOTENTE: usa UPSERT sobre `kg_consolidado.trazabilidad`.

Parámetros configurables (defaults razonables para arrancar):
  - umbral_retefuente: base mínima para causar retención. Default 1_000_000 COP
    (≈27 UVT 2026; el VBA leía `Hoja1.Cells(1, 9)`).
  - tasa_retefuente: 1.5% por defecto.
  - tasa_ashofrucol: 1% por defecto.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from conexion import get_conn

UMBRAL_RETEFUENTE_DEFAULT = 1_000_000   # COP
TASA_RETEFUENTE          = 0.015
TASA_ASHOFRUCOL          = 0.01


def reconstruir_kg_consolidado(
    anio: int | None = None,
    semana: int | None = None,
    umbral_retefuente: float = UMBRAL_RETEFUENTE_DEFAULT,
) -> dict:
    """Recalcula kg_consolidado para (anio, semana) o para todo si son None.

    Devuelve dict con conteos y warnings agrupados.
    """
    warnings_acc: Counter[str] = Counter()
    procesadas = 0

    with get_conn() as conn, conn.cursor() as cur:
        where = "WHERE 1=1"
        params: list = []
        if anio is not None:
            where += " AND i.anio = %s"
            params.append(anio)
        if semana is not None:
            where += " AND i.semana = %s"
            params.append(semana)

        cur.execute(
            f"""
            SELECT i.id, i.trazabilidad, i.zona, i.lote, i.fecha_ingreso, i.semana,
                   i.anio, i.no_cargue, i.canastillas, i.peso_neto, i.fruta_export_flag
            FROM prosagro.ingresos i
            {where}
            ORDER BY i.fecha_ingreso, i.no_cargue
            """,
            params,
        )
        ingresos = cur.fetchall()

        for (
            ing_id,
            traza,
            zona,
            lote,
            fecha,
            semana_i,
            anio_i,
            no_cargue,
            canast,
            peso_total,
            fe_flag,
        ) in ingresos:
            peso_total = float(peso_total or 0)
            canast = int(canast or 0)

            # 1) Agregados fruta_export
            cur.execute(
                """
                SELECT categoria,
                       COALESCE(SUM(total_kg_netos), 0)::FLOAT AS kg,
                       MAX(fecha_procesamiento)
                FROM prosagro.fruta_export
                WHERE ingreso_id = %s
                GROUP BY categoria
                """,
                (ing_id,),
            )
            kg_C1 = 0.0
            kg_AJUSTE = 0.0
            kg_C2 = 0.0
            fecha_proc = fecha
            for cat, kg, fp in cur.fetchall():
                if cat == "C1":
                    kg_C1 += kg
                elif cat == "AJUSTE":
                    kg_AJUSTE += kg
                elif cat == "C2":
                    kg_C2 += kg
                if fp:
                    fecha_proc = fp

            # Predio / GGN / ICA: del max() de fruta_export (suelen ser homogéneos por traza)
            cur.execute(
                """
                SELECT predio, ica, ggn, productor_nombre
                FROM prosagro.fruta_export
                WHERE ingreso_id = %s
                ORDER BY total_kg_netos DESC NULLS LAST
                LIMIT 1
                """,
                (ing_id,),
            )
            row_pic = cur.fetchone()
            predio, ica_traza, ggn_traza, productor_nombre_traza = (
                row_pic if row_pic else (None, None, None, None)
            )

            # 2) Agregados fruta_nacional
            cur.execute(
                """
                SELECT COALESCE(SUM(merma), 0)::FLOAT,
                       COALESCE(SUM(cant_kilos_descarte), 0)::FLOAT,
                       COALESCE(SUM(simulacion_kg), 0)::FLOAT
                FROM prosagro.fruta_nacional
                WHERE ingreso_id = %s
                """,
                (ing_id,),
            )
            row_n = cur.fetchone() or (0.0, 0.0, 0.0)
            _merma_decl, descarte, simulacion = row_n

            # 3) Balance final
            kg_expo_real = kg_C1
            kg_expo_ajustado = kg_AJUSTE
            # La fruta C2 + simulación van a nacional. Los AJUSTE compensan kg
            # contrario en nacional (regla "manual" de la macro → automática).
            kg_nacional = descarte + simulacion + kg_C2 - kg_AJUSTE
            kg_merma = peso_total - kg_expo_real - kg_nacional

            # 4) Productor vigente por (zona, lote, fecha_ingreso)
            cur.execute(
                """
                SELECT id, nombre_finca, propietario, documento, cantidad_plantas,
                       ubicacion, telefono, requiere_retencion, facturacion_electronica
                FROM prosagro.productores
                WHERE zona = %s AND lote = %s
                  AND fecha_vigencia_desde <= %s
                  AND (fecha_vigencia_hasta IS NULL OR fecha_vigencia_hasta >= %s)
                ORDER BY fecha_vigencia_desde DESC
                LIMIT 1
                """,
                (zona, lote, fecha, fecha),
            )
            prod = cur.fetchone()
            if prod:
                (
                    _pid,
                    finca,
                    propietario,
                    doc,
                    plantas,
                    ubicacion,
                    telefono,
                    requiere_ret,
                    fact_elec,
                ) = prod
            else:
                warnings_acc[f"sin productor vigente zona={zona} lote={lote}"] += 1
                finca = propietario = doc = ubicacion = telefono = None
                requiere_ret = fact_elec = None
                plantas = None

            # 5) Precio vigente por (zona, lote, fecha_proc)
            cur.execute(
                """
                SELECT precio_expo, precio_nal, precio_desh, dias_pago
                FROM prosagro.precio_fruta
                WHERE zona = %s AND lote = %s
                  AND fecha_vigencia_desde <= %s
                  AND (fecha_vigencia_hasta IS NULL OR fecha_vigencia_hasta >= %s)
                ORDER BY fecha_vigencia_desde DESC
                LIMIT 1
                """,
                (zona, lote, fecha_proc, fecha_proc),
            )
            precio = cur.fetchone()
            if precio:
                p_expo, p_nal, p_desh, dias_pago = precio
                p_expo = float(p_expo or 0)
                p_nal = float(p_nal or 0)
                p_desh = float(p_desh or 0)
                dias_pago = int(dias_pago or 0)
            else:
                warnings_acc[f"sin precio vigente zona={zona} lote={lote}"] += 1
                p_expo = p_nal = p_desh = 0.0
                dias_pago = 0

            # 6) Costos
            costo_expo = kg_expo_real * p_expo
            costo_nal = kg_nacional * p_nal
            costo_desh = max(kg_merma, 0.0) * p_desh
            ashofrucol = (costo_expo + costo_nal + costo_desh) * TASA_ASHOFRUCOL

            # 7) Certificación (GGN+ICA) — separados
            cur.execute(
                """
                SELECT precio_ggn, precio_ica
                FROM prosagro.precio_certificacion
                WHERE zona = %s AND lote = %s
                  AND fecha_vigencia_desde <= %s
                  AND (fecha_vigencia_hasta IS NULL OR fecha_vigencia_hasta >= %s)
                ORDER BY fecha_vigencia_desde DESC
                LIMIT 1
                """,
                (zona, lote, fecha_proc, fecha_proc),
            )
            cert = cur.fetchone()
            if cert:
                pre_ggn, pre_ica = (float(cert[0] or 0), float(cert[1] or 0))
            else:
                pre_ggn = pre_ica = 0.0
            costo_ggn = kg_expo_real * pre_ggn
            costo_ica = kg_expo_real * pre_ica

            # 8) Fecha de pago (regla viernes ajustado por calendario_pagos)
            fecha_pago = _calcular_fecha_pago(cur, fecha_proc, dias_pago)

            # 9) UPSERT
            cur.execute(
                """
                INSERT INTO prosagro.kg_consolidado
                    (trazabilidad, fecha_ingreso, semana, anio, zona, lote,
                     kg_total, kg_expo_real, kg_expo_ajustado, kg_nacional,
                     kg_categoria_2, kg_merma, canastillas,
                     nombre_finca, propietario, documento, cantidad_plantas,
                     ubicacion, fecha_procesamiento,
                     precio_expo, precio_nal, precio_desh,
                     costo_total_expo, costo_total_nal, costo_total_desh,
                     costo_total_ggn, costo_total_ica,
                     ggn, ica, dias_pago, fecha_pago,
                     fruta_export_flag, requiere_retencion, ashofrucol,
                     facturacion_electronica, telefono)
                VALUES (%(traz)s, %(fi)s, %(semana)s, %(anio)s, %(zona)s, %(lote)s,
                        %(kg_total)s, %(kg_expo)s, %(kg_aj)s, %(kg_nac)s,
                        %(kg_c2)s, %(kg_merma)s, %(canast)s,
                        %(finca)s, %(prop)s, %(doc)s, %(plantas)s,
                        %(ubic)s, %(fp)s,
                        %(p_expo)s, %(p_nal)s, %(p_desh)s,
                        %(c_expo)s, %(c_nal)s, %(c_desh)s,
                        %(c_ggn)s, %(c_ica)s,
                        %(ggn)s, %(ica)s, %(dpago)s, %(fpago)s,
                        %(fe)s, %(reten)s, %(ashof)s,
                        %(fact)s, %(tel)s)
                ON CONFLICT (trazabilidad) DO UPDATE SET
                    kg_total                = EXCLUDED.kg_total,
                    kg_expo_real            = EXCLUDED.kg_expo_real,
                    kg_expo_ajustado        = EXCLUDED.kg_expo_ajustado,
                    kg_nacional             = EXCLUDED.kg_nacional,
                    kg_categoria_2          = EXCLUDED.kg_categoria_2,
                    kg_merma                = EXCLUDED.kg_merma,
                    canastillas             = EXCLUDED.canastillas,
                    nombre_finca            = EXCLUDED.nombre_finca,
                    propietario             = EXCLUDED.propietario,
                    documento               = EXCLUDED.documento,
                    cantidad_plantas        = EXCLUDED.cantidad_plantas,
                    ubicacion               = EXCLUDED.ubicacion,
                    fecha_procesamiento     = EXCLUDED.fecha_procesamiento,
                    precio_expo             = EXCLUDED.precio_expo,
                    precio_nal              = EXCLUDED.precio_nal,
                    precio_desh             = EXCLUDED.precio_desh,
                    costo_total_expo        = EXCLUDED.costo_total_expo,
                    costo_total_nal         = EXCLUDED.costo_total_nal,
                    costo_total_desh        = EXCLUDED.costo_total_desh,
                    costo_total_ggn         = EXCLUDED.costo_total_ggn,
                    costo_total_ica         = EXCLUDED.costo_total_ica,
                    ggn                     = EXCLUDED.ggn,
                    ica                     = EXCLUDED.ica,
                    dias_pago               = EXCLUDED.dias_pago,
                    fecha_pago              = EXCLUDED.fecha_pago,
                    fruta_export_flag       = EXCLUDED.fruta_export_flag,
                    requiere_retencion      = EXCLUDED.requiere_retencion,
                    ashofrucol              = EXCLUDED.ashofrucol,
                    facturacion_electronica = EXCLUDED.facturacion_electronica,
                    telefono                = EXCLUDED.telefono,
                    actualizado_en          = now()
                """,
                {
                    "traz": traza,
                    "fi": fecha,
                    "semana": semana_i,
                    "anio": anio_i,
                    "zona": zona,
                    "lote": lote,
                    "kg_total": peso_total,
                    "kg_expo": kg_expo_real,
                    "kg_aj": kg_expo_ajustado,
                    "kg_nac": kg_nacional,
                    "kg_c2": kg_C2,
                    "kg_merma": kg_merma,
                    "canast": canast,
                    "finca": finca,
                    "prop": propietario,
                    "doc": doc,
                    "plantas": plantas,
                    "ubic": ubicacion,
                    "fp": fecha_proc,
                    "p_expo": p_expo,
                    "p_nal": p_nal,
                    "p_desh": p_desh,
                    "c_expo": costo_expo,
                    "c_nal": costo_nal,
                    "c_desh": costo_desh,
                    "c_ggn": costo_ggn,
                    "c_ica": costo_ica,
                    "ggn": ggn_traza,
                    "ica": ica_traza,
                    "dpago": dias_pago,
                    "fpago": fecha_pago,
                    "fe": fe_flag,
                    "reten": requiere_ret,
                    "ashof": ashofrucol,
                    "fact": fact_elec,
                    "tel": telefono,
                },
            )
            procesadas += 1

        # ── Segunda pasada: retención en la fuente prorrateada ──
        rete_aplicadas = _calcular_rete_fuente(cur, anio, semana, umbral_retefuente)

        conn.commit()

    return {
        "procesadas": procesadas,
        "rete_grupos": rete_aplicadas,
        "warnings": dict(warnings_acc),
    }


def _calcular_fecha_pago(cur, fecha_proc: dt.date, dias_pago: int) -> dt.date:
    """Replica la regla: parte de fecha_proc + dias_pago y se mueve al viernes
    de pago más cercano según el calendario."""
    if dias_pago <= 0:
        return fecha_proc
    fp_target = fecha_proc + dt.timedelta(days=dias_pago)
    cur.execute(
        "SELECT fecha, dia_semana, es_dia_pago FROM prosagro.calendario_pagos WHERE fecha = %s",
        (fp_target,),
    )
    row = cur.fetchone()
    if not row:
        return fp_target
    cf, ds, ep = row
    if ep:
        return cf
    if ds == 7:  # sábado → viernes anterior
        return cf - dt.timedelta(days=1)
    if ds == 1:  # domingo → viernes anterior
        return cf - dt.timedelta(days=2)
    # otro día (festivo / no pago) — siguiente día de pago
    cur.execute(
        """
        SELECT fecha FROM prosagro.calendario_pagos
        WHERE fecha > %s AND es_dia_pago
        ORDER BY fecha LIMIT 1
        """,
        (cf,),
    )
    siguiente = cur.fetchone()
    return siguiente[0] if siguiente else cf


def _calcular_rete_fuente(cur, anio, semana, umbral) -> int:
    """Agrupa por (fecha_ingreso, propietario) la base = expo + nal + desh,
    si supera umbral aplica 1.5% y lo PRORRATEA proporcionalmente a las
    contribuciones de cada traza del grupo."""
    where = "WHERE k.propietario IS NOT NULL AND (k.requiere_retencion IS NULL OR k.requiere_retencion <> 'No')"
    params: list = []
    if anio is not None:
        where += " AND k.anio = %s"
        params.append(anio)
    if semana is not None:
        where += " AND k.semana = %s"
        params.append(semana)

    cur.execute(
        f"""
        SELECT k.fecha_ingreso, k.propietario,
               SUM(k.costo_total_expo + k.costo_total_nal + k.costo_total_desh) AS base,
               ARRAY_AGG(k.id) AS ids
        FROM prosagro.kg_consolidado k
        {where}
        GROUP BY k.fecha_ingreso, k.propietario
        """,
        params,
    )
    grupos = cur.fetchall()
    aplicadas = 0
    for fecha_ing, prop, base, ids in grupos:
        base = float(base or 0)
        if base < umbral:
            rete_total = 0.0
        else:
            rete_total = base * TASA_RETEFUENTE
            aplicadas += 1
        # Prorratear
        for kid in ids:
            cur.execute(
                """
                SELECT (costo_total_expo + costo_total_nal + costo_total_desh)
                FROM prosagro.kg_consolidado WHERE id = %s
                """,
                (kid,),
            )
            sub = float(cur.fetchone()[0] or 0)
            proporc = (sub / base) * rete_total if base else 0.0
            cur.execute(
                "UPDATE prosagro.kg_consolidado SET retencion_fuente = %s WHERE id = %s",
                (proporc, kid),
            )
    return aplicadas


def estadisticas_kg_consolidado(anio: int | None = None, semana: int | None = None) -> dict:
    """Para mostrar en la app después del recálculo."""
    where = "WHERE 1=1"
    params: list = []
    if anio is not None:
        where += " AND anio = %s"
        params.append(anio)
    if semana is not None:
        where += " AND semana = %s"
        params.append(semana)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*),
                   COALESCE(SUM(kg_total), 0),
                   COALESCE(SUM(kg_expo_real), 0),
                   COALESCE(SUM(kg_nacional), 0),
                   COALESCE(SUM(kg_merma), 0),
                   COALESCE(SUM(costo_total_expo + costo_total_nal + costo_total_desh), 0),
                   COALESCE(SUM(ashofrucol), 0),
                   COALESCE(SUM(retencion_fuente), 0)
            FROM prosagro.kg_consolidado
            {where}
            """,
            params,
        )
        r = cur.fetchone()
    return {
        "filas":            r[0],
        "kg_total":         float(r[1] or 0),
        "kg_expo":          float(r[2] or 0),
        "kg_nacional":      float(r[3] or 0),
        "kg_merma":         float(r[4] or 0),
        "costo_total":      float(r[5] or 0),
        "ashofrucol":       float(r[6] or 0),
        "retencion_fuente": float(r[7] or 0),
    }
