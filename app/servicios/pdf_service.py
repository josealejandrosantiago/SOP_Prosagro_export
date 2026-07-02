"""Generación de PDFs de liquidación (reportlab).

Reemplaza la exportación a PDF de la plantilla Excel 'Liquidación productor'
del VBA (frmLiquidarproductores). Todas las fechas en dd/mm/aaaa (Colombia)
y los valores con separador de miles colombiano.
"""
from __future__ import annotations

import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

AZUL = colors.HexColor("#1FA4DB")
AZUL_SOFT = colors.HexColor("#DCEFF9")
INK = colors.HexColor("#1F2937")


def _fecha(v) -> str:
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%d/%m/%Y")
    return "" if v is None else str(v)


def _cop(v) -> str:
    try:
        return f"${float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def _num(v, dec=0) -> str:
    try:
        s = f"{float(v):,.{dec}f}"
        # separador de miles colombiano: punto miles, coma decimal
        if dec:
            ent, frac = s.split(".")
            return ent.replace(",", ".") + "," + frac
        return s.replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _pct(v) -> str:
    try:
        return f"{float(v) * 100:.1f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "0%"


def liquidacion_productor_pdf(
    propietario: str,
    documento: str,
    anio: int,
    semana: int,
    detalle: list[dict],
    observaciones: str = "",
) -> bytes:
    """Devuelve el PDF (bytes) de la liquidación de un productor en una semana."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(letter),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=f"Liquidación {propietario} S{semana} {anio}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=AZUL, fontSize=18)
    normal = ParagraphStyle("n", parent=styles["Normal"], textColor=INK, fontSize=9)
    small = ParagraphStyle("s", parent=styles["Normal"], textColor=colors.grey, fontSize=8)

    elems = []
    elems.append(Paragraph("Prosagro Export — Liquidación de fruta", h1))
    elems.append(Paragraph(
        f"<b>Productor:</b> {propietario} &nbsp;&nbsp; "
        f"<b>Documento:</b> {documento or '—'} &nbsp;&nbsp; "
        f"<b>Semana:</b> {semana} / {anio}", normal))
    elems.append(Spacer(1, 6 * mm))

    # Cabecera de la tabla
    header = [
        "Lote", "Fecha ingreso", "Fecha pago", "Canast.", "Kg total",
        "Kg expo", "% expo", "$ unit expo", "$ expo",
        "Kg nal+desh", "% n+d", "$ nal+desh", "Total $",
        "Ashofrucol", "Retefuente", "A girar",
    ]
    data = [header]
    tot = {k: 0.0 for k in ("kg_total", "kg_expo", "expo", "nal", "total", "ash", "rete", "girar", "canast")}
    for d in detalle:
        data.append([
            f"{d.get('zona','')}-{d.get('lote','')}",
            _fecha(d.get("fecha_ingreso")),
            _fecha(d.get("fecha_pago")),
            _num(d.get("canastillas")),
            _num(d.get("kg_total")),
            _num(d.get("kg_expo_real")),
            _pct(d.get("pct_expo")),
            _cop(d.get("precio_expo")),
            _cop(d.get("costo_total_expo")),
            _num(d.get("kg_nal_desh")),
            _pct(d.get("pct_nal_desh")),
            _cop(d.get("costo_nal_desh")),
            _cop(d.get("costo_total")),
            _cop(d.get("ashofrucol")),
            _cop(d.get("retencion_fuente")),
            _cop(d.get("valor_girar")),
        ])
        tot["kg_total"] += float(d.get("kg_total") or 0)
        tot["kg_expo"] += float(d.get("kg_expo_real") or 0)
        tot["expo"] += float(d.get("costo_total_expo") or 0)
        tot["nal"] += float(d.get("costo_nal_desh") or 0)
        tot["total"] += float(d.get("costo_total") or 0)
        tot["ash"] += float(d.get("ashofrucol") or 0)
        tot["rete"] += float(d.get("retencion_fuente") or 0)
        tot["girar"] += float(d.get("valor_girar") or 0)
        tot["canast"] += float(d.get("canastillas") or 0)

    data.append([
        "TOTAL", "", "", _num(tot["canast"]), _num(tot["kg_total"]),
        _num(tot["kg_expo"]), "", "", _cop(tot["expo"]),
        "", "", _cop(tot["nal"]), _cop(tot["total"]),
        _cop(tot["ash"]), _cop(tot["rete"]), _cop(tot["girar"]),
    ])

    tabla = Table(data, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (2, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, -1), (-1, -1), AZUL_SOFT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elems.append(tabla)
    elems.append(Spacer(1, 6 * mm))

    elems.append(Paragraph(
        f"<b>Valor total a girar: {_cop(tot['girar'])}</b>", normal))
    if observaciones:
        elems.append(Spacer(1, 4 * mm))
        elems.append(Paragraph(f"<b>Observaciones:</b> {observaciones}", small))
    elems.append(Spacer(1, 8 * mm))
    elems.append(Paragraph(
        f"Generado el {dt.date.today().strftime('%d/%m/%Y')} por SOP Prosagro Export.", small))

    doc.build(elems)
    return buf.getvalue()
