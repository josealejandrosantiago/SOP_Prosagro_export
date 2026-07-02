"""Página: SOP — Costeo por contenedor.

El corazón del sistema. Reúne el costeo real por contenedor:
  - KPIs globales (contenedores, kg export, costo fruta, costo total,
    ingreso real, margen) de `sop_service.totales_globales()`.
  - Tabla principal de todos los contenedores con costos formateados.
  - Detalle de un contenedor: resumen (metrics) + trazas por lote.

Ojo: fruta y certificación ya se calculan; logístico, insumos y precios de
venta se completan al cargar esos módulos. Ingreso (USD/EUR) y costo (COP)
pueden estar en monedas distintas — el margen requiere TRM (pendiente).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS
from app.servicios import sop_service


def render(user: dict) -> None:
    st.title("SOP — Costeo por contenedor")
    st.caption(
        "El costo de fruta y certificación ya se calculan; costos logísticos, "
        "insumos y precios de venta se completan al cargar esos módulos."
    )

    contenedores = sop_service.contenedores_sop()
    if not contenedores:
        st.info("Aún no hay contenedores con costeo cargado en BD.")
        return

    _bloque_kpis()

    st.warning(
        "⚠ El ingreso puede venir en USD/EUR y el costo en COP: el **margen** "
        "aún NO convierte monedas — requiere la TRM (pendiente)."
    )

    st.divider()
    _bloque_tabla(contenedores)

    st.divider()
    _bloque_detalle(contenedores)


# ─────────────────────────────────────────────────────────────────────────────
# Bloques de UI
# ─────────────────────────────────────────────────────────────────────────────
def _bloque_kpis() -> None:
    tot = sop_service.totales_globales()
    c1, c2, c3 = st.columns(3)
    c1.metric("Contenedores", f"{_int(tot.get('contenedores'))}")
    c2.metric("Kg export", _fmt_kg(tot.get("kg_export")))
    c3.metric("Costo fruta", _fmt_pesos(tot.get("costo_fruta")))
    c4, c5, c6 = st.columns(3)
    c4.metric("Costo total", _fmt_pesos(tot.get("costo_total")))
    c5.metric("Ingreso real", _fmt_pesos(tot.get("ingreso_real")))
    c6.metric("Margen", _fmt_pesos(tot.get("margen")))


def _bloque_tabla(contenedores: list[dict]) -> None:
    st.subheader("Contenedores")
    df = pd.DataFrame(
        [
            {
                "Contenedor": c.get("codigo"),
                "Kg export": _num(c.get("kg_export")),
                "Cajas": _num(c.get("cajas")),
                "Pallets": _num(c.get("pallets")),
                "Costo fruta": _num(c.get("costo_fruta")),
                "Costo certif": _num(c.get("costo_certif")),
                "Costo logístico": _num(c.get("costo_logistico")),
                "Costo total": _num(c.get("costo_total")),
                "$/kg": _num(c.get("costo_por_kg")),
                "$/caja": _num(c.get("costo_por_caja")),
            }
            for c in contenedores
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Kg export": st.column_config.NumberColumn(format="%.0f"),
            "Cajas": st.column_config.NumberColumn(format="%.0f"),
            "Pallets": st.column_config.NumberColumn(format="%.0f"),
            "Costo fruta": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo certif": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo logístico": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo total": st.column_config.NumberColumn(format="$ %.0f"),
            "$/kg": st.column_config.NumberColumn(format="$ %.0f"),
            "$/caja": st.column_config.NumberColumn(format="$ %.0f"),
        },
    )


def _bloque_detalle(contenedores: list[dict]) -> None:
    st.subheader("Detalle por contenedor")
    codigos = [c.get("codigo") for c in contenedores]
    codigo = st.selectbox("Elegir contenedor", codigos, key="sop_codigo")

    detalle = sop_service.detalle_sop(codigo)
    resumen = (detalle or {}).get("resumen") or {}
    trazas = (detalle or {}).get("trazas") or []

    if not resumen and not trazas:
        st.info(f"El contenedor {codigo} no tiene detalle cargado.")
        return

    # Resumen del contenedor (metrics)
    fecha = resumen.get("fecha_cargue")
    armado = resumen.get("armado_completo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kg export", _fmt_kg(resumen.get("kg_export")))
    c2.metric("Cajas", f"{_int(resumen.get('cajas'))}")
    c3.metric("Pallets", f"{_int(resumen.get('pallets'))}")
    c4.metric("Costo total", _fmt_pesos(resumen.get("costo_total")))
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Costo fruta", _fmt_pesos(resumen.get("costo_fruta")))
    c6.metric("Costo certif", _fmt_pesos(resumen.get("costo_certif")))
    c7.metric("$/kg", _fmt_pesos(resumen.get("costo_por_kg")))
    c8.metric("$/caja", _fmt_pesos(resumen.get("costo_por_caja")))

    meta = []
    if fecha:
        meta.append(f"Fecha de cargue: **{_fmt_fecha(fecha)}**")
    if armado is not None:
        meta.append(f"Armado completo: **{'Sí' if armado else 'No'}**")
    if meta:
        st.caption(" · ".join(meta))

    # Tabla de trazas
    if not trazas:
        st.info("El contenedor no tiene trazas de fruta cargadas.")
        return

    st.markdown("**Trazas del contenedor**")
    df = pd.DataFrame(
        [
            {
                "Trazabilidad": t.get("trazabilidad"),
                "Zona-lote": _zona_lote(t),
                "Predio": t.get("predio"),
                "Calibre": t.get("calibre_num"),
                "Cajas": _num(t.get("cajas")),
                "Kg": _num(t.get("kg")),
                "Precio expo": _num(t.get("precio_expo")),
                "Costo fruta": _num(t.get("costo_fruta")),
            }
            for t in trazas
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Calibre": st.column_config.NumberColumn(format="%.0f"),
            "Cajas": st.column_config.NumberColumn(format="%.0f"),
            "Kg": st.column_config.NumberColumn(format="%.0f"),
            "Precio expo": st.column_config.NumberColumn(format="$ %.0f"),
            "Costo fruta": st.column_config.NumberColumn(format="$ %.0f"),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de formato
# ─────────────────────────────────────────────────────────────────────────────
def _zona_lote(t: dict) -> str:
    zona = t.get("zona")
    lote = t.get("lote")
    partes = [str(p) for p in (zona, lote) if p not in (None, "")]
    return "-".join(partes)


def _num(valor):
    """A float para que st.dataframe pueda ordenar y formatear. None → None."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _int(valor) -> str:
    """Entero con miles colombianos: 1.234. None → 0."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        return "0"
    return f"{n:,.0f}".replace(",", ".")


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
