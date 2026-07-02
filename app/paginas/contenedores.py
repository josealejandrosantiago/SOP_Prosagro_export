"""Página: Contenedores.

Flujo:
  1. Subir packing list (xlsx) → parseo con contenedor_engine.cargar_packing_list.
     Muestra contenedor, pallets, cajas. Botón para cruzar con fruta export.
  2. Estado de contenedores: tabla consolidada del resumen de cada contenedor
     disponible + selectbox para ver el detalle de uno.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import contenedor_engine, ggn_service


def render(user: dict) -> None:
    st.title("Contenedores")
    st.caption(
        "Armado y cruce de contenedores: subí el packing list del warehouse, "
        "cruzalo contra la fruta de exportación y revisá el estado de cada "
        "contenedor (pallets cruzados, cajas y kilos export)."
    )

    _bloque_subir_packing_list()

    st.divider()
    _bloque_estado_contenedores()


# ─────────────────────────────────────────────────────────────────────────────
# Sección: Subir packing list
# ─────────────────────────────────────────────────────────────────────────────
def _bloque_subir_packing_list() -> None:
    st.subheader("Subir packing list")

    archivo = st.file_uploader(
        "Selecciona el packing list (xlsx)",
        type=["xlsx"],
        key="packing_list_uploader",
    )
    if archivo is None:
        st.info("Subí un packing list para armar y cruzar el contenedor.")
        return

    with st.spinner("Parseando packing list…"):
        try:
            info = _cargar_subido(archivo)
        except Exception as e:  # pragma: no cover — UX necesita el detalle
            st.error(f"Error leyendo el packing list: {e}")
            return

    codigo = info.get("contenedor")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contenedor", codigo or "—")
    c2.metric("Pallets", info.get("pallets", 0))
    c3.metric("Cajas", info.get("total_cajas", 0))
    c4.metric("Warehouse", info.get("warehouse") or "—")
    st.caption(f"Archivo: `{archivo.name}`")

    detalle = info.get("detalle_filas") or []
    if detalle:
        with st.expander(f"Detalle del packing list ({len(detalle)} filas)"):
            st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

    if not codigo:
        st.warning("El packing list no trae un código de contenedor identificable.")
        return

    st.divider()
    if st.button(
        f"Cruzar con fruta export ({codigo})",
        type="primary",
        use_container_width=True,
        key="btn_cruzar",
    ):
        _accion_cruzar(codigo)


def _accion_cruzar(codigo: str) -> None:
    with st.spinner(f"Cruzando contenedor {codigo} con fruta export…"):
        try:
            cruce = contenedor_engine.cruzar_contenedor(codigo)
        except Exception as e:  # pragma: no cover — UX necesita el detalle
            st.error(f"Error cruzando el contenedor: {e}")
            return

    c1, c2, c3 = st.columns(3)
    c1.metric("Pallets cruzados", len(cruce.get("pallets_cruzados") or []))
    c2.metric("Pallets sin match", len(cruce.get("pallets_sin_match") or []))
    c3.metric("Filas divididas", len(cruce.get("filas_divididas") or []))

    cruces = cruce.get("cruces") or []
    if cruces:
        st.markdown("**Cruces encontrados:**")
        st.dataframe(pd.DataFrame(cruces), use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron cruces para este contenedor.")

    sin_match = cruce.get("pallets_sin_match") or []
    if sin_match:
        with st.expander(f"Pallets sin match ({len(sin_match)})"):
            st.dataframe(pd.DataFrame(sin_match), use_container_width=True, hide_index=True)

    warnings = cruce.get("warnings") or []
    if warnings:
        with st.expander(f"⚠ Warnings del cruce ({len(warnings)})"):
            for w in warnings:
                st.warning(w)


# ─────────────────────────────────────────────────────────────────────────────
# Sección: Estado de contenedores
# ─────────────────────────────────────────────────────────────────────────────
def _bloque_estado_contenedores() -> None:
    st.subheader("Estado de contenedores")

    codigos = ggn_service.contenedores_disponibles()
    if not codigos:
        st.info("No hay contenedores disponibles todavía.")
        return

    filas = []
    resumenes: dict[str, dict] = {}
    for cod in codigos:
        try:
            r = contenedor_engine.resumen_contenedor(cod)
        except Exception:  # pragma: no cover — un contenedor roto no tumba la tabla
            continue
        resumenes[cod] = r
        filas.append(
            {
                "Código": r.get("codigo", cod),
                "Armado completo": "Sí" if r.get("armado_completo") else "No",
                "Pallets cruzados": r.get("pallets_total", 0),
                "Pallets total": r.get("total_pallets", 0),
                "Cajas export": r.get("cajas_export", 0),
                "Kg export": round(float(r.get("kg_export", 0) or 0), 0),
            }
        )

    if not filas:
        st.info("No se pudo armar el resumen de ningún contenedor.")
        return

    df = pd.DataFrame(filas)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Detalle de un contenedor**")
    sel = st.selectbox(
        "Elegí un contenedor para ver el detalle",
        options=list(resumenes.keys()),
        key="sel_contenedor_detalle",
    )
    if not sel:
        return

    r = resumenes[sel]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Armado completo", "Sí" if r.get("armado_completo") else "No")
    c2.metric("Pallets cruzados / total", f"{r.get('pallets_total', 0)} / {r.get('total_pallets', 0)}")
    c3.metric("Cajas export", r.get("cajas_export", 0))
    c4.metric("Kg export", f"{float(r.get('kg_export', 0) or 0):,.0f}")

    detalle_filas = r.get("detalle_filas") or []
    detalle_cruzadas = r.get("detalle_cruzadas") or []
    tab_det, tab_cruz = st.tabs(["Detalle de filas", "Filas cruzadas"])
    with tab_det:
        if detalle_filas:
            st.dataframe(pd.DataFrame(detalle_filas), use_container_width=True, hide_index=True)
        else:
            st.info("Sin filas de detalle para este contenedor.")
    with tab_cruz:
        if detalle_cruzadas:
            st.dataframe(pd.DataFrame(detalle_cruzadas), use_container_width=True, hide_index=True)
        else:
            st.info("Sin filas cruzadas para este contenedor.")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _cargar_subido(archivo) -> dict:
    """Streamlit FileUploader devuelve un BytesIO — el engine quiere un path."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(archivo.getvalue())
        tmp_path = Path(tmp.name)
    try:
        return contenedor_engine.cargar_packing_list(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
