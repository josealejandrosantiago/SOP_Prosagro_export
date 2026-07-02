"""Página: Simulación de viaje — tablero de calidad de la fruta (réplica Power BI).

Las 3 gráficas por lote van ALINEADAS verticalmente (mismo lote en la misma
columna): volumen arriba, simulación en medio, severidad abajo → se lee un lote
de arriba a abajo de un vistazo. Filtros por zona (Urrao/San José/Oriente) y
lote. El panel semanal + escala de evaluación va al final.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.brand import COLORS
from app.servicios import simulacion_service as sv

_COLOR_EVENTO = {
    "BUEN ESTADO": COLORS["lime"],
    "ANTRACNOSIS": COLORS["coral"],
    "DESIDRATADA": COLORS["yellow"],
    "DESHIDRATADA": COLORS["yellow"],
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


def _titulo(txt: str):
    st.markdown(
        f"<div style='background:{COLORS['primary']};color:#fff;text-align:center;"
        f"font-weight:700;padding:4px;border-radius:6px;font-size:0.9rem;margin-bottom:2px'>{txt}</div>",
        unsafe_allow_html=True,
    )


def render(user: dict) -> None:
    st.title("Simulación de viaje")

    anios = sv.anios()
    if not anios:
        st.info("No hay datos de simulación de viaje cargados.")
        return

    # ─── Filtros ────────────────────────────────────────────────────────────
    fc = st.columns([1, 1, 1.3, 1])
    anio = fc[0].selectbox("Año", anios, index=0)
    sems = sv.semanas(anio)
    if not sems:
        st.info("No hay semanas con muestras para el año.")
        return
    semana = fc[1].selectbox("Semana", sems, index=len(sems) - 1)
    zona_nom = fc[2].selectbox("Zona", ["Todas", "Urrao", "San José", "Oriente"], index=0)
    zona = None if zona_nom == "Todas" else zona_nom
    lotes_disp = sv.lotes_disponibles(anio, semana, zona)
    lote_sel = fc[3].selectbox("Lote", ["Todos"] + lotes_disp, index=0)
    lote = None if lote_sel == "Todos" else lote_sel

    # Lista maestra de lotes → eje X idéntico y alineado en las 3 gráficas
    lotes_master = sv.lotes_de(anio, semana, zona, lote)
    if not lotes_master:
        st.info("No hay muestras para el filtro seleccionado.")
        return

    ALTURA = 210  # pequeñas para que quepan las 3 en una pantalla

    def _fijar_x(fig):
        fig.update_xaxes(categoryorder="array", categoryarray=lotes_master, tickangle=-45)
        fig.update_layout(height=ALTURA, margin=dict(l=0, r=0, t=6, b=0))

    # ══════════ 1 · VOLUMEN por lote ══════════
    _titulo("Volumen de exportación por lote (Kg)")
    vpl = sv.volumen_por_lote(anio, semana, zona, lote)
    if vpl:
        df = pd.DataFrame(vpl)
        fig = px.bar(df, x="zona_lote", y="volumen", text="volumen",
                     color_discrete_sequence=[COLORS["primary"]])
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        _fijar_x(fig)
        fig.update_layout(showlegend=False, yaxis_title="Kg", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True, key="vol")
    else:
        st.info("Sin volumen.")

    # ══════════ 2 · SIMULACIÓN (eventos 100% apilado) por lote ══════════
    _titulo("Simulación de viaje por lote (% del muestreo)")
    epl = sv.eventos_por_lote(anio, semana, zona, lote)
    if epl:
        df = pd.DataFrame(epl)
        df["pct"] = df.groupby("zona_lote")["cantidad"].transform(lambda s: s / s.sum() * 100)
        cmap = _color_map(sorted(df["evento"].unique()))
        fig = px.bar(df, x="zona_lote", y="pct", color="evento", text="pct",
                     color_discrete_map=cmap)
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="inside")
        _fijar_x(fig)
        fig.update_layout(barmode="stack", yaxis_title="%", xaxis_title="",
                          legend=dict(orientation="h", y=1.25, title=""))
        st.plotly_chart(fig, use_container_width=True, key="sim")
    else:
        st.info("Sin muestras de eventos.")

    # ══════════ 3 · SEVERIDAD (Antracnosis) por lote ══════════
    _titulo("Severidad Antracnosis por lote (escala 0-5)")
    spl = sv.severidad_por_lote(anio, semana, "ANTRACNOSIS", zona, lote)
    if spl:
        df = pd.DataFrame(spl)
        fig = px.bar(df, x="zona_lote", y="severidad", text="severidad",
                     color_discrete_sequence=[COLORS["primary"]])
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
        _fijar_x(fig)
        fig.update_layout(showlegend=False, yaxis=dict(range=[0, 5], title="Severidad"), xaxis_title="Zona-lote")
        st.plotly_chart(fig, use_container_width=True, key="sev")
    else:
        st.info("Sin datos de severidad (no hubo Antracnosis en el filtro).")

    st.divider()

    # ══════════ Panel semanal + escala de evaluación (al final) ══════════
    p1, p2, p3 = st.columns([1, 1, 2])
    with p1:
        _titulo("Volumen semanal")
        vs = sv.volumen_semanal(anio, zona, lote)
        if vs:
            df = pd.DataFrame(vs)
            df["sel"] = df["semana"].eq(semana)
            fig = px.bar(df, x="semana", y="volumen", color="sel",
                         color_discrete_map={True: COLORS["primary"], False: "#B9DCED"})
            fig.update_layout(height=220, margin=dict(l=0, r=0, t=6, b=0),
                              showlegend=False, xaxis_title="Sem", yaxis_title="Kg")
            st.plotly_chart(fig, use_container_width=True, key="volsem")
    with p2:
        _titulo("Simulación semanal")
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
                            text=f"{r['pct']:.0f}%", textposition="inside")
            fig.update_layout(height=220, margin=dict(l=0, r=0, t=6, b=0),
                              barmode="stack", showlegend=False, xaxis_title="Sem", yaxis_title="%")
            st.plotly_chart(fig, use_container_width=True, key="simsem")
    with p3:
        _titulo("Escala de evaluación")
        st.markdown(
            "<div style='background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;"
            "padding:8px 12px;font-size:0.82rem'>"
            + "<br>".join(sv.ESCALA_EVALUACION)
            + "</div>",
            unsafe_allow_html=True,
        )
