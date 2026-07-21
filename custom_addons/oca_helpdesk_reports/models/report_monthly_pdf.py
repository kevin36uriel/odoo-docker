import base64
import io
import math

from odoo import models

_MESES_ES = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

_NAVY = (18, 42, 89)
_BLUE = (59, 142, 222)
_TRACK = (228, 231, 238)
_TEXT = (55, 58, 66)

_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _format_date_es(d):
    if not d:
        return ""
    return "%d de %s de %d" % (d.day, _MESES_ES[d.month], d.year)


def _build_pie_chart_png(completed, pending, width=1400):
    """Pastel de 2 rebanadas: tickets completados vs. pendientes."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font_title = ImageFont.truetype(_FONT_BOLD, 34)
        font_label = ImageFont.truetype(_FONT_BOLD, 26)
        font_legend = ImageFont.truetype(_FONT_REGULAR, 24)
    except OSError:
        font_title = font_label = font_legend = ImageFont.load_default()

    top_pad = 96
    circle_d = 520
    bottom_pad = 90
    height = top_pad + circle_d + bottom_pad + 60

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    draw.text(
        (40, 34),
        "Tickets completados vs. pendientes",
        font=font_title,
        fill=_NAVY,
    )

    total = completed + pending
    cx, cy, r = width / 2, top_pad + circle_d / 2, circle_d / 2
    bbox = [cx - r, cy - r, cx + r, cy + r]

    def _label(angle_mid_deg, count, color):
        rad = math.radians(angle_mid_deg)
        anchor_x, anchor_y = cx + r * math.cos(rad), cy + r * math.sin(rad)
        lx, ly = cx + (r + 40) * math.cos(rad), cy + (r + 40) * math.sin(rad)
        draw.line([anchor_x, anchor_y, lx, ly], fill=color, width=3)
        text = "%d (%.0f%%)" % (count, 100.0 * count / total)
        tw = draw.textlength(text, font=font_label)
        tx = lx + 10 if math.cos(rad) >= 0 else lx - 10 - tw
        draw.text((tx, ly - 15), text, font=font_label, fill=_TEXT)

    if total:
        start = -90.0
        completed_angle = 360.0 * completed / total
        if completed:
            draw.pieslice(bbox, start, start + completed_angle, fill=_NAVY)
            _label(start + completed_angle / 2, completed, _NAVY)
        if pending:
            draw.pieslice(bbox, start + completed_angle, start + 360, fill=_BLUE)
            _label(start + completed_angle + (360 - completed_angle) / 2, pending, _BLUE)
    else:
        draw.ellipse(bbox, fill=_TRACK)

    ly = height - bottom_pad + 10
    draw.rounded_rectangle([40, ly, 72, ly + 26], radius=5, fill=_NAVY)
    draw.text((82, ly + 1), "Completados", font=font_legend, fill=_TEXT)
    lx2 = 82 + draw.textlength("Completados", font=font_legend) + 50
    draw.rounded_rectangle([lx2, ly, lx2 + 32, ly + 26], radius=5, fill=_BLUE)
    draw.text((lx2 + 42, ly + 1), "Pendientes", font=font_legend, fill=_TEXT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class ReportHelpdeskMonthlyPdf(models.AbstractModel):
    _name = "report.oca_helpdesk_reports.report_monthly_pdf_template"
    _description = "Valores del reporte mensual de tickets (PDF)"

    _max_listed = 50

    def _get_report_values(self, docids, data=None):
        wizards = self.env["helpdesk.report.monthly.wizard"].browse(docids)
        report_data = {}

        for wizard in wizards:
            tickets = self.env["helpdesk.ticket"].search(
                wizard._build_domain(), order="create_date"
            )
            completed = tickets.filtered(lambda t: t.stage_id.closed)
            pending = tickets - completed

            report_data[wizard.id] = {
                "completed": completed[: self._max_listed],
                "completed_extra": max(0, len(completed) - self._max_listed),
                "pending": pending[: self._max_listed],
                "pending_extra": max(0, len(pending) - self._max_listed),
                "date_from_es": _format_date_es(wizard.date_from),
                "date_to_es": _format_date_es(wizard.date_to),
                "chart_b64": (
                    _build_pie_chart_png(len(completed), len(pending))
                    if tickets
                    else False
                ),
            }

        return {
            "doc_ids": docids,
            "doc_model": "helpdesk.report.monthly.wizard",
            "docs": wizards,
            "report_data": report_data,
        }
