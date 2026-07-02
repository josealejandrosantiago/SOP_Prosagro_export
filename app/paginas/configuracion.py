"""Página: Configuración.

Visor de catálogos maestros (solo lectura por ahora). Lee la BD directo con
`get_conn` + pandas y muestra cada tabla en su propia pestaña. Productores y
Precio fruta traen un filtro de texto (zona/lote/nombre).

Tablas expuestas:
  prosagro.zonas | prosagro.productores | prosagro.precio_fruta
  prosagro.clientes | prosagro.proveedores
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.brand import COLORS  # noqa: F401  (mantiene el estilo de la app)
from conexion import get_conn


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _consultar(sql: str) -> pd.DataFrame:
    """Corre un SELECT y devuelve un DataFrame. Nunca revienta la página."""
    try:
        with get_conn() as conn:
            return pd.read_sql_query(sql, conn)
    except Exception as e:  # pragma: no cover — UX necesita el detalle
        st.error(f"No se pudo consultar la BD: {e}")
        return pd.DataFrame()


def _fmt_fechas(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """Formatea columnas de fecha a dd/mm/aaaa (deja NULL como '—')."""
    for col in columnas:
        if col in df.columns:
            df[col] = (
                pd.to_datetime(df[col], errors="coerce")
                .dt.strftime("%d/%m/%Y")
                .fillna("—")
            )
    return df


def _filtrar_texto(df: pd.DataFrame, texto: str, columnas: list[str]) -> pd.DataFrame:
    """Filtra filas donde `texto` aparezca (case-insensitive) en alguna columna."""
    texto = (texto or "").strip()
    if not texto or df.empty:
        return df
    cols = [c for c in columnas if c in df.columns]
    if not cols:
        return df
    mask = pd.Series(False, index=df.index)
    for c in cols:
        mask |= df[c].astype(str).str.contains(texto, case=False, na=False)
    return df[mask]


def _mostrar_tabla(df: pd.DataFrame, singular: str, plural: str) -> None:
    """Muestra el conteo y el dataframe, o un info si no hay datos."""
    if df.empty:
        st.info(f"No hay {plural} registrados en la BD.")
        return
    st.metric(f"Total {plural}", f"{len(df):,}".replace(",", "."))
    st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Página
# ─────────────────────────────────────────────────────────────────────────────
def render(user: dict) -> None:
    st.title("Configuración")
    st.caption(
        "Visor de catálogos maestros del sistema (zonas, productores, precios, "
        "clientes y proveedores). Por ahora es **solo lectura**: para modificar "
        "un dato se re-importa el documento fuente o se ajusta en la BD."
    )

    tab_zonas, tab_prod, tab_precio, tab_cli, tab_prov = st.tabs(
        ["Zonas", "Productores", "Precio fruta", "Clientes", "Proveedores"]
    )

    with tab_zonas:
        _tab_zonas()
    with tab_prod:
        _tab_productores()
    with tab_precio:
        _tab_precio_fruta()
    with tab_cli:
        _tab_clientes()
    with tab_prov:
        _tab_proveedores()


# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
def _tab_zonas() -> None:
    st.subheader("Zonas")
    df = _consultar(
        """
        SELECT codigo_interno   AS "Código interno",
               codigo_externo   AS "Código externo",
               nombre           AS "Nombre",
               fruta_dominante  AS "Fruta dominante",
               creado_en        AS "Creado"
          FROM prosagro.zonas
         ORDER BY nombre
        """
    )
    df = _fmt_fechas(df, ["Creado"])
    _mostrar_tabla(df, "zona", "zonas")


def _tab_productores() -> None:
    st.subheader("Productores")
    df = _consultar(
        """
        SELECT zona                  AS "Zona",
               lote                  AS "Lote",
               nombre_finca          AS "Finca",
               propietario           AS "Propietario",
               documento             AS "Documento",
               telefono              AS "Teléfono",
               ubicacion             AS "Ubicación",
               requiere_retencion    AS "Retención",
               facturacion_electronica AS "Fact. electrónica",
               fecha_vigencia_desde  AS "Vigente desde",
               fecha_vigencia_hasta  AS "Vigente hasta"
          FROM prosagro.productores
         ORDER BY zona, lote, fecha_vigencia_desde DESC
        """
    )
    df = _fmt_fechas(df, ["Vigente desde", "Vigente hasta"])

    texto = st.text_input(
        "Filtrar (zona / lote / finca / propietario / documento)",
        key="cfg_filtro_productores",
        placeholder="Ej: Urrao, LT-05, María...",
    )
    df_f = _filtrar_texto(
        df, texto, ["Zona", "Lote", "Finca", "Propietario", "Documento"]
    )
    _mostrar_tabla(df_f, "productor", "productores")


def _tab_precio_fruta() -> None:
    st.subheader("Precio fruta")
    df = _consultar(
        """
        SELECT zona                  AS "Zona",
               lote                  AS "Lote",
               precio_expo           AS "Precio expo",
               precio_nal            AS "Precio nacional",
               precio_desh           AS "Precio deshidratado",
               dias_pago             AS "Días pago",
               moneda                AS "Moneda",
               consolidar_canastillas AS "Consolidar canast.",
               pagar_canastillas     AS "Pagar canast.",
               fecha_vigencia_desde  AS "Vigente desde",
               fecha_vigencia_hasta  AS "Vigente hasta"
          FROM prosagro.precio_fruta
         ORDER BY zona, lote, fecha_vigencia_desde DESC
        """
    )
    df = _fmt_fechas(df, ["Vigente desde", "Vigente hasta"])

    texto = st.text_input(
        "Filtrar (zona / lote / moneda)",
        key="cfg_filtro_precio",
        placeholder="Ej: Oriente, LT-12, COP...",
    )
    df_f = _filtrar_texto(df, texto, ["Zona", "Lote", "Moneda"])
    _mostrar_tabla(df_f, "precio", "precios")


def _tab_clientes() -> None:
    st.subheader("Clientes")
    df = _consultar(
        """
        SELECT nombre         AS "Nombre",
               vat            AS "VAT",
               pais           AS "País",
               correo         AS "Correo",
               activo         AS "Activo",
               creado_en      AS "Creado"
          FROM prosagro.clientes
         ORDER BY nombre
        """
    )
    df = _fmt_fechas(df, ["Creado"])
    _mostrar_tabla(df, "cliente", "clientes")


def _tab_proveedores() -> None:
    st.subheader("Proveedores")
    df = _consultar(
        """
        SELECT nombre         AS "Nombre",
               nit            AS "NIT",
               tipo           AS "Tipo",
               activo         AS "Activo",
               creado_en      AS "Creado"
          FROM prosagro.proveedores
         ORDER BY nombre
        """
    )
    df = _fmt_fechas(df, ["Creado"])
    _mostrar_tabla(df, "proveedor", "proveedores")
