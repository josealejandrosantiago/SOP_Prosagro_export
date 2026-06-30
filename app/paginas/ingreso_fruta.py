"""Página: Ingreso de fruta.

Flujo:
  1. Lista las semanas ya cargadas.
  2. Permite subir el `Informe de proceso semana N.xlsx` de Binlab.
  3. Muestra preview con tres pestañas (ingresos / export / nacional) y un
     editor para marcar `fruta_export Si/No` por trazabilidad.
  4. Guarda a BD en una sola transacción (idempotente).
  5. Botón aparte para reconstruir `kg_consolidado` de esa semana.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import persistencia, sop_engine
from ingesta.parser_maquila import InformeMaquila, parsear


def render(user: dict) -> None:
    st.title("Ingreso de fruta")
    st.caption(
        "Subir el archivo crudo `Informe de proceso semana N.xlsx` "
        "que entrega Binlab. La app normaliza la trazabilidad, separa "
        "calibre 26 a simulación y carga a la BD."
    )

    _bloque_semanas_cargadas()

    st.divider()
    st.subheader("Subir nuevo informe")

    archivo = st.file_uploader(
        "Selecciona el xlsx de la maquila",
        type=["xlsx"],
        key="informe_uploader",
    )
    if archivo is None:
        return

    # Parseo en archivo temporal (openpyxl quiere un path)
    with st.spinner("Parseando archivo…"):
        informe = _parsear_subido(archivo)

    _bloque_resumen(informe, archivo.name)

    if not informe.ingresos:
        st.error("El archivo no trae filas de ingreso. Revisa que sea el archivo correcto.")
        return

    flags_export = _bloque_tabs_y_editor(informe)

    st.divider()
    col_a, col_b, _ = st.columns([1, 1, 3])
    if col_a.button("Guardar a BD", type="primary", use_container_width=True):
        _accion_guardar(informe, flags_export, user)
    if col_b.button(
        f"Reconstruir Kg consolidado semana {informe.semana}",
        use_container_width=True,
        help="Recalcula la tabla kg_consolidado para esta semana usando "
             "productores, precios y calendario vigentes.",
    ):
        _accion_reconstruir(informe.anio, informe.semana)


# ─────────────────────────────────────────────────────────────────────────────
# Bloques de UI
# ─────────────────────────────────────────────────────────────────────────────
def _bloque_semanas_cargadas() -> None:
    semanas = persistencia.semanas_cargadas()
    if not semanas:
        st.info("Aún no hay informes cargados en BD.")
        return
    df = pd.DataFrame(semanas)
    df["semana"] = df["semana"].astype(int)
    df["anio"] = df["anio"].astype(int)
    df["peso_total"] = df["peso_total"].astype(float).round(0)
    df = df.rename(
        columns={
            "anio": "Año",
            "semana": "Semana",
            "ingresos": "# ingresos",
            "export_flag": "marcados export",
            "peso_total": "Kg total",
            "desde": "Desde",
            "hasta": "Hasta",
        }
    )
    with st.expander(f"Semanas ya cargadas ({len(df)})", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)


def _bloque_resumen(informe: InformeMaquila, nombre_archivo: str) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Año", informe.anio)
    c2.metric("Semana", informe.semana)
    c3.metric("Ingresos", len(informe.ingresos))
    c4.metric("Filas export", len(informe.export))
    c5.metric("Filas nacional", len(informe.nacional))
    st.caption(f"Archivo: `{nombre_archivo}`")

    if informe.avisos:
        with st.expander(f"⚠ {len(informe.avisos)} avisos del parser"):
            for a in informe.avisos[:50]:
                st.warning(a)


def _bloque_tabs_y_editor(informe: InformeMaquila) -> dict[str, bool]:
    """Tres pestañas con preview + editor del flag `fruta_export` en ingresos."""
    tab_ing, tab_exp, tab_nal = st.tabs(
        ["Ingresos (editar export Si/No)", "Fruta export", "Fruta nacional"]
    )

    with tab_ing:
        df = pd.DataFrame(
            [
                {
                    "trazabilidad": i.trazabilidad,
                    "fecha": i.fecha_ingreso,
                    "zona": i.zona,
                    "lote": i.lote,
                    "no_cargue": i.no_cargue,
                    "canastillas": i.canastillas,
                    "peso_neto": float(i.peso_neto),
                    "conductor": i.conductor,
                    "placa": i.placa,
                    "fruta_export": True,
                }
                for i in informe.ingresos
            ]
        )
        col_a, col_b, _ = st.columns([1, 1, 5])
        if col_a.button("Marcar todos", use_container_width=True, key="mark_all_yes"):
            st.session_state["_mark_all_yes"] = True
        if col_b.button("Desmarcar todos", use_container_width=True, key="mark_all_no"):
            st.session_state["_mark_all_yes"] = False
        if "_mark_all_yes" in st.session_state:
            df["fruta_export"] = st.session_state["_mark_all_yes"]
            del st.session_state["_mark_all_yes"]

        df_edit = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=[c for c in df.columns if c != "fruta_export"],
            column_config={
                "fruta_export": st.column_config.CheckboxColumn(
                    "¿Es fruta export?", help="Desmárcalo si NO se va a contabilizar como exportación."
                ),
                "peso_neto": st.column_config.NumberColumn("Peso neto", format="%.0f kg"),
            },
        )
        flags = dict(zip(df_edit["trazabilidad"], df_edit["fruta_export"]))

    with tab_exp:
        df = pd.DataFrame(
            [
                {
                    "trazabilidad": f.trazabilidad,
                    "fecha": f.fecha_ingreso,
                    "no_cargue": f.no_cargue,
                    "id_calibre": f.id_calibre,
                    "calibre_num": f.calibre_num,
                    "cant_cajas": float(f.cant_cajas),
                    "total_kg": float(f.total_kg_netos),
                    "predio": f.predio,
                    "ica": f.ica,
                    "ggn": f.ggn,
                    "categoria": f.categoria,
                }
                for f in informe.export
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_nal:
        df = pd.DataFrame(
            [
                {
                    "trazabilidad": f.trazabilidad,
                    "fecha": f.fecha_ingreso,
                    "no_cargue": f.no_cargue,
                    "lote_proceso": f.lote_proceso,
                    "merma": float(f.merma),
                    "cant_kilos_descarte": float(f.cant_kilos_descarte),
                    "simulacion_kg": float(f.simulacion_kg),
                    "total_nacional": float(f.cant_kilos_descarte + f.simulacion_kg),
                }
                for f in informe.nacional
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Acciones
# ─────────────────────────────────────────────────────────────────────────────
def _accion_guardar(informe: InformeMaquila, flags: dict[str, bool], user: dict) -> None:
    n_si = sum(1 for v in flags.values() if v)
    n_no = len(flags) - n_si
    with st.spinner(f"Guardando {len(informe.ingresos)} ingresos a BD…"):
        try:
            resumen = persistencia.persistir_informe(informe, flags, user)
        except Exception as e:  # pragma: no cover — UX necesita el detalle
            st.error(f"Error guardando: {e}")
            raise
    st.success(
        f"✅ Guardado en BD:\n\n"
        f"- **{resumen['ingresos']}** ingresos "
        f"({resumen['nuevos']} nuevos, {resumen['actualizados']} actualizados).\n"
        f"- **{resumen['export']}** filas fruta export.\n"
        f"- **{resumen['nacional']}** filas fruta nacional.\n"
        f"- Marcadas como fruta export: **{n_si}**, NO export: **{n_no}**."
    )


def _accion_reconstruir(anio: int, semana: int) -> None:
    with st.spinner(f"Reconstruyendo Kg consolidado de semana {semana}/{anio}…"):
        resultado = sop_engine.reconstruir_kg_consolidado(anio=anio, semana=semana)
        stats = sop_engine.estadisticas_kg_consolidado(anio=anio, semana=semana)

    st.success(
        f"✅ Recalculado para semana {semana} / {anio}:\n\n"
        f"- **{resultado['procesadas']}** trazabilidades procesadas.\n"
        f"- **{resultado['rete_grupos']}** grupos retención aplicados.\n"
        f"- **{len(resultado['warnings'])}** tipos de warnings."
    )
    if resultado["warnings"]:
        with st.expander("Warnings"):
            for k, v in resultado["warnings"].items():
                st.warning(f"{v} × {k}")
    st.markdown("**Totales de la semana:**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kg total",     f"{stats['kg_total']:,.0f}")
    c2.metric("Kg expo",      f"{stats['kg_expo']:,.0f}")
    c3.metric("Kg nacional",  f"{stats['kg_nacional']:,.0f}")
    c4.metric("Kg merma",     f"{stats['kg_merma']:,.0f}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Costo total",  f"${stats['costo_total']:,.0f}")
    c2.metric("Ashofrucol",   f"${stats['ashofrucol']:,.0f}")
    c3.metric("Retefuente",   f"${stats['retencion_fuente']:,.0f}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _parsear_subido(archivo) -> InformeMaquila:
    """Streamlit FileUploader devuelve un BytesIO — openpyxl quiere un path."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(archivo.getvalue())
        tmp_path = Path(tmp.name)
    try:
        return parsear(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
