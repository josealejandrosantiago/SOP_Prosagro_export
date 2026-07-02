"""Envío de reportes a productores por Twilio (WhatsApp/SMS).

Reemplaza el flujo Power Automate del VBA. Si no hay credenciales Twilio en el
entorno, funciona en modo STUB: registra el envío en la tabla `envio_twilio`
con estado PENDIENTE (para que quede el audit trail) pero no envía nada. Cuando
se configuren TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_WHATSAPP, envía
de verdad.
"""
from __future__ import annotations

import os
import re

from conexion import get_conn


def _normalizar_telefono(tel: str | None) -> str | None:
    if not tel:
        return None
    # tomar el primer número si vienen varios separados por ; ,
    tel = re.split(r"[;,]", str(tel))[0].strip()
    digits = re.sub(r"\D", "", tel)
    if not digits:
        return None
    # asumir Colombia (+57) si viene sin indicativo y son 10 dígitos
    if len(digits) == 10:
        digits = "57" + digits
    return "+" + digits


def _hay_credenciales() -> bool:
    return bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN"))


def registrar_envio(
    propietario: str,
    telefono: str | None,
    tipo_documento: str,
    alias_pdf: str,
    url_pdf: str | None = None,
    mensaje: str | None = None,
) -> dict:
    """Registra (y si hay credenciales, envía) un reporte a un productor.
    Devuelve {estado, id, error}."""
    tel = _normalizar_telefono(telefono)
    canal = "whatsapp"
    estado = "PENDIENTE"
    twilio_sid = None
    error = None

    if _hay_credenciales() and tel and url_pdf:
        try:
            from twilio.rest import Client  # import perezoso
            client = Client(
                os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
            )
            from_wa = os.environ.get("TWILIO_FROM_WHATSAPP")
            msg = client.messages.create(
                from_=f"whatsapp:{from_wa}",
                to=f"whatsapp:{tel}",
                body=mensaje or f"Reporte de producción — {propietario}",
                media_url=[url_pdf],
            )
            twilio_sid = msg.sid
            estado = "ENVIADO"
        except Exception as e:  # pragma: no cover
            estado = "ERROR"
            error = str(e)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prosagro.envio_twilio
                (propietario, telefono, canal, tipo_documento, alias_pdf,
                 url_pdf, mensaje, twilio_sid, estado, error_msg, enviado_en)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'ENVIADO' THEN now() ELSE NULL END)
            RETURNING id
            """,
            (propietario, tel, canal, tipo_documento, alias_pdf, url_pdf,
             mensaje, twilio_sid, estado, error, estado),
        )
        eid = cur.fetchone()[0]
        conn.commit()

    return {"estado": estado, "id": eid, "error": error, "stub": not _hay_credenciales()}


def historial_envios(limite: int = 100) -> list[dict]:
    with get_conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT propietario, telefono, tipo_documento, alias_pdf, estado,
                   error_msg, enviado_en, creado_en
            FROM prosagro.envio_twilio
            ORDER BY creado_en DESC
            LIMIT %s
            """,
            (limite,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
