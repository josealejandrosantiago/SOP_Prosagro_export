"""Página: Distribución a clientes.

Reemplaza el `frmDistribucionContenedor` de la macro VBA.

Dos pestañas:
  1. Por contenedor — resumen por cliente + detalle de pallets de un contenedor,
     con formulario para asignar un pallet a un cliente.
  2. Resumen por cliente (global) — totales acumulados por cliente y un gráfico
     de cajas por cliente.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import distribucion_service


def render(user: dict) -> None:
    st.title("Distribución a clientes")
    st.caption(
        "Asignación de pallets a clientes por contenedor y consolidado global "
        "de pallets/cajas por cliente. Reemplaza el formulario "
        "`frmDistribucionContenedor` de la macro."
    )

    tab_cont, tab_global = st.tabs(
        ["Por contenedor", "Resumen por cliente (global)"]
    )

    with tab_cont:
        _tab_por_contenedor()

    with tab_global:
        _tab_resumen_global()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Por contenedor
# ─────────────────────────────────────────────────────────────────────────────
def _tab_por_contenedor() -> None:
    codigos = distribucion_service.contenedores()
    if not codigos:
        st.info("Aún no hay contenedores cargados para distribuir.")
        return

    codigo = st.selectbox("Contenedor", codigos, key="dist_codigo")

    # ── Resumen por cliente del contenedor ──────────────────────────────────
    st.subheader("Resumen por cliente")
    resumen = distribucion_service.resumen_por_cliente(codigo)
    if not resumen:
        st.info(f"El contenedor {codigo} aún no tiene pallets asignados.")
    else:
        df_res = pd.DataFrame(resumen)
        tot_pallets = sum(int(r.get("pallets", 0) or 0) for r in resumen)
        tot_cajas = sum(int(r.get("cajas", 0) or 0) for r in resumen)
        m1, m2, m3 = st.columns(3)
        m1.metric("Clientes", f"{len(resumen):,.0f}".replace(",", "."))
        m2.metric("Pallets", f"{tot_pallets:,.0f}".replace(",", "."))
        m3.metric("Cajas", f"{tot_cajas:,.0f}".replace(",", "."))

        df_res_show = df_res.rename(
            columns={
                "cliente": "Cliente",
                "pais": "País",
                "pallets": "Pallets",
                "cajas": "Cajas",
                "tipo_negociacion": "Tipo negociación",
            }
        )
        st.dataframe(
            df_res_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pallets": st.column_config.NumberColumn(format="%.0f"),
                "Cajas": st.column_config.NumberColumn(format="%.0f"),
            },
        )

    # ── Detalle de pallets del contenedor ───────────────────────────────────
    st.divider()
    st.subheader("Detalle de pallets")
    detalle = distribucion_service.distribucion_de(codigo)
    if not detalle:
        st.info(f"El contenedor {codigo} no tiene pallets registrados.")
    else:
        df_det = pd.DataFrame(detalle)
        df_det_show = df_det.rename(
            columns={
                "no_pallet": "N° pallet",
                "total_cajas": "Cajas",
                "calibre_dominante": "Calibre",
                "cliente": "Cliente",
                "tipo_negociacion": "Tipo negociación",
            }
        )
        st.dataframe(
            df_det_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Cajas": st.column_config.NumberColumn(format="%.0f"),
            },
        )

    # ── Formulario de asignación ────────────────────────────────────────────
    st.divider()
    _form_asignar(codigo)


def _form_asignar(codigo: str) -> None:
    st.subheader("Asignar pallet a cliente")

    clientes = distribucion_service.clientes()
    if not clientes:
        st.info("No hay clientes registrados para asignar.")
        return

    opciones = {c["id"]: c for c in clientes}

    with st.form(key=f"form_asignar_{codigo}"):
        c1, c2 = st.columns(2)
        no_pallet = c1.number_input(
            "N° de pallet",
            min_value=1,
            step=1,
            key="asig_no_pallet",
        )
        cliente_id = c2.selectbox(
            "Cliente",
            options=list(opciones.keys()),
            format_func=lambda cid: (
                f"{opciones[cid]['nombre']} ({opciones[cid].get('pais', '')})"
            ),
            key="asig_cliente",
        )
        tipo_neg = st.text_input(
            "Tipo de negociación",
            key="asig_tipo_neg",
            help="Ej.: Precio fijo, Consignación, Comisión…",
        )
        enviar = st.form_submit_button(
            "Asignar", type="primary", use_container_width=True
        )

    if enviar:
        with st.spinner("Asignando pallet…"):
            try:
                distribucion_service.asignar_pallet(
                    codigo, int(no_pallet), cliente_id, tipo_neg
                )
            except Exception as e:  # pragma: no cover — UX necesita el detalle
                st.error(f"No se pudo asignar el pallet: {e}")
                raise
        nombre = opciones[cliente_id]["nombre"]
        st.success(
            f"✅ Pallet {int(no_pallet)} del contenedor {codigo} asignado a "
            f"**{nombre}**."
        )
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Resumen por cliente (global)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_resumen_global() -> None:
    totales = distribucion_service.totales_por_cliente_global()
    if not totales:
        st.info("Aún no hay distribuciones registradas.")
        return

    df = pd.DataFrame(totales)
    tot_pallets = sum(int(r.get("pallets", 0) or 0) for r in totales)
    tot_cajas = sum(int(r.get("cajas", 0) or 0) for r in totales)
    m1, m2, m3 = st.columns(3)
    m1.metric("Clientes", f"{len(totales):,.0f}".replace(",", "."))
    m2.metric("Pallets", f"{tot_pallets:,.0f}".replace(",", "."))
    m3.metric("Cajas", f"{tot_cajas:,.0f}".replace(",", "."))

    df_show = df.rename(
        columns={
            "nombre": "Cliente",
            "pais": "País",
            "pallets": "Pallets",
            "cajas": "Cajas",
            "contenedores": "Contenedores",
        }
    )
    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pallets": st.column_config.NumberColumn(format="%.0f"),
            "Cajas": st.column_config.NumberColumn(format="%.0f"),
            "Contenedores": st.column_config.NumberColumn(format="%.0f"),
        },
    )

    st.divider()
    st.subheader("Cajas por cliente")
    df_chart = df[["nombre", "cajas"]].copy()
    df_chart["cajas"] = pd.to_numeric(df_chart["cajas"], errors="coerce").fillna(0)
    df_chart = df_chart.set_index("nombre")
    st.bar_chart(df_chart, color=COLORS["primary"])
