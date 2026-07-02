"""Autenticación y control de acceso (patrón NexFresh).

Con Easy Auth / Entra ID activo en Azure, Microsoft maneja el login con la clave
corporativa de Microsoft 365 (incluido MFA) e inyecta el correo del usuario en el
header `X-MS-CLIENT-PRINCIPAL-NAME`. La app solo lee ese correo y lo valida contra
`usuarios_app`. NO se guardan claves en la app.

Transición: mientras Easy Auth no esté habilitado (header ausente), cae al login
local con bcrypt para que la app siga funcionando. Una vez habilitado Easy Auth,
el header siempre viene y el login local nunca se usa.
"""
from __future__ import annotations

import os
import bcrypt
import streamlit as st

from conexion import get_conn

# Correos que SIEMPRE son admin (anti-bloqueo, aunque los borren de la tabla).
SUPER_ADMINS = {"analistadedatos@gruposanjose.com.co"}


# ───────────────────────── Easy Auth (Entra ID / M365) ──────────────────────
def _email_easy_auth() -> str | None:
    """Correo del usuario logueado vía Easy Auth. None en local/dev."""
    try:
        email = st.context.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    except Exception:
        email = None
    return (email or "").strip().lower() or None


def _registrar_usuario(email: str, nombre: str | None = None) -> None:
    """Auto-alta en el primer ingreso (para que el admin lo vea en la lista)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO prosagro.usuarios_app (email, nombre)
               VALUES (%s, %s)
               ON CONFLICT (email) DO UPDATE SET ultimo_login = now()""",
            (email, nombre),
        )
        conn.commit()


def es_admin(email: str) -> bool:
    if email in SUPER_ADMINS:
        return True
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT es_admin FROM prosagro.usuarios_app WHERE email = %s AND activo", (email,))
        r = cur.fetchone()
    return bool(r and r[0])


def usuario_activo(email: str) -> bool:
    if email in SUPER_ADMINS:
        return True
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT activo FROM prosagro.usuarios_app WHERE email = %s", (email,))
        r = cur.fetchone()
    return bool(r and r[0])


def secciones_permitidas(email: str) -> set[str]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT seccion FROM prosagro.permisos_usuario WHERE email = %s", (email,))
        return {r[0] for r in cur.fetchall()}


# ───────────────────────── Login local (transición) ─────────────────────────
def _hash_pwd(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def _check_pwd(plain: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def ensure_default_user() -> None:
    """Bootstrap del hash local del admin (solo para el login de transición)."""
    plain = os.environ.get("APP_PASSWORD_HASH", "").strip()
    email = os.environ.get("APP_USER", "").strip()
    if not plain or not email:
        return
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT password_hash FROM prosagro.usuarios WHERE email = %s", (email,))
        row = cur.fetchone()
        if row and row[0] == "__SET_BY_APP__":
            cur.execute(
                "UPDATE prosagro.usuarios SET password_hash = %s WHERE email = %s",
                (_hash_pwd(plain).decode("utf-8"), email),
            )
            conn.commit()


def _login_form_local() -> dict | None:
    """Login local con bcrypt (solo mientras no esté Easy Auth)."""
    st.markdown("### Iniciar sesión")
    st.caption("Login temporal. Cuando quede activo el ingreso con Microsoft 365, "
               "entrarás con tu clave corporativa.")
    with st.form("login_form"):
        email = st.text_input("Correo", value=os.environ.get("APP_USER", ""))
        pwd = st.text_input("Clave", type="password")
        ok = st.form_submit_button("Entrar", type="primary")
    if not ok:
        return None
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT nombre, password_hash, activo FROM prosagro.usuarios WHERE email = %s", (email,))
        row = cur.fetchone()
    if not row or not _check_pwd(pwd, row[1]) or not row[2]:
        st.error("Correo o clave incorrectos")
        return None
    return {"email": email.lower(), "nombre": row[0]}


# ───────────────────────── Punto de entrada ─────────────────────────────────
def autenticar() -> dict | None:
    """Devuelve el usuario autenticado {email, nombre, es_admin, secciones}
    o None si no está autenticado."""
    if "user" in st.session_state:
        return st.session_state["user"]

    email = _email_easy_auth()
    nombre = None

    if email is None:
        u = _login_form_local()
        if not u:
            return None
        email = u["email"]
        nombre = u["nombre"]

    if not usuario_activo(email):
        st.error("⛔ Tu usuario no está activo. Contacta al administrador.")
        st.stop()

    _registrar_usuario(email, nombre)
    user = {
        "email": email,
        "nombre": nombre or email,
        "es_admin": es_admin(email),
        "secciones": secciones_permitidas(email),
    }
    st.session_state["user"] = user
    if _email_easy_auth() is None:
        st.rerun()
    return user


# Compat: nombre viejo usado por app.py
def login_form() -> dict | None:
    return autenticar()
