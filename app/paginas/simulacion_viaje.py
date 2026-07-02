"""Página: Simulación de viaje — tablero de calidad de la fruta en frío.

Réplica del tablero Power BI: arriba las 3 gráficas que determinan qué tan bien
o mal llega la fruta y cuánto afecta a los contenedores:
  1. VOLUMEN de exportación por semana.
  2. INCIDENCIA (% de muestras con defecto) por semana.
  3. SEVERIDAD promedio por semana.
Abajo: top de eventos/defectos y detalle.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.brand import COLORS
from app.servicios import simulacion_service as sv


def _fmt_miles(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def render(user: dict) -> None:
    st.title("Simulación de viaje")
    st.caption(
        "Tablero de calidad de la fruta en frío. Las 3 gráficas de arriba muestran "
        "el volumen exportado, la incidencia de defectos y la severidad promedio "
        "por semana — indican qué tan bien o mal llega la fruta y cuánto afecta a los contenedores."
    )

    anios = sv.anios()
    if not anios:
        st.info("No hay datos de simulación de viaje cargados todavía.")
        return

    anio = st.selectbox("Año", anios, index=0)

    k = sv.kpis(anio)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Volumen export", f"{_fmt_miles(k['volumen'])} kg")
    c2.metric("Incidencia promedio", f"{k['incidencia']:.1f} %".replace(".", ","))
    c3.metric("Severidad promedio", f"{k['severidad']:.2f}".replace(".", ","))
    c4.metric("Semanas con muestra", k["semanas"])

    st.divider()

    # ─── Las 3 gráficas (una fila) ──────────────────────────────────────────
    g1, g2, g3 = st.columns(3)

    with g1:
        st.markdown("**1 · Volumen por semana**")
        vol = sv.volumen_por_semana(anio)
        if vol:
            df = pd.DataFrame(vol)
            fig = px.bar(df, x="semana", y="volumen",
                         labels={"semana": "Semana", "volumen": "Kg export"},
                         color_discrete_sequence=[COLORS["primary"]])
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de volumen.")

    with g2:
        st.markdown("**2 · Incidencia (% defecto) por semana**")
        inc = sv.incidencia_por_semana(anio)
        if inc:
            df = pd.DataFrame(inc)
            fig = px.line(df, x="semana", y="incidencia_pct", markers=True,
                          labels={"semana": "Semana", "incidencia_pct": "% incidencia"},
                          color_discrete_sequence=[COLORS["coral"]])
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de incidencia.")

    with g3:
        st.markdown("**3 · Severidad promedio por semana**")
        sev = sv.severidad_por_semana(anio)
        if sev:
            df = pd.DataFrame(sev)
            fig = px.line(df, x="semana", y="severidad", markers=True,
                          labels={"semana": "Semana", "severidad": "Severidad"},
                          color_discrete_sequence=[COLORS["magenta"]])
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de severidad.")

    st.divider()

    # ─── Top de eventos/defectos ────────────────────────────────────────────
    st.subheader("Eventos / defectos más frecuentes")
    ev = sv.eventos_top(anio, limite=15)
    if ev:
        dfe = pd.DataFrame(ev)
        col_a, col_b = st.columns([3, 2])
        with col_a:
            fig = px.bar(dfe.sort_values("cantidad"), x="cantidad", y="evento",
                         orientation="h", labels={"cantidad": "Cantidad", "evento": ""},
                         color_discrete_sequence=[COLORS["coral"]])
            fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            dfe_show = dfe.copy()
            dfe_show["pct_promedio"] = (dfe_show["pct_promedio"].astype(float) * 100).round(2)
            dfe_show = dfe_show.rename(columns={
                "evento": "Evento", "muestras": "Muestras",
                "cantidad": "Cantidad", "pct_promedio": "% prom",
            })
            st.dataframe(dfe_show, use_container_width=True, hide_index=True)
    else:
        st.info("Sin eventos registrados para el año.")

    st.divider()

    # ─── Detalle ────────────────────────────────────────────────────────────
    with st.expander("Ver detalle de muestras"):
        semanas_disp = sorted({d["semana"] for d in sv.detalle(anio)})
        sem = st.selectbox("Semana (opcional)", ["Todas"] + semanas_disp, index=0)
        det = sv.detalle(anio, None if sem == "Todas" else int(sem))
        if det:
            dfd = pd.DataFrame(det)
            for col in ("fecha_inspeccion",):
                if col in dfd:
                    dfd[col] = pd.to_datetime(dfd[col], errors="coerce").dt.strftime("%d/%m/%Y")
            st.dataframe(dfd, use_container_width=True, hide_index=True)
        else:
            st.info("Sin muestras.")
