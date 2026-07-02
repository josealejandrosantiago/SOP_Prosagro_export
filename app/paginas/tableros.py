"""Página: Tableros (réplica del Power BI).

Dashboard de solo lectura que consulta la BD directo (sin pasar por los
servicios de negocio) para dibujar KPIs y gráficos con plotly. Tres
subpestañas:

  - Resumen global : KPIs + kg por semana + costo por semana + kg por zona.
  - Causales       : kg afectado por severidad y por causal (top 10).
  - Contenedores   : tabla con kg_export y % cruzado por contenedor.

Todo se lee sobre `prosagro.kg_consolidado`, `prosagro.causales_rechazo`
y `prosagro.contenedores`. Está blindado para funcionar aunque cualquiera
de esas tablas esté vacía (se muestra st.info en vez de reventar).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.brand import COLORS
from conexion import get_conn


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de formato (Colombia)
# ─────────────────────────────────────────────────────────────────────────────
def _miles(valor: float, prefijo: str = "") -> str:
    """Formatea un número con separador de miles colombiano (punto)."""
    try:
        entero = f"{float(valor):,.0f}"
    except (TypeError, ValueError):
        return f"{prefijo}0"
    return f"{prefijo}{entero.replace(',', '.')}"


def _leer_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve un DataFrame. Si la tabla no existe o
    algo falla, devuelve un DataFrame vacío (la página nunca revienta)."""
    try:
        with get_conn() as conn:
            return pd.read_sql(sql, conn, params=params)
    except Exception as e:  # pragma: no cover — UX: preferimos "sin datos" a caerse
        st.warning(f"No se pudo consultar la BD: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Entrada
# ─────────────────────────────────────────────────────────────────────────────
def render(user: dict) -> None:
    st.title("Tableros")
    st.caption(
        "Réplica del Power BI: indicadores y gráficos de solo lectura sobre "
        "el consolidado de kilos, las causales de rechazo y los contenedores."
    )

    tab_global, tab_causales, tab_contenedores = st.tabs(
        ["Resumen global", "Causales", "Contenedores"]
    )

    with tab_global:
        _tab_resumen_global()
    with tab_causales:
        _tab_causales()
    with tab_contenedores:
        _tab_contenedores()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Resumen global
# ─────────────────────────────────────────────────────────────────────────────
def _tab_resumen_global() -> None:
    # KPIs globales sobre TODO el histórico de kg_consolidado.
    kpis = _leer_df(
        """
        SELECT
            COUNT(*)                              AS trazas,
            COALESCE(SUM(kg_total), 0)            AS kg_total,
            COALESCE(SUM(kg_expo_real), 0)        AS kg_expo,
            COALESCE(SUM(costo_total_expo
                         + costo_total_nal
                         + costo_total_desh), 0)  AS costo_total
        FROM prosagro.kg_consolidado
        """
    )

    if kpis.empty or int(kpis.iloc[0]["trazas"]) == 0:
        st.info("Aún no hay datos en `kg_consolidado`. Cargá una semana en "
                "**Ingreso de fruta** y reconstruí el consolidado.")
        return

    fila = kpis.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trazabilidades", _miles(fila["trazas"]))
    c2.metric("Kg total",       f"{_miles(fila['kg_total'])} kg")
    c3.metric("Kg exportación",  f"{_miles(fila['kg_expo'])} kg")
    c4.metric("Costo total",    _miles(fila["costo_total"], prefijo="$"))

    # Año más reciente para los gráficos por semana.
    anios = _leer_df(
        "SELECT DISTINCT anio FROM prosagro.kg_consolidado ORDER BY anio DESC"
    )
    if anios.empty:
        st.info("No hay años cargados para graficar por semana.")
        return
    anio_reciente = int(anios.iloc[0]["anio"])

    st.divider()
    st.subheader(f"Comportamiento semanal · año {anio_reciente}")

    semanal = _leer_df(
        """
        SELECT
            semana,
            COALESCE(SUM(kg_total), 0)           AS kg_total,
            COALESCE(SUM(costo_total_expo
                         + costo_total_nal
                         + costo_total_desh), 0) AS costo_total
        FROM prosagro.kg_consolidado
        WHERE anio = %s
        GROUP BY semana
        ORDER BY semana
        """,
        (anio_reciente,),
    )

    if semanal.empty:
        st.info(f"Sin movimiento cargado para el año {anio_reciente}.")
    else:
        semanal["semana"] = semanal["semana"].astype(int)
        semanal["kg_total"] = semanal["kg_total"].astype(float)
        semanal["costo_total"] = semanal["costo_total"].astype(float)
        semanal["Semana"] = "S" + semanal["semana"].astype(str)

        col_a, col_b = st.columns(2)

        with col_a:
            fig_kg = px.bar(
                semanal,
                x="Semana",
                y="kg_total",
                title="Kg total por semana",
                labels={"kg_total": "Kg total", "Semana": "Semana"},
                color_discrete_sequence=[COLORS["primary"]],
            )
            fig_kg.update_layout(margin=dict(t=48, b=10, l=10, r=10))
            st.plotly_chart(fig_kg, use_container_width=True)

        with col_b:
            fig_costo = px.line(
                semanal,
                x="Semana",
                y="costo_total",
                title="Costo total por semana",
                labels={"costo_total": "Costo total ($)", "Semana": "Semana"},
                markers=True,
                color_discrete_sequence=[COLORS["magenta"]],
            )
            fig_costo.update_layout(margin=dict(t=48, b=10, l=10, r=10))
            st.plotly_chart(fig_costo, use_container_width=True)

    st.divider()
    st.subheader("Distribución de kilos por zona (histórico)")

    zonas = _leer_df(
        """
        SELECT
            COALESCE(NULLIF(TRIM(zona), ''), 'Sin zona') AS zona,
            COALESCE(SUM(kg_total), 0)                   AS kg_total
        FROM prosagro.kg_consolidado
        GROUP BY COALESCE(NULLIF(TRIM(zona), ''), 'Sin zona')
        HAVING COALESCE(SUM(kg_total), 0) > 0
        ORDER BY kg_total DESC
        """
    )

    if zonas.empty:
        st.info("No hay kilos por zona para mostrar.")
    else:
        zonas["kg_total"] = zonas["kg_total"].astype(float)
        fig_zona = px.pie(
            zonas,
            names="zona",
            values="kg_total",
            title="Participación de kg por zona",
            hole=0.4,
        )
        fig_zona.update_traces(textposition="inside", textinfo="percent+label")
        fig_zona.update_layout(margin=dict(t=48, b=10, l=10, r=10))
        st.plotly_chart(fig_zona, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Causales
# ─────────────────────────────────────────────────────────────────────────────
def _tab_causales() -> None:
    st.subheader("Causales de rechazo")

    por_sev = _leer_df(
        """
        SELECT
            COALESCE(NULLIF(TRIM(severidad), ''), 'Sin severidad') AS severidad,
            COALESCE(SUM(kg_con_causal), 0)                        AS kg_con_causal
        FROM prosagro.causales_rechazo
        GROUP BY COALESCE(NULLIF(TRIM(severidad), ''), 'Sin severidad')
        HAVING COALESCE(SUM(kg_con_causal), 0) > 0
        ORDER BY kg_con_causal DESC
        """
    )

    if por_sev.empty:
        st.info("No hay causales de rechazo cargadas todavía. Cargá un reporte "
                "de calidad en el módulo de **Causales**.")
        return

    por_sev["kg_con_causal"] = por_sev["kg_con_causal"].astype(float)

    col_a, col_b = st.columns(2)

    with col_a:
        fig_sev = px.bar(
            por_sev,
            x="severidad",
            y="kg_con_causal",
            title="Kg afectado por severidad",
            labels={"kg_con_causal": "Kg con causal", "severidad": "Severidad"},
            color="severidad",
            color_discrete_sequence=[
                COLORS["coral"], COLORS["yellow"], COLORS["lime"],
                COLORS["magenta"], COLORS["secondary"],
            ],
        )
        fig_sev.update_layout(margin=dict(t=48, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig_sev, use_container_width=True)

    por_causal = _leer_df(
        """
        SELECT
            COALESCE(NULLIF(TRIM(causal), ''), 'Sin causal') AS causal,
            COALESCE(SUM(kg_con_causal), 0)                  AS kg_con_causal
        FROM prosagro.causales_rechazo
        GROUP BY COALESCE(NULLIF(TRIM(causal), ''), 'Sin causal')
        HAVING COALESCE(SUM(kg_con_causal), 0) > 0
        ORDER BY kg_con_causal DESC
        LIMIT 10
        """
    )

    with col_b:
        if por_causal.empty:
            st.info("Sin causales individuales para el top 10.")
        else:
            por_causal["kg_con_causal"] = por_causal["kg_con_causal"].astype(float)
            # Orden ascendente para que la barra más grande quede arriba (horizontal).
            por_causal = por_causal.sort_values("kg_con_causal", ascending=True)
            fig_causal = px.bar(
                por_causal,
                x="kg_con_causal",
                y="causal",
                orientation="h",
                title="Top 10 causales por kg afectado",
                labels={"kg_con_causal": "Kg con causal", "causal": "Causal"},
                color_discrete_sequence=[COLORS["magenta"]],
            )
            fig_causal.update_layout(margin=dict(t=48, b=10, l=10, r=10))
            st.plotly_chart(fig_causal, use_container_width=True)

    # Tabla de apoyo con miles formateados.
    st.divider()
    tabla = por_sev.copy()
    tabla["Kg con causal"] = tabla["kg_con_causal"].apply(_miles)
    tabla = tabla.rename(columns={"severidad": "Severidad"})[["Severidad", "Kg con causal"]]
    st.dataframe(tabla, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Contenedores
# ─────────────────────────────────────────────────────────────────────────────
def _tab_contenedores() -> None:
    st.subheader("Contenedores")

    df = _leer_df(
        """
        SELECT
            c.codigo,
            c.warehouse,
            c.eta,
            c.fecha_cargue,
            c.armado_completo,
            COALESCE(c.total_pallets, 0)                                        AS total_pallets,
            COALESCE(c.total_cajas, 0)                                          AS total_cajas,
            (SELECT COALESCE(SUM(e.total_kg_netos), 0)
             FROM prosagro.fruta_export e
             WHERE e.contenedor_codigo = c.codigo)                             AS kg_export,
            (SELECT COUNT(*)
             FROM prosagro.pallets_detalle pd
             WHERE pd.contenedor_id = c.id)                                    AS pallets_filas,
            (SELECT COUNT(*)
             FROM prosagro.pallets_detalle pd
             WHERE pd.contenedor_id = c.id AND pd.estado_cruce = 'CRUZADO')    AS pallets_cruzados
        FROM prosagro.contenedores c
        ORDER BY c.codigo
        """
    )

    if df.empty:
        st.info("No hay contenedores cargados todavía. Subí un packing list en "
                "el módulo de **Contenedores**.")
        return

    df["kg_export"] = df["kg_export"].astype(float)
    df["pallets_filas"] = df["pallets_filas"].astype(int)
    df["pallets_cruzados"] = df["pallets_cruzados"].astype(int)

    # KPIs cabecera.
    c1, c2, c3 = st.columns(3)
    c1.metric("Contenedores", _miles(len(df)))
    c2.metric("Kg exportación total", f"{_miles(df['kg_export'].sum())} kg")
    c3.metric("Armados completos", _miles(int(df["armado_completo"].fillna(False).sum())))

    # % cruzado por contenedor (usando el detalle de pallets; si no hay detalle,
    # cae al flag armado_completo para no mostrar 0% engañoso).
    def _pct_cruzado(row) -> float:
        if row["pallets_filas"] > 0:
            return round(100.0 * row["pallets_cruzados"] / row["pallets_filas"], 1)
        return 100.0 if bool(row["armado_completo"]) else 0.0

    df["pct_cruzado"] = df.apply(_pct_cruzado, axis=1)

    # Presentación: fechas dd/mm/aaaa y miles colombianos.
    vista = pd.DataFrame({
        "Contenedor":  df["codigo"],
        "Bodega":      df["warehouse"].fillna("—"),
        "ETA":         _fechas(df["eta"]),
        "Cargue":      _fechas(df["fecha_cargue"]),
        "Armado":      df["armado_completo"].map(
                           lambda v: "Completo" if bool(v) else "Parcial"),
        "Pallets":     df["total_pallets"].astype(int).map(_miles),
        "Cajas":       df["total_cajas"].astype(int).map(_miles),
        "Kg export":   df["kg_export"].map(lambda v: f"{_miles(v)} kg"),
        "% cruzado":   df["pct_cruzado"].map(lambda v: f"{v:.1f}%"),
    })

    st.dataframe(vista, use_container_width=True, hide_index=True)

    st.divider()
    # Gráfico de kg_export por contenedor (solo los que tienen kg).
    con_kg = df[df["kg_export"] > 0].sort_values("kg_export", ascending=False)
    if con_kg.empty:
        st.info("Ningún contenedor tiene kg de exportación cruzados todavía.")
    else:
        fig = px.bar(
            con_kg,
            x="codigo",
            y="kg_export",
            title="Kg de exportación por contenedor",
            labels={"kg_export": "Kg export", "codigo": "Contenedor"},
            color_discrete_sequence=[COLORS["coral"]],
        )
        fig.update_layout(margin=dict(t=48, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)


def _fechas(serie: pd.Series) -> pd.Series:
    """Convierte una serie de fechas a dd/mm/aaaa (o '—' si es nula)."""
    fechas = pd.to_datetime(serie, errors="coerce")
    return fechas.map(lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "—")
