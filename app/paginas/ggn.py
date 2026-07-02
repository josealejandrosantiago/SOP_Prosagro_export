"""Página: GGN / Certificación.

Liquida el costo de certificación (GGN + ICA) que corrige el bug de la macro
VBA original: el VBA calculaba un único costo mezclado, cuando en realidad GGN
e ICA son certificaciones SEPARADAS con precio propio; acá se calculan aparte
y se SUMAN.

Dos vistas:
  - "Por contenedor": elige un contenedor y muestra la liquidación fila a fila
    (una por trazabilidad) con costo GGN, costo ICA y total.
  - "Por rango de fechas": agrupa por productor entre dos fechas.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import ggn_service


def render(user: dict) -> None:
    st.title("GGN / Certificación")
    st.caption(
        "Costo de certificación por kg exportado. GGN e ICA son "
        "certificaciones distintas: se liquidan por separado y se suman."
    )

    st.info(
        "🐞 Corrige el bug de la macro VBA: el VBA calculaba un único costo "
        "mezclado. Acá **GGN e ICA se calculan SEPARADOS y se suman** en el "
        "costo total de certificación."
    )
    st.caption(
        "Si `precio_certificacion` no está cargado para el período, los costos "
        "saldrán en $0. Cargá los precios de certificación para ver valores."
    )

    tab_cont, tab_rango = st.tabs(["Por contenedor", "Por rango de fechas"])

    with tab_cont:
        _tab_por_contenedor()

    with tab_rango:
        _tab_por_rango()


# ─────────────────────────────────────────────────────────────────────────────
# Tab: Por contenedor
# ─────────────────────────────────────────────────────────────────────────────
def _tab_por_contenedor() -> None:
    contenedores = ggn_service.contenedores_disponibles()
    if not contenedores:
        st.info("Aún no hay contenedores disponibles para liquidar.")
        return

    contenedor = st.selectbox(
        "Contenedor",
        options=contenedores,
        key="ggn_contenedor",
    )
    if not contenedor:
        return

    filas = ggn_service.liquidacion_por_contenedor(contenedor)
    if not filas:
        st.info(f"El contenedor {contenedor} no tiene filas para liquidar.")
        return

    df = pd.DataFrame(filas)
    df["fecha_procesamiento"] = pd.to_datetime(
        df["fecha_procesamiento"], errors="coerce"
    ).dt.strftime("%d/%m/%Y")

    total_ggn = float(df["costo_total_ggn"].fillna(0).sum())
    total_ica = float(df["costo_total_ica"].fillna(0).sum())
    total_cert = float(df["costo_certif_total"].fillna(0).sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Costo GGN", f"${total_ggn:,.0f}".replace(",", "."))
    c2.metric("Costo ICA", f"${total_ica:,.0f}".replace(",", "."))
    c3.metric("Total certificación", f"${total_cert:,.0f}".replace(",", "."))

    vista = pd.DataFrame(
        {
            "Trazabilidad": df["trazabilidad"],
            "Zona": df["zona"],
            "Lote": df["lote"],
            "Finca": df["nombre_finca"],
            "Propietario": df["propietario"],
            "Documento": df["documento"],
            "GGN": df["ggn"],
            "ICA": df["ica"],
            "Kg expo": df["kg_expo_real"].astype(float).round(0),
            "Fecha proc.": df["fecha_procesamiento"],
            "Costo GGN": df["costo_total_ggn"].fillna(0).astype(float).round(0),
            "Costo ICA": df["costo_total_ica"].fillna(0).astype(float).round(0),
            "Total cert.": df["costo_certif_total"].fillna(0).astype(float).round(0),
        }
    )
    st.dataframe(
        vista,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Kg expo": st.column_config.NumberColumn(format="%.0f"),
            "Costo GGN": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo ICA": st.column_config.NumberColumn(format="$ %.0f"),
            "Total cert.": st.column_config.NumberColumn(format="$ %.0f"),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tab: Por rango de fechas
# ─────────────────────────────────────────────────────────────────────────────
def _tab_por_rango() -> None:
    c1, c2 = st.columns(2)
    fecha_desde = c1.date_input("Desde", key="ggn_rango_desde", format="DD/MM/YYYY")
    fecha_hasta = c2.date_input("Hasta", key="ggn_rango_hasta", format="DD/MM/YYYY")

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        st.warning("La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
        return

    filas = ggn_service.liquidacion_por_rango(fecha_desde, fecha_hasta)
    if not filas:
        st.info(
            f"No hay liquidación de certificación entre "
            f"{fecha_desde.strftime('%d/%m/%Y')} y "
            f"{fecha_hasta.strftime('%d/%m/%Y')}."
        )
        return

    df = pd.DataFrame(filas)

    total_ggn = float(df["costo_ggn"].fillna(0).sum())
    total_ica = float(df["costo_ica"].fillna(0).sum())
    total_cert = float(df["costo_total"].fillna(0).sum())

    m1, m2, m3 = st.columns(3)
    m1.metric("Costo GGN", f"${total_ggn:,.0f}".replace(",", "."))
    m2.metric("Costo ICA", f"${total_ica:,.0f}".replace(",", "."))
    m3.metric("Total certificación", f"${total_cert:,.0f}".replace(",", "."))

    vista = pd.DataFrame(
        {
            "Propietario": df["propietario"],
            "Documento": df["documento"],
            "Zona": df["zona"],
            "Lote": df["lote"],
            "Finca": df["nombre_finca"],
            "GGN": df["ggn"],
            "ICA": df["ica"],
            "Kg expo": df["kg_expo"].astype(float).round(0),
            "Costo GGN": df["costo_ggn"].fillna(0).astype(float).round(0),
            "Costo ICA": df["costo_ica"].fillna(0).astype(float).round(0),
            "Costo total": df["costo_total"].fillna(0).astype(float).round(0),
        }
    )
    st.dataframe(
        vista,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Kg expo": st.column_config.NumberColumn(format="%.0f"),
            "Costo GGN": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo ICA": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo total": st.column_config.NumberColumn(format="$ %.0f"),
        },
    )
