"""Página: Ventas.

Reemplaza los formularios VBA frmPrecioEstimado / frmAsignarPrecios /
frmArchivosPlanoFacturacion. Tres pestañas:
  1. Precios estimados — por contenedor, tabla de precios estimados por cliente.
  2. Precios reales — tabla de precios reales + formulario para registrar uno.
  3. Resumen + plano — resumen de ventas por contenedor y descarga del plano
     de facturación (CSV) por contenedor.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import distribucion_service, ventas_service


def render(user: dict) -> None:
    st.title("Ventas")
    st.caption(
        "Precios estimados y reales por contenedor, registro de precios de "
        "venta y generación del plano de facturación para cada contenedor."
    )

    contenedores = ventas_service.contenedores()
    if not contenedores:
        st.info("Aún no hay contenedores con información de ventas.")
        return

    tab_est, tab_real, tab_res = st.tabs(
        ["Precios estimados", "Precios reales", "Resumen + plano"]
    )

    with tab_est:
        _tab_precios_estimados(contenedores)

    with tab_real:
        _tab_precios_reales(contenedores)

    with tab_res:
        _tab_resumen_plano(contenedores)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Precios estimados
# ─────────────────────────────────────────────────────────────────────────────
def _tab_precios_estimados(contenedores: list[str]) -> None:
    codigo = st.selectbox("Contenedor", contenedores, key="est_cont")

    precios = ventas_service.precios_estimados(codigo)
    if not precios:
        st.info(f"El contenedor {codigo} no tiene precios estimados.")
        return

    df = pd.DataFrame(precios)
    if "fecha_recogida_estimada" in df.columns:
        df["fecha_recogida_estimada"] = df["fecha_recogida_estimada"].apply(_fmt_fecha)
    df_show = df.rename(
        columns={
            "cliente": "Cliente",
            "precio_estimado": "Precio estimado",
            "moneda": "Moneda",
            "cajas": "Cajas",
            "fecha_recogida_estimada": "F. recogida",
            "observaciones": "Observaciones",
        }
    )
    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cajas": st.column_config.NumberColumn(format="%.0f"),
            "Precio estimado": st.column_config.NumberColumn(format="%.2f"),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Precios reales
# ─────────────────────────────────────────────────────────────────────────────
def _tab_precios_reales(contenedores: list[str]) -> None:
    codigo = st.selectbox("Contenedor", contenedores, key="real_cont")

    precios = ventas_service.precios_reales(codigo)
    if not precios:
        st.info(f"El contenedor {codigo} no tiene precios reales registrados.")
    else:
        df = pd.DataFrame(precios)
        if "fecha_recogida_real" in df.columns:
            df["fecha_recogida_real"] = df["fecha_recogida_real"].apply(_fmt_fecha)
        df_show = df.rename(
            columns={
                "cliente": "Cliente",
                "tipo_documento": "Tipo doc.",
                "consecutivo_ne": "Consecutivo NE",
                "cajas": "Cajas",
                "precio_unitario": "Precio unitario",
                "moneda": "Moneda",
                "fecha_recogida_real": "F. recogida",
                "observaciones": "Observaciones",
            }
        )
        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Cajas": st.column_config.NumberColumn(format="%.0f"),
                "Precio unitario": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.divider()
    st.subheader("Registrar precio real")

    clientes = distribucion_service.clientes()
    if not clientes:
        st.info("No hay clientes registrados para asignar un precio.")
        return

    opciones = {f"{c['nombre']} ({c['pais']})": c["id"] for c in clientes}
    with st.form("form_precio_real", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cliente_label = c1.selectbox("Cliente", list(opciones.keys()))
        moneda = c2.selectbox("Moneda", ["USD", "EUR", "COP"])

        c3, c4 = st.columns(2)
        cajas = c3.number_input("Cajas", min_value=0, value=0, step=1)
        precio_unitario = c4.number_input(
            "Precio unitario", min_value=0.0, value=0.0, step=0.01, format="%.2f"
        )

        consecutivo_ne = st.text_input("Consecutivo NE")
        observaciones = st.text_input("Observaciones (opcional)")

        enviado = st.form_submit_button("Registrar", type="primary")

    if enviado:
        if cajas <= 0 or precio_unitario <= 0:
            st.warning("Cajas y precio unitario deben ser mayores que cero.")
            return
        with st.spinner("Registrando precio real…"):
            try:
                ventas_service.registrar_precio_real(
                    codigo,
                    opciones[cliente_label],
                    int(cajas),
                    float(precio_unitario),
                    moneda,
                    consecutivo_ne,
                    observaciones or "",
                )
            except Exception as e:  # pragma: no cover — UX necesita el detalle
                st.error(f"Error registrando el precio: {e}")
                raise
        st.success(
            f"✅ Precio real registrado para {cliente_label} en {codigo}: "
            f"{int(cajas):,} cajas × {precio_unitario:.2f} {moneda}.".replace(
                ",", "."
            )
        )
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Resumen + plano
# ─────────────────────────────────────────────────────────────────────────────
def _tab_resumen_plano(contenedores: list[str]) -> None:
    resumen = ventas_service.resumen_ventas()
    if not resumen:
        st.info("Aún no hay resumen de ventas.")
    else:
        df = pd.DataFrame(resumen)
        df["ingreso_estimado_fmt"] = [
            _fmt_dinero(r.get("ingreso_estimado"), r.get("moneda"))
            for r in resumen
        ]
        df_show = df.rename(
            columns={
                "codigo": "Contenedor",
                "moneda": "Moneda",
                "clientes": "Clientes",
                "cajas": "Cajas",
                "ingreso_estimado_fmt": "Ingreso estimado",
            }
        )
        cols = ["Contenedor", "Moneda", "Clientes", "Cajas", "Ingreso estimado"]
        cols = [c for c in cols if c in df_show.columns]
        st.dataframe(
            df_show[cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Clientes": st.column_config.NumberColumn(format="%.0f"),
                "Cajas": st.column_config.NumberColumn(format="%.0f"),
            },
        )

    st.divider()
    st.subheader("Plano de facturación")
    codigo = st.selectbox("Contenedor", contenedores, key="plano_cont")
    try:
        csv_bytes = ventas_service.plano_facturacion(codigo)
        st.download_button(
            "Descargar plano de facturación (CSV)",
            data=csv_bytes,
            file_name=f"Facturacion {codigo}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    except Exception as e:  # pragma: no cover — UX necesita el detalle
        st.error(f"No se pudo generar el plano de facturación: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de formato
# ─────────────────────────────────────────────────────────────────────────────
def _fmt_fecha(valor) -> str:
    """Fecha a dd/mm/aaaa. Acepta date/datetime/str/None."""
    if valor is None or valor == "":
        return ""
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    try:
        return pd.to_datetime(valor).strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def _fmt_dinero(valor, moneda) -> str:
    """Formatea un monto según la moneda. COP con miles colombianos; USD/EUR con 2 decimales."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    mon = (moneda or "").upper()
    if mon == "COP":
        return "$" + f"{n:,.0f}".replace(",", ".")
    if mon == "EUR":
        return "€" + f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if mon == "USD":
        return "US$" + f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    # Sin moneda conocida: formato colombiano sin símbolo
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
