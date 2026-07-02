"""Página: Causales de rechazo.

Flujo:
  1. Subir uno o varios reportes `Evaluación de Calidad` de Binlab (xlsx).
     Por cada archivo se guarda en tempfile y se llama a
     `causales_service.cargar_reporte`, mostrando causales cargadas,
     trazabilidad y avisos.
  2. Resumen en dos pestañas:
       - "Detalle": tabla fila a fila (`resumen`), fechas dd/mm/aaaa.
       - "Por causal": tabla agregada (`resumen_por_causal`) ordenada por
         kg afectados + gráfico de barras de kg por causal.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import causales_service


def render(user: dict) -> None:
    st.title("Causales de rechazo")
    st.caption(
        "Subir los reportes `Evaluación de Calidad` de Binlab para registrar "
        "las causales de rechazo de fruta nacional por trazabilidad. Abajo se "
        "consolidan las causales cargadas y su impacto en kilos."
    )

    _bloque_subir()

    st.divider()
    st.subheader("Resumen de causales")
    _bloque_resumen()


# ─────────────────────────────────────────────────────────────────────────────
# Bloques de UI
# ─────────────────────────────────────────────────────────────────────────────
def _bloque_subir() -> None:
    st.subheader("Subir reportes de calidad")
    archivos = st.file_uploader(
        "Selecciona uno o varios xlsx `Evaluación de Calidad`",
        type=["xlsx"],
        accept_multiple_files=True,
        key="causales_uploader",
    )
    if not archivos:
        return

    for archivo in archivos:
        with st.spinner(f"Cargando `{archivo.name}`…"):
            try:
                resultado = _cargar_subido(archivo)
            except Exception as e:  # pragma: no cover — UX necesita el detalle
                st.error(f"Error cargando `{archivo.name}`: {e}")
                continue

        with st.expander(f"📄 {archivo.name}", expanded=True):
            causales = resultado.get("causales") or []
            avisos = resultado.get("avisos") or []
            traza = resultado.get("trazabilidad")

            c1, c2 = st.columns(2)
            c1.metric("Causales cargadas", len(causales))
            c2.metric("Avisos", len(avisos))
            if traza:
                st.caption(f"Trazabilidad: `{traza}`")

            if causales:
                st.dataframe(
                    pd.DataFrame(causales),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("El reporte no trajo causales para cargar.")

            if avisos:
                st.markdown(f"**⚠ {len(avisos)} avisos:**")
                for a in avisos[:50]:
                    st.warning(a)


def _bloque_resumen() -> None:
    tab_detalle, tab_por_causal = st.tabs(["Detalle", "Por causal"])

    with tab_detalle:
        filas = causales_service.resumen(limite=500)
        if not filas:
            st.info("Aún no hay causales registradas en BD.")
        else:
            df = pd.DataFrame(filas)
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
                df["fecha"] = df["fecha"].dt.strftime("%d/%m/%Y")
            df = df.rename(
                columns={
                    "fecha": "Fecha",
                    "trazabilidad": "Trazabilidad",
                    "causal": "Causal",
                    "severidad": "Severidad",
                    "porcentaje": "% causal",
                    "kg_nacional": "Kg nacional",
                    "kg_con_causal": "Kg con causal",
                    "zona": "Zona",
                    "lote": "Lote",
                }
            )
            st.caption(f"{len(df)} registros")
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_por_causal:
        agg = causales_service.resumen_por_causal()
        if not agg:
            st.info("Aún no hay causales registradas en BD.")
        else:
            df = pd.DataFrame(agg)
            if "kg_afectados" in df.columns:
                df = df.sort_values("kg_afectados", ascending=False)
            df_show = df.rename(
                columns={
                    "causal": "Causal",
                    "severidad": "Severidad",
                    "ocurrencias": "Ocurrencias",
                    "pct_promedio": "% promedio",
                    "kg_afectados": "Kg afectados",
                }
            )
            st.dataframe(df_show, use_container_width=True, hide_index=True)

            if "kg_afectados" in df.columns and "causal" in df.columns:
                st.markdown("**Kg afectados por causal:**")
                chart_df = df.set_index("causal")[["kg_afectados"]]
                st.bar_chart(chart_df, color=COLORS.get("primary"))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _cargar_subido(archivo) -> dict:
    """Streamlit FileUploader devuelve un BytesIO — el servicio quiere un path."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(archivo.getvalue())
        tmp_path = Path(tmp.name)
    try:
        return causales_service.cargar_reporte(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
