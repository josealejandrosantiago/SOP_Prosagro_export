"""SOP Prosagro Export — punto de entrada Streamlit.

Sigue el mismo patrón que `nexfresh-sop`: una sola app con navegación lateral.
Las páginas se irán llenando fase por fase.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Para poder importar `conexion.py` y `app.*` desde el root del repo
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.brand import COLORS, MODULE_COLORS, img_b64, streamlit_css  # noqa: E402
from app.auth import ensure_default_user, login_form  # noqa: E402

st.set_page_config(
    page_title="SOP Prosagro Export",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Imagen de fondo (plántulas) — busca varios nombres/extensiones posibles.
BRAND_DIR = ROOT / "app" / "assets" / "brand"
_bg_b64 = None
_bg_mime = "image/jpeg"
for _cand in ("fondo-plantulas.jpg", "fondo-plantulas.png", "fondo.jpg", "fondo.png"):
    _b64 = img_b64(BRAND_DIR / _cand)
    if _b64:
        _bg_b64 = _b64
        _bg_mime = "image/png" if _cand.endswith(".png") else "image/jpeg"
        break

st.markdown(streamlit_css(bg_b64=_bg_b64, bg_mime=_bg_mime), unsafe_allow_html=True)

# Bootstrap del usuario admin local si .env trae APP_PASSWORD_HASH.
try:
    ensure_default_user()
except Exception as e:  # pragma: no cover — fallar suave en el primer arranque
    st.warning(f"No pude bootstrap del usuario admin: {e}")

# ────────────────────────────── Login ────────────────────────────────────────
user = login_form()
if not user:
    st.stop()

# ────────────────────────────── Sidebar ──────────────────────────────────────
with st.sidebar:
    # Logo de Prosagro debajo de la barra azul. Busca varios nombres posibles.
    _logo_path = None
    for _lc in ("logo-prosagro.png", "logo-vertical.png", "logo.png"):
        if (BRAND_DIR / _lc).exists():
            _logo_path = BRAND_DIR / _lc
            break
    if _logo_path:
        # Logo a ~mitad de ancho del sidebar, centrado.
        _lc1, _lc2 = st.columns([1, 1])
        with _lc1:
            st.image(str(_logo_path), use_container_width=True)
    else:
        st.markdown(
            f"<h2 style='color:{COLORS['primary']};margin:0'>Prosagro</h2>"
            f"<p style='color:{COLORS['secondary']};margin:0'>export</p>",
            unsafe_allow_html=True,
        )

    st.divider()
    seccion = st.radio(
        "Módulo",
        [
            "Inicio",
            "Ingreso de fruta",
            "Liquidación productores",
            "Causales de rechazo",
            "Contenedores",
            "SOP (costeo)",
            "GGN / Certificación",
            "Distribución a clientes",
            "Ventas",
            "Costos logísticos",
            "Proyección de fruta",
            "Tableros",
            "Configuración",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"Sesión: **{user['nombre']}**")
    if st.button("Cerrar sesión", use_container_width=True):
        del st.session_state["user"]
        st.rerun()

# ────────────────────────────── Contenido ────────────────────────────────────
def _pendiente(modulo: str, fase: str, descripcion: str) -> None:
    color = MODULE_COLORS.get(modulo, COLORS["primary"])
    st.markdown(
        f"<div style='border-left:6px solid {color}; padding:12px 16px; "
        f"background:#F8FAFC; border-radius:6px'>"
        f"<b>{modulo.title()}</b><br/>"
        f"<small style='color:{COLORS['muted']}'>{fase}</small><br/>"
        f"<p style='margin-top:8px'>{descripcion}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


if seccion == "Inicio":
    st.title("SOP Prosagro Export")
    st.caption("Sistema de costeo y rentabilidad por contenedor")
    st.markdown(
        f"<p style='color:{COLORS['muted']}'>Bienvenido, "
        f"<b>{user['nombre']}</b>. Esta es la app que reemplaza las dos macros "
        f"VBA (base de datos gulupa + consolidación costos y ventas).</p>",
        unsafe_allow_html=True,
    )

    # Resumen de estado de la BD
    from conexion import get_conn

    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM prosagro.zonas")
            zonas = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM prosagro.productores")
            productores = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM prosagro.ingresos")
            ingresos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM prosagro.kg_consolidado")
            kgc = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM prosagro.contenedores")
            cont = cur.fetchone()[0]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Zonas",              zonas)
        c2.metric("Productores",        productores)
        c3.metric("Ingresos cargados",  ingresos)
        c4.metric("Kg consolidado",     kgc)
        c5.metric("Contenedores",       cont)
    except Exception as e:
        st.error(f"No pude consultar la BD: {e}")
        st.info("Verifica que aplicaste las migraciones: `bash scripts/aplicar_migraciones.sh`")

    st.divider()
    st.markdown("### Roadmap")
    st.markdown(
        "- ✅ **Fase 0** — Esquema BD + app base (esta pantalla)\n"
        "- 🚧 **Fase 1** — Ingreso de fruta\n"
        "- ⏳ **Fase 2** — Liquidación productores + Twilio + PyA\n"
        "- ⏳ **Fase 3** — Causales + contenedor + GGN\n"
        "- ⏳ **Fase 4** — Simulación + Proyección + Tableros Power BI\n"
        "- ⏳ **Fase 5** — SOP / Costos / Distribución / Packing list / Ventas\n"
        "- ⏳ **Fase 6** — Bandeja correo + cruce auto facturas\n"
        "- ⏳ **Fase 7** — Monetizaciones + Cash flow + PyG"
    )

elif seccion == "Ingreso de fruta":
    from app.paginas import ingreso_fruta
    ingreso_fruta.render(user)
elif seccion == "Liquidación productores":
    from app.paginas import liquidacion
    liquidacion.render(user)
elif seccion == "Causales de rechazo":
    from app.paginas import causales
    causales.render(user)
elif seccion == "Contenedores":
    from app.paginas import contenedores
    contenedores.render(user)
elif seccion == "SOP (costeo)":
    from app.paginas import sop
    sop.render(user)
elif seccion == "GGN / Certificación":
    from app.paginas import ggn
    ggn.render(user)
elif seccion == "Distribución a clientes":
    from app.paginas import distribucion
    distribucion.render(user)
elif seccion == "Ventas":
    from app.paginas import ventas
    ventas.render(user)
elif seccion == "Costos logísticos":
    _pendiente("costos", "Fase 5/6", "Costos pronosticados (tarifas de últimos N contenedores) + "
               "costos reales con cruce automático de facturas recibidas por correo.")
elif seccion == "Proyección de fruta":
    _pendiente("proyeccion", "Fase 4", "Mantener la proyección por zona/lote/semana con los "
               "kg reales conforme se procesa.")
elif seccion == "Tableros":
    from app.paginas import tableros
    tableros.render(user)
elif seccion == "Configuración":
    from app.paginas import configuracion
    configuracion.render(user)
