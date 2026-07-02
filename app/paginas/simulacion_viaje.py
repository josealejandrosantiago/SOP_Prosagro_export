"""Página: Simulación de viaje — tablero de calidad de la fruta (réplica Power BI).

Layout (todo filtrado por semana seleccionada, discriminado por zona-lote):
  Fila 1: Volumen export por lote        | Volumen export semanal (tendencia)
  Fila 2: Simulación 100% apilada por lote | Simulación 100% apilada de la semana
  Fila 3: Severidad (Antracnosis) por lote | Escala de evaluación (0-5)
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.brand import COLORS
from app.servicios import simulacion_service as sv

# Colores de eventos: BUEN ESTADO verde, defectos en rojo/naranja/magenta
_COLOR_EVENTO = {
    "BUEN ESTADO": COLORS["lime"],
    "ANTRACNOSIS": COLORS["coral"],
    "DESIDRATADA": COLORS["yellow"],
    "DESHIDRATADA": COLORS["yellow"],
    "POForma": COLORS["magenta"],
}
_PALETA = [COLORS["coral"], COLORS["yellow"], COLORS["magenta"],
           COLORS["secondary"], COLORS["green_dark"], "#9C27B0", "#FF7043"]


def _color_map(eventos: list[str]) -> dict:
    cmap, i = {}, 0
    for ev in eventos:
        up = (ev or "").upper()
        if up == "BUEN ESTADO":
            cmap[ev] = COLORS["lime"]
        elif up in _COLOR_EVENTO:
            cmap[ev] = _COLOR_EVENTO[up]
        else:
            cmap[ev] = _PALETA[i % len(_PALETA)]
            i += 1
    return cmap


def _titulo_panel(txt: str):
    st.markdown(
        f"<div style='background:{COLORS['primary']};color:#fff;text-align:center;"
        f"font-weight:700;padding:6px;border-radius:6px 6px 0 0'>{txt}</div>",
        unsafe_allow_html=True,
    )


def render(user: dict) -> None:
    st.title("Simulación de viaje")
    st.caption(
        "Calidad de la fruta en frío por lote. Elegí la semana: el tablero muestra el "
        "volumen exportado, la distribución de eventos (Antracnosis vs Buen estado) y la "
        "severidad de la Antracnosis por lote — indica qué tan bien o mal llega la fruta."
    )

    anios = sv.anios()
    if not anios:
        st.info("No hay datos de simulación de viaje cargados.")
        return

    c_a, c_s, _ = st.columns([1, 1, 3])
    anio = c_a.selectbox("Año", anios, index=0)
    sems = sv.semanas(anio)
    if not sems:
        st.info("No hay semanas con muestras para el año.")
        return
    semana = c_s.selectbox("Semana muestra", sems, index=len(sems) - 1)

    tot = sv.totales_semana(anio, semana)
    k1, k2, k3 = st.columns(3)
    k1.metric("Volumen semana", f"{tot['volumen']:,.0f} kg".replace(",", "."))
    k2.metric("Incidencia", f"{tot['incidencia']:.1f} %".replace(".", ","))
    k3.metric("Severidad promedio", f"{tot['severidad']:.2f}".replace(".", ","))

    st.divider()

    # ══════════ FILA 1 — Volumen ══════════
    f1a, f1b = st.columns([3, 1])
    with f1a:
        _titulo_panel("Volumen de exportación discriminado por lote")
        vpl = sv.volumen_por_lote(anio, semana)
        if vpl:
            df = pd.DataFrame(vpl)
            fig = px.bar(df, x="zona_lote", y="volumen", text="volumen",
                         labels={"zona_lote": "Zona-lote", "volumen": "Volumen (Kg)"},
                         color_discrete_sequence=[COLORS["primary"]])
            fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig.update_layout(height=330, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin volumen para la semana.")
    with f1b:
        _titulo_panel("Volumen semanal")
        vs = sv.volumen_semanal(anio)
        if vs:
            df = pd.DataFrame(vs)
            df["sel"] = df["semana"].eq(semana)
            fig = px.bar(df, x="semana", y="volumen",
                         color="sel", color_discrete_map={True: COLORS["primary"], False: "#B9DCED"},
                         labels={"semana": "Semana", "volumen": "Volumen (Kg)"})
            fig.update_layout(height=330, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # ══════════ FILA 2 — Simulación (eventos 100% apilado) ══════════
    f2a, f2b = st.columns([3, 1])
    eventos_lote = sv.eventos_por_lote(anio, semana)
    with f2a:
        _titulo_panel("Simulación de viaje discriminado por lote")
        if eventos_lote:
            df = pd.DataFrame(eventos_lote)
            # % dentro de cada lote
            df["pct"] = df.groupby("zona_lote")["cantidad"].transform(lambda s: s / s.sum() * 100)
            cmap = _color_map(sorted(df["evento"].unique()))
            fig = px.bar(df, x="zona_lote", y="pct", color="evento", text="pct",
                         labels={"zona_lote": "Zona-lote", "pct": "% del muestreo", "evento": "Evento"},
                         color_discrete_map=cmap)
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
            fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0),
                              barmode="stack", legend=dict(orientation="h", y=1.15))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin muestras de eventos para la semana.")
    with f2b:
        _titulo_panel("Simulación semanal")
        es = sv.eventos_semanal(anio, semana)
        if es:
            df = pd.DataFrame(es)
            total = df["cantidad"].sum() or 1
            df["pct"] = df["cantidad"] / total * 100
            cmap = _color_map(sorted(df["evento"].unique()))
            fig = go.Figure()
            for _, r in df.iterrows():
                fig.add_bar(x=[str(semana)], y=[r["pct"]], name=r["evento"],
                            marker_color=cmap.get(r["evento"]),
                            text=f"{r['pct']:.1f}%", textposition="inside")
            fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0),
                              barmode="stack", showlegend=False,
                              xaxis_title="Semana", yaxis_title="% del muestreo")
            st.plotly_chart(fig, use_container_width=True)

    # ══════════ FILA 3 — Severidad + Escala ══════════
    f3a, f3b = st.columns([3, 2])
    with f3a:
        eventos_disp = sv.eventos_disponibles(anio, semana) or ["ANTRACNOSIS"]
        ev_sel = eventos_disp[0] if "ANTRACNOSIS" not in [e.upper() for e in eventos_disp] else \
            next(e for e in eventos_disp if e.upper() == "ANTRACNOSIS")
        _titulo_panel(f"Severidad {ev_sel}")
        spl = sv.severidad_por_lote(anio, semana, ev_sel)
        if spl:
            df = pd.DataFrame(spl)
            fig = px.bar(df, x="zona_lote", y="severidad", text="severidad",
                         labels={"zona_lote": "Zona-lote", "severidad": "Severidad promedio"},
                         color_discrete_sequence=[COLORS["primary"]])
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                              showlegend=False, yaxis=dict(range=[0, 5]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos de severidad para la semana.")
    with f3b:
        _titulo_panel("Escala de evaluación")
        st.markdown(
            "<div style='background:#F8FAFC;border:1px solid #E2E8F0;border-radius:0 0 6px 6px;"
            "padding:12px 16px;font-size:0.92rem'>"
            + "<br>".join(sv.ESCALA_EVALUACION)
            + "</div>",
            unsafe_allow_html=True,
        )
