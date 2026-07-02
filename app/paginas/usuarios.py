"""Página admin: Usuarios y permisos (patrón NexFresh).

El login lo hace Microsoft 365 (Entra ID / Easy Auth). Acá el admin controla
QUIÉN puede entrar, quién es admin, y qué secciones ve cada usuario no-admin.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.servicios import usuarios_service as us


def _fmt_fecha(v) -> str:
    try:
        return pd.to_datetime(v).strftime("%d/%m/%Y %H:%M") if v is not None else "—"
    except (ValueError, TypeError):
        return "—"


def render(user: dict, secciones: list[str]) -> None:
    st.title("⚙️ Usuarios y permisos")
    st.caption(
        "El ingreso se valida con la clave de Microsoft 365 (Entra ID). Acá defines "
        "quién puede entrar, quién administra y qué secciones ve cada usuario. Los "
        "usuarios se auto-registran en su primer ingreso."
    )

    usuarios = us.listar()

    # ─── Tabla de usuarios ──────────────────────────────────────────────────
    if usuarios:
        df = pd.DataFrame(usuarios)
        df["ultimo_login"] = df["ultimo_login"].map(_fmt_fecha)
        df = df.rename(columns={
            "email": "Correo", "nombre": "Nombre", "es_admin": "Admin",
            "activo": "Activo", "ultimo_login": "Último ingreso", "secciones": "# Secciones",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay usuarios registrados.")

    st.divider()

    # ─── Alta de usuario ────────────────────────────────────────────────────
    st.subheader("Agregar / actualizar usuario")
    with st.form("alta_usuario"):
        c1, c2, c3 = st.columns([3, 3, 1])
        email = c1.text_input("Correo Microsoft 365", placeholder="persona@gruposanjose.com.co")
        nombre = c2.text_input("Nombre")
        admin = c3.checkbox("Admin")
        ok = st.form_submit_button("Guardar usuario", type="primary")
    if ok and email:
        us.alta(email, nombre or None, admin)
        st.success(f"Usuario {email.lower()} guardado.")
        st.rerun()

    st.divider()

    # ─── Editar permisos de un usuario ──────────────────────────────────────
    st.subheader("Permisos por usuario")
    emails = [u["email"] for u in usuarios if not u["es_admin"]]
    if not emails:
        st.info("Los administradores ven todas las secciones. Agrega usuarios no-admin "
                "para asignarles secciones específicas.")
        return

    sel = st.selectbox("Usuario (no admin)", emails)
    actuales = us.permisos(sel)
    elegidas = st.multiselect(
        "Secciones que puede ver",
        [s for s in secciones if s != "Inicio"],
        default=[s for s in secciones if s in actuales],
    )
    colp1, colp2 = st.columns([1, 1])
    if colp1.button("Guardar permisos", type="primary"):
        us.guardar_permisos(sel, elegidas)
        st.success(f"Permisos de {sel} actualizados.")
        st.rerun()
    with colp2:
        act = next((u["activo"] for u in usuarios if u["email"] == sel), True)
        if st.button("Desactivar" if act else "Activar"):
            us.set_activo(sel, not act)
            st.rerun()
