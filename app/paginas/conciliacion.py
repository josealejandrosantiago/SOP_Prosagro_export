"""Página: Conciliación de facturas.

Cruza las facturas de proveedores logísticos contra el cuadro de operaciones
(cronograma). En Prosagro las operaciones salen como EXP-<consecutivo> y se
cruzan por invoice / contenedor físico / BL.

El parser de PDF/XML y la bandeja de correo (Graph) se conectan en Fase 6 —
mismo patrón que el SOP NexFresh. Por ahora: cuadro de operaciones listo para
cruzar + registro manual de facturas.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import conciliacion_service as cs


def _fmt_fecha(v) -> str:
    try:
        return pd.to_datetime(v).strftime("%d/%m/%Y") if v is not None else ""
    except (ValueError, TypeError):
        return ""


def render(user: dict) -> None:
    st.title("Conciliación de facturas")
    st.caption(
        "Cruce de facturas de proveedores logísticos contra el cuadro de operaciones "
        "(cronograma). Las operaciones salen como EXP-<consecutivo> y se cruzan por "
        "invoice, contenedor físico o BL. La bandeja de correo + parser de PDF se conecta "
        "en la siguiente fase (patrón NexFresh)."
    )

    r = cs.resumen()
    c1, c2, c3 = st.columns(3)
    c1.metric("Operaciones (cronograma)", r["operaciones"])
    c2.metric("Facturas recibidas", r["facturas"])
    c3.metric("Facturas cruzadas", r["cruzadas"])

    tab1, tab2, tab3 = st.tabs(["Cuadro de operaciones", "Buscar operación", "Registrar factura"])

    # ─── Cuadro de operaciones ──────────────────────────────────────────────
    with tab1:
        ops = cs.operaciones()
        if not ops:
            st.info("No hay operaciones cargadas en el cronograma.")
        else:
            df = pd.DataFrame(ops)
            for col in ("fecha_embarque", "fecha_llegada"):
                if col in df:
                    df[col] = df[col].map(_fmt_fecha)
            df = df.rename(columns={
                "contenedor_codigo": "OP", "exp": "EXP", "invoice": "Invoice",
                "contenedor_fisico": "Contenedor", "bl": "BL", "naviera": "Naviera",
                "puerto_destino": "Destino", "fecha_llegada": "Llegada",
                "semana_llegada": "Sem. lleg.", "importador": "Importador",
                "facturas": "# Fact.",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(ops)} operaciones. Estas son las llaves para cruzar las facturas.")

    # ─── Buscar operación ───────────────────────────────────────────────────
    with tab2:
        clave = st.text_input("Buscar por OP / EXP / invoice / contenedor físico / BL",
                              placeholder="Ej: OP-325, EXP-325, 325, TEMU9371712, SYZS116...")
        if clave:
            res = cs.buscar_operacion(clave)
            if res:
                df = pd.DataFrame(res)
                if "fecha_llegada" in df:
                    df["fecha_llegada"] = df["fecha_llegada"].map(_fmt_fecha)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("No se encontró ninguna operación con esa clave.")

    # ─── Registrar factura manual ───────────────────────────────────────────
    with tab3:
        st.markdown("Registro manual (mientras se conecta la bandeja de correo).")
        with st.form("factura_manual"):
            cont = st.text_input("Contenedor / OP a la que aplica la factura", placeholder="OP-325")
            colv1, colv2 = st.columns(2)
            valor = colv1.number_input("Valor factura", min_value=0.0, step=1000.0)
            moneda = colv2.selectbox("Moneda", ["COP", "USD", "EUR"])
            prov = st.text_input("Proveedor (opcional)")
            adj = st.text_input("Nombre del adjunto (opcional)")
            enviar = st.form_submit_button("Registrar factura", type="primary")
        if enviar and cont and valor > 0:
            fid = cs.registrar_factura_manual(cont.strip(), valor, moneda, prov or None, adj or None)
            st.success(f"Factura registrada (id {fid}).")
            st.rerun()

        st.divider()
        st.markdown("**Facturas recibidas**")
        fr = cs.facturas_recibidas()
        if fr:
            dff = pd.DataFrame(fr)
            if "fecha_recepcion" in dff:
                dff["fecha_recepcion"] = dff["fecha_recepcion"].map(_fmt_fecha)
            st.dataframe(dff, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay facturas registradas.")
