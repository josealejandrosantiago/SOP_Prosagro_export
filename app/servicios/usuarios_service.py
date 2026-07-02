"""Servicio de administración de usuarios y permisos (patrón NexFresh)."""
from __future__ import annotations

from conexion import get_conn


def listar() -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT u.email, u.nombre, u.es_admin, u.activo, u.ultimo_login,
                   COALESCE((SELECT COUNT(*) FROM prosagro.permisos_usuario p
                             WHERE p.email = u.email), 0) AS secciones
            FROM prosagro.usuarios_app u
            ORDER BY u.es_admin DESC, u.email
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def alta(email: str, nombre: str | None, es_admin: bool) -> None:
    email = email.strip().lower()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO prosagro.usuarios_app (email, nombre, es_admin, activo)
               VALUES (%s,%s,%s,TRUE)
               ON CONFLICT (email) DO UPDATE
                 SET nombre = COALESCE(EXCLUDED.nombre, prosagro.usuarios_app.nombre),
                     es_admin = EXCLUDED.es_admin, activo = TRUE""",
            (email, nombre, es_admin),
        )
        conn.commit()


def set_admin(email: str, es_admin: bool) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE prosagro.usuarios_app SET es_admin=%s WHERE email=%s", (es_admin, email))
        conn.commit()


def set_activo(email: str, activo: bool) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE prosagro.usuarios_app SET activo=%s WHERE email=%s", (activo, email))
        conn.commit()


def permisos(email: str) -> set[str]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute("SELECT seccion FROM prosagro.permisos_usuario WHERE email=%s", (email,))
        return {r[0] for r in cur.fetchall()}


def guardar_permisos(email: str, secciones: list[str]) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM prosagro.permisos_usuario WHERE email=%s", (email,))
        if secciones:
            cur.executemany(
                "INSERT INTO prosagro.permisos_usuario (email, seccion) VALUES (%s,%s)",
                [(email, s) for s in secciones],
            )
        conn.commit()
