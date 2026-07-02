"""Página: Liquidación productores.

Tres pestañas:
  1. Liquidación semanal — totales + productores de la semana, detalle por
     productor, PDF de liquidación y registro de envío por Twilio.
  2. Informe de pago — informe agrupado por fecha de pago en un rango de semanas.
  3. Planos PyA — genera cuentas de cobro / factura electrónica, exporta el
     plano CSV y persiste los documentos en BD.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import (
    liquidacion_service,
    pdf_service,
    pya_service,
    twilio_service,
)


def render(user: dict) -> None:
    st.title("Liquidación productores")
    st.caption(
        "Liquidación semanal por productor, informe de pago por rango de "
        "semanas y generación de los planos PyA (cuentas de cobro / factura "
        "electrónica) para SIIGO."
    )

    anios = liquidacion_service.anios_disponibles()
    if not anios:
        st.info("Aún no hay liquidaciones cargadas en BD.")
        return

    tab_sem, tab_pago, tab_pya = st.tabs(
        ["Liquidación semanal", "Informe de pago", "Planos PyA"]
    )

    with tab_sem:
        _tab_liquidacion_semanal(anios, user)

    with tab_pago:
        _tab_informe_pago(anios)

    with tab_pya:
        _tab_planos_pya(anios)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Liquidación semanal
# ─────────────────────────────────────────────────────────────────────────────
def _tab_liquidacion_semanal(anios: list[int], user: dict) -> None:
    c1, c2 = st.columns(2)
    anio = c1.selectbox("Año", anios, key="sem_anio")
    semanas = liquidacion_service.semanas_de_anio(anio)
    if not semanas:
        st.info(f"No hay semanas cargadas para {anio}.")
        return
    semana = c2.selectbox("Semana", semanas, key="sem_semana")

    totales = liquidacion_service.totales_semana(anio, semana)
    m1, m2, m3 = st.columns(3)
    m1.metric("Productores", f"{totales['productores']:,.0f}".replace(",", "."))
    m2.metric("Kg expo", _fmt_kg(totales["kg_expo"]))
    m3.metric("Valor a girar", _fmt_pesos(totales["valor_girar"]))

    productores = liquidacion_service.productores_de_semana(anio, semana)
    if not productores:
        st.info(f"No hay productores para la semana {semana} / {anio}.")
        return

    st.subheader("Productores de la semana")
    df_prod = pd.DataFrame(productores)
    df_prod_show = df_prod.rename(
        columns={
            "propietario": "Propietario",
            "documento": "Documento",
            "telefono": "Teléfono",
            "lotes": "Lotes",
            "kg_total": "Kg total",
            "kg_expo": "Kg expo",
            "costo_total": "Costo total",
            "ashofrucol": "Asohofrucol",
            "retencion": "Retención",
            "valor_girar": "Valor a girar",
        }
    )
    st.dataframe(
        df_prod_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Kg total": st.column_config.NumberColumn(format="%.0f"),
            "Kg expo": st.column_config.NumberColumn(format="%.0f"),
            "Costo total": st.column_config.NumberColumn(format="$ %.0f"),
            "Asohofrucol": st.column_config.NumberColumn(format="$ %.0f"),
            "Retención": st.column_config.NumberColumn(format="$ %.0f"),
            "Valor a girar": st.column_config.NumberColumn(format="$ %.0f"),
        },
    )

    st.divider()
    st.subheader("Detalle por productor")
    props = [p["propietario"] for p in productores]
    propietario = st.selectbox("Elegir productor", props, key="sem_propietario")

    prod_sel = next(p for p in productores if p["propietario"] == propietario)
    documento = prod_sel.get("documento", "")
    telefono = prod_sel.get("telefono", "")

    detalle = liquidacion_service.detalle_productor(anio, semana, propietario)
    if not detalle:
        st.info("El productor no tiene detalle en esta semana.")
        return

    df_det = pd.DataFrame(detalle)
    for col in ("fecha_ingreso", "fecha_procesamiento", "fecha_pago"):
        if col in df_det.columns:
            df_det[col] = df_det[col].apply(_fmt_fecha)
    df_det_show = df_det.rename(
        columns={
            "trazabilidad": "Trazabilidad",
            "zona": "Zona",
            "lote": "Lote",
            "nombre_finca": "Finca",
            "fecha_ingreso": "F. ingreso",
            "fecha_procesamiento": "F. proceso",
            "fecha_pago": "F. pago",
            "canastillas": "Canastillas",
            "kg_total": "Kg total",
            "kg_expo_real": "Kg expo",
            "pct_expo": "% expo",
            "precio_expo": "Precio expo",
            "costo_total_expo": "Costo expo",
            "kg_nal_desh": "Kg nal/desh",
            "pct_nal_desh": "% nal/desh",
            "precio_nal": "Precio nal",
            "costo_nal_desh": "Costo nal/desh",
            "costo_total": "Costo total",
            "ashofrucol": "Asohofrucol",
            "retencion_fuente": "Retención",
            "valor_girar": "Valor a girar",
        }
    )
    st.dataframe(df_det_show, use_container_width=True, hide_index=True)

    # KPIs del productor (sumados del detalle)
    tot_expo = sum(float(d.get("kg_expo_real", 0) or 0) for d in detalle)
    tot_girar = sum(float(d.get("valor_girar", 0) or 0) for d in detalle)
    k1, k2, k3 = st.columns(3)
    k1.metric("Trazabilidades", len(detalle))
    k2.metric("Kg expo", _fmt_kg(tot_expo))
    k3.metric("Valor a girar", _fmt_pesos(tot_girar))

    st.divider()
    observaciones = st.text_input(
        "Observaciones para el PDF (opcional)", key="sem_obs"
    )

    col_pdf, col_tw = st.columns(2)

    # PDF de liquidación
    nombre_pdf = f"Liquidacion {propietario} S{semana}.pdf"
    try:
        pdf_bytes = pdf_service.liquidacion_productor_pdf(
            propietario,
            documento,
            anio,
            semana,
            detalle,
            observaciones=observaciones or "",
        )
        col_pdf.download_button(
            "Descargar PDF de liquidación",
            data=pdf_bytes,
            file_name=nombre_pdf,
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:  # pragma: no cover — UX necesita el detalle
        col_pdf.error(f"No se pudo generar el PDF: {e}")

    # Registro de envío Twilio
    if col_tw.button(
        "Registrar envío Twilio",
        use_container_width=True,
        help="Registra el envío de la liquidación al WhatsApp/SMS del productor.",
    ):
        if not telefono:
            st.warning("El productor no tiene teléfono registrado.")
        else:
            with st.spinner("Registrando envío…"):
                res = twilio_service.registrar_envio(
                    propietario,
                    telefono,
                    "LIQUIDACION",
                    nombre_pdf,
                )
            _mostrar_resultado_twilio(res)


def _mostrar_resultado_twilio(res: dict) -> None:
    estado = res.get("estado", "desconocido")
    if res.get("error"):
        st.error(f"Error registrando envío: {res['error']}")
        return
    if res.get("stub"):
        st.warning(
            f"Envío registrado en modo STUB (Twilio no configurado). "
            f"Estado: {estado}, id: {res.get('id')}."
        )
    else:
        st.success(
            f"✅ Envío registrado. Estado: {estado}, id: {res.get('id')}."
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Informe de pago
# ─────────────────────────────────────────────────────────────────────────────
def _tab_informe_pago(anios: list[int]) -> None:
    anio = st.selectbox("Año", anios, key="pago_anio")
    semanas = liquidacion_service.semanas_de_anio(anio)
    if not semanas:
        st.info(f"No hay semanas cargadas para {anio}.")
        return

    s_min, s_max = min(semanas), max(semanas)
    if s_min == s_max:
        semana_desde = semana_hasta = s_min
        st.caption(f"Única semana disponible: {s_min}.")
    else:
        semana_desde, semana_hasta = st.slider(
            "Rango de semanas",
            min_value=s_min,
            max_value=s_max,
            value=(s_min, s_max),
            key="pago_rango",
        )

    informe = liquidacion_service.informe_pago(anio, semana_desde, semana_hasta)
    if not informe:
        st.info(
            f"No hay pagos en el rango semanas {semana_desde}–{semana_hasta} "
            f"de {anio}."
        )
        return

    df = pd.DataFrame(informe)
    if "fecha_pago" in df.columns:
        df["fecha_pago"] = df["fecha_pago"].apply(_fmt_fecha)

    total_girar = sum(float(r.get("valor_girar", 0) or 0) for r in informe)
    c1, c2 = st.columns(2)
    c1.metric("Registros", len(informe))
    c2.metric("Total a girar", _fmt_pesos(total_girar))

    # Agrupado por fecha de pago
    st.subheader("Detalle por fecha de pago")
    for fecha in _orden_fechas(df):
        sub = df[df["fecha_pago"] == fecha]
        sub_girar = sum(float(v or 0) for v in sub["valor_girar"])
        with st.expander(
            f"Pago {fecha} — {len(sub)} productores — "
            f"{_fmt_pesos(sub_girar)}",
            expanded=(len(_orden_fechas(df)) == 1),
        ):
            sub_show = sub.rename(
                columns={
                    "fecha_pago": "F. pago",
                    "propietario": "Propietario",
                    "documento": "Documento",
                    "lotes": "Lotes",
                    "costo_expo": "Costo expo",
                    "costo_nal": "Costo nal",
                    "costo_desh": "Costo desh",
                    "costo_total": "Costo total",
                    "ashofrucol": "Asohofrucol",
                    "retencion": "Retención",
                    "valor_girar": "Valor a girar",
                }
            )
            st.dataframe(
                sub_show,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Costo expo": st.column_config.NumberColumn(format="$ %.0f"),
                    "Costo nal": st.column_config.NumberColumn(format="$ %.0f"),
                    "Costo desh": st.column_config.NumberColumn(format="$ %.0f"),
                    "Costo total": st.column_config.NumberColumn(format="$ %.0f"),
                    "Asohofrucol": st.column_config.NumberColumn(format="$ %.0f"),
                    "Retención": st.column_config.NumberColumn(format="$ %.0f"),
                    "Valor a girar": st.column_config.NumberColumn(format="$ %.0f"),
                },
            )


def _orden_fechas(df: pd.DataFrame) -> list[str]:
    """Fechas únicas preservando el orden de aparición (ya vienen dd/mm/aaaa)."""
    seen: list[str] = []
    for f in df["fecha_pago"]:
        if f not in seen:
            seen.append(f)
    return seen


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Planos PyA
# ─────────────────────────────────────────────────────────────────────────────
def _tab_planos_pya(anios: list[int]) -> None:
    c1, c2 = st.columns(2)
    anio = c1.selectbox("Año", anios, key="pya_anio")
    semanas = liquidacion_service.semanas_de_anio(anio)
    if not semanas:
        st.info(f"No hay semanas cargadas para {anio}.")
        return
    semana = c2.selectbox("Semana", semanas, key="pya_semana")

    consecutivo = st.number_input(
        "Consecutivo inicial",
        min_value=1,
        value=1,
        step=1,
        key="pya_consecutivo",
    )
    tipo_label = st.radio(
        "Tipo de documento",
        ["Cuentas de cobro (DR_CXC)", "Factura electrónica (FE_COMPRA)"],
        key="pya_tipo",
    )
    tipo = "DR_CXC" if tipo_label.startswith("Cuentas") else "FE_COMPRA"

    if st.button("Generar", type="primary", key="pya_generar"):
        with st.spinner("Generando documentos…"):
            filas = pya_service.generar_cuentas_cobro(
                anio, semana, int(consecutivo), tipo=tipo
            )
        st.session_state["_pya_filas"] = filas

    filas = st.session_state.get("_pya_filas")
    if not filas:
        st.info("Configurá los parámetros y presioná «Generar».")
        return

    st.subheader(f"{len(filas)} documentos generados ({tipo})")
    df = pd.DataFrame(filas)
    st.dataframe(df, use_container_width=True, hide_index=True)

    col_csv, col_bd = st.columns(2)

    try:
        csv_bytes = pya_service.exportar_plano(filas)
        col_csv.download_button(
            "Descargar plano CSV",
            data=csv_bytes,
            file_name=f"Plano_{tipo}_{anio}_S{semana}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    except Exception as e:  # pragma: no cover — UX necesita el detalle
        col_csv.error(f"No se pudo exportar el plano: {e}")

    if col_bd.button(
        "Guardar en BD", use_container_width=True, key="pya_persistir"
    ):
        with st.spinner("Guardando documentos en BD…"):
            try:
                n = pya_service.persistir_documentos(filas)
            except Exception as e:  # pragma: no cover
                st.error(f"Error guardando: {e}")
                raise
        st.success(f"✅ {n} documentos persistidos en BD.")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de formato
# ─────────────────────────────────────────────────────────────────────────────
def _fmt_fecha(valor) -> str:
    """Fecha a dd/mm/aaaa. Acepta date/datetime/str/None."""
    if valor is None or valor == "":
        return ""
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    # str: intentar parsear ISO yyyy-mm-dd; si no, devolver tal cual
    try:
        return pd.to_datetime(valor).strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def _fmt_pesos(valor) -> str:
    """Miles estilo colombiano: $1.234.567."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        return "$0"
    return "$" + f"{n:,.0f}".replace(",", ".")


def _fmt_kg(valor) -> str:
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        return "0 kg"
    return f"{n:,.0f}".replace(",", ".") + " kg"
