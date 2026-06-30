"""Login placeholder — usuario y clave en .env, hash con bcrypt.

Sustituir por Azure AD cuando el tenant esté listo. Mismo patrón que NexFresh:
una sola sesión por navegador, validación contra `usuarios` en BD.
"""
from __future__ import annotations

import os
import bcrypt
import streamlit as st

from conexion import get_conn


def _hash_pwd(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def _check_pwd(plain: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def ensure_default_user() -> None:
    """Si la tabla usuarios tiene el placeholder __SET_BY_APP__, lo reemplaza
    por el hash de APP_PASSWORD_HASH (texto plano en .env, lo hasheamos al vuelo).
    """
    plain = os.environ.get("APP_PASSWORD_HASH", "").strip()
    email = os.environ.get("APP_USER", "").strip()
    if not plain or not email:
        return
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT password_hash FROM prosagro.usuarios WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
        if row and row[0] == "__SET_BY_APP__":
            cur.execute(
                "UPDATE prosagro.usuarios SET password_hash = %s WHERE email = %s",
                (_hash_pwd(plain).decode("utf-8"), email),
            )
            conn.commit()


def login_form() -> dict | None:
    """Muestra el form y devuelve el usuario autenticado (dict) o None."""
    if "user" in st.session_state:
        return st.session_state["user"]

    st.markdown("### Iniciar sesión")
    with st.form("login_form"):
        email = st.text_input("Correo", value=os.environ.get("APP_USER", ""))
        pwd = st.text_input("Clave", type="password")
        ok = st.form_submit_button("Entrar", type="primary")
    if not ok:
        return None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email, nombre, password_hash, rol, activo
            FROM prosagro.usuarios
            WHERE email = %s
            """,
            (email,),
        )
        row = cur.fetchone()

    if not row:
        st.error("Usuario no encontrado")
        return None
    uid, uemail, nombre, phash, rol, activo = row
    if not activo:
        st.error("Usuario inactivo")
        return None
    if not _check_pwd(pwd, phash):
        st.error("Clave incorrecta")
        return None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE prosagro.usuarios SET ultimo_login = now() WHERE id = %s",
            (uid,),
        )
        conn.commit()

    user = {"id": uid, "email": uemail, "nombre": nombre, "rol": rol}
    st.session_state["user"] = user
    st.rerun()
    return user
