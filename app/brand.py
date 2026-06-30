"""Paleta y constantes de marca de Prosagro Export.

Los valores hex de aquí se aplican via CSS en `app.py` para que toda la
interfaz comparta colores con el manual de marca.
"""

# Paleta primaria — extraída del logotipo y patrón de marca.
COLORS = {
    "primary":      "#1FA4DB",   # azul Prosagro (del lockup "Prosagro export")
    "secondary":    "#159FDB",   # cyan complementario (sidebar bottom)
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


def streamlit_css() -> str:
    """CSS para inyectar en la app de Streamlit (st.markdown unsafe_allow_html)."""
    c = COLORS
    return f"""
    <style>
      :root {{
        --color-primary:   {c['primary']};
        --color-secondary: {c['secondary']};
        --color-magenta:   {c['magenta']};
        --color-yellow:    {c['yellow']};
        --color-coral:     {c['coral']};
        --color-lime:      {c['lime']};
        --color-ink:       {c['ink']};
        --color-muted:     {c['muted']};
      }}

      /* Topbar accent */
      header[data-testid="stHeader"] {{
        background-color: var(--color-primary) !important;
      }}

      /* Sidebar — franja vertical de marca */
      section[data-testid="stSidebar"] {{
        background-color: #FFFFFF;
        border-left: 10px solid var(--color-magenta);
        box-shadow: inset 0 -10px 0 0 var(--color-yellow),
                    inset 0 -20px 0 0 var(--color-coral),
                    inset 0 -30px 0 0 var(--color-lime),
                    inset 0 -40px 0 0 var(--color-magenta),
                    inset 0 -50px 0 0 var(--color-yellow),
                    inset 0 -60px 0 0 var(--color-secondary);
      }}

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
