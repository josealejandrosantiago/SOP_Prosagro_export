"""Paleta y constantes de marca de Prosagro Export.

Los valores hex de aquí se aplican via CSS en `app.py` para que toda la
interfaz comparta colores con el manual de marca.
"""
from __future__ import annotations

import base64
from pathlib import Path

# Paleta primaria — extraída del logotipo y patrón de marca.
COLORS = {
    "primary":      "#1FA4DB",   # azul Prosagro (barra superior)
    "primary_soft": "#DCEFF9",   # azul clarito (menú lateral)
    "secondary":    "#159FDB",   # cyan complementario
    "magenta":      "#E91A6B",   # acento / badges
    "yellow":       "#FFD400",   # warnings
    "coral":        "#EE4D3A",   # errores
    "lime":         "#76C043",   # éxitos
    "green_dark":   "#3F8C2E",   # categoría fruta
    "white":        "#FFFFFF",
    "ink":          "#1F2937",   # texto principal
    "muted":        "#6B7280",   # texto secundario
    "bg":           "#F8FAFC",   # fondo
}

# Mapeo módulo → color (cada módulo hereda un color del patrón de marca).
MODULE_COLORS = {
    "ingreso":          COLORS["magenta"],
    "liquidacion":      COLORS["yellow"],
    "contenedor":       COLORS["coral"],
    "ggn":              COLORS["lime"],
    "causales":         COLORS["magenta"],
    "ventas":           COLORS["secondary"],
    "costos":           COLORS["green_dark"],
    "proyeccion":       COLORS["primary"],
}


def img_b64(path: str | Path) -> str | None:
    """Devuelve la imagen como base64 (o None si no existe). Para incrustar
    en CSS sin depender de archivos servidos (funciona igual en el contenedor)."""
    p = Path(path)
    if not p.exists():
        return None
    return base64.b64encode(p.read_bytes()).decode("ascii")


def streamlit_css(bg_b64: str | None = None, bg_mime: str = "image/jpeg") -> str:
    """CSS para inyectar en la app de Streamlit (st.markdown unsafe_allow_html).

    bg_b64: imagen de fondo (plántulas) en base64. Si se pasa, se muestra
            muy tenue detrás de todo el contenido.
    """
    c = COLORS

    # Bloque de fondo (solo si hay imagen). Un velo blanco al 92% lo deja tenue.
    fondo_css = ""
    if bg_b64:
        fondo_css = f"""
      [data-testid="stAppViewContainer"] {{
        background-image:
          linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.94)),
          url("data:{bg_mime};base64,{bg_b64}");
        background-size: cover;
        background-position: center center;
        background-attachment: fixed;
        background-repeat: no-repeat;
      }}
      /* Tarjeta blanca semitransparente para que el texto se lea bien */
      [data-testid="stMain"] .block-container {{
        background: rgba(255,255,255,0.80);
        border-radius: 14px;
        padding: 2rem 2.5rem 3rem 2.5rem;
        margin-top: 1rem;
        box-shadow: 0 1px 12px rgba(31,41,55,0.06);
      }}
        """

    return f"""
    <style>
      :root {{
        --color-primary:      {c['primary']};
        --color-primary-soft: {c['primary_soft']};
        --color-secondary:    {c['secondary']};
        --color-magenta:      {c['magenta']};
        --color-yellow:       {c['yellow']};
        --color-coral:        {c['coral']};
        --color-lime:         {c['lime']};
        --color-ink:          {c['ink']};
        --color-muted:        {c['muted']};
      }}

      /* Barra superior azul fuerte */
      header[data-testid="stHeader"] {{
        background-color: var(--color-primary) !important;
      }}

      /* Menú lateral en azul clarito, sin franja de colores */
      section[data-testid="stSidebar"] {{
        background-color: var(--color-primary-soft);
        border-right: 1px solid rgba(31,164,219,0.30);
      }}
      section[data-testid="stSidebar"] > div {{
        background-color: transparent;
      }}
      /* Texto del menú un poco más oscuro para contraste sobre el azul clarito */
      section[data-testid="stSidebar"] label,
      section[data-testid="stSidebar"] .stRadio div {{
        color: var(--color-ink);
      }}

      {fondo_css}

      /* Botones primarios */
      .stButton > button[kind="primary"] {{
        background-color: var(--color-primary);
        border-color: var(--color-primary);
      }}
      .stButton > button[kind="primary"]:hover {{
        background-color: var(--color-secondary);
        border-color: var(--color-secondary);
      }}
    </style>
    """
