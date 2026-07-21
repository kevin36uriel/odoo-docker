import base64
import io
import math

from odoo import fields, models

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

_DIAS_SEMANA_ES = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo",
]

_FRANJAS_HORARIAS = [
    "%02d-%02d" % (h, h + 2) for h in range(0, 24, 2)
]

_PRIORITY_LABELS = {
    "0": "Baja",
    "1": "Media",
    "2": "Alta",
    "3": "Muy Alta",
}

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
        font_label = ImageFont.truetype(_FONT_BOLD, 26)
        font_legend = ImageFont.truetype(_FONT_REGULAR, 24)
    except OSError:
        font_label = font_legend = ImageFont.load_default()

    top_pad = 36
    circle_d = 520
    bottom_pad = 90
    height = top_pad + circle_d + bottom_pad + 60

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

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


def _build_bar_chart_png(categories, series_data, width=1400):
    """Barras verticales, con 1 o varias series apiladas.

    series_data: lista de (etiqueta, color, valores) — valores alineado con categories.
    Devuelve None si no hay ninguna categoría con datos (evita gráficas vacías).
    El título de la sección lo pone el HTML, no la imagen.
    """
    from PIL import Image, ImageDraw, ImageFont

    n = len(categories)
    totals = [sum(s[2][i] for s in series_data) for i in range(n)] if n else []
    if not totals or not any(totals):
        return None

    try:
        font_axis = ImageFont.truetype(_FONT_REGULAR, 22)
        font_value = ImageFont.truetype(_FONT_BOLD, 22)
        font_legend = ImageFont.truetype(_FONT_REGULAR, 24)
    except OSError:
        font_axis = font_value = font_legend = ImageFont.load_default()

    long_labels = any(len(c) > 8 for c in categories)
    left_pad, right_pad = 90, 40
    top_pad = 30
    chart_h = 480
    bottom_pad = 170 if long_labels else 110
    legend_h = 60 if len(series_data) > 1 else 0
    height = top_pad + chart_h + bottom_pad + legend_h

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    steps = 4
    step_val = max(1, math.ceil(max(totals) / steps))
    max_val = step_val * steps

    plot_w = width - left_pad - right_pad
    plot_bottom = top_pad + chart_h

    for i in range(steps + 1):
        y = plot_bottom - (chart_h * i / steps)
        draw.line([left_pad, y, width - right_pad, y], fill=_TRACK, width=1)
        val_label = step_val * i
        tw = draw.textlength(str(val_label), font=font_axis)
        draw.text((left_pad - 16 - tw, y - 12), str(val_label), font=font_axis, fill=_TEXT)

    slot_w = plot_w / n
    bar_w = min(90, slot_w * 0.5)

    for i, cat in enumerate(categories):
        cx = left_pad + slot_w * i + slot_w / 2
        y_cursor = plot_bottom
        for _label, color, values in series_data:
            val = values[i]
            if val <= 0:
                continue
            bar_h = chart_h * val / max_val
            draw.rectangle([cx - bar_w / 2, y_cursor - bar_h, cx + bar_w / 2, y_cursor], fill=color)
            y_cursor -= bar_h

        if totals[i] > 0:
            text = str(totals[i])
            tw = draw.textlength(text, font=font_value)
            top_y = plot_bottom - (chart_h * totals[i] / max_val)
            draw.text((cx - tw / 2, top_y - 30), text, font=font_value, fill=_TEXT)

        if long_labels:
            txt_img = Image.new("RGBA", (200, 30), (255, 255, 255, 0))
            tdraw = ImageDraw.Draw(txt_img)
            tdraw.text((0, 0), cat, font=font_axis, fill=_TEXT)
            txt_img = txt_img.rotate(35, expand=True, resample=Image.BICUBIC)
            img.paste(txt_img, (int(cx - txt_img.width / 2), int(plot_bottom + 14)), txt_img)
        else:
            tw = draw.textlength(cat, font=font_axis)
            draw.text((cx - tw / 2, plot_bottom + 14), cat, font=font_axis, fill=_TEXT)

    if len(series_data) > 1:
        lx = 40
        ly = height - legend_h + 10
        for label, color, _values in series_data:
            draw.rounded_rectangle([lx, ly, lx + 28, ly + 22], radius=4, fill=color)
            draw.text((lx + 36, ly), label, font=font_legend, fill=_TEXT)
            lx += 36 + draw.textlength(label, font=font_legend) + 40

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _weekday_chart(tickets):
    counts = [0] * 7
    for ticket in tickets:
        if not ticket.create_date:
            continue
        local_dt = fields.Datetime.context_timestamp(ticket, ticket.create_date)
        counts[local_dt.weekday()] += 1
    return _build_bar_chart_png(_DIAS_SEMANA_ES, [("Tickets", _NAVY, counts)])


def _hourly_chart(tickets):
    counts = [0] * 12
    for ticket in tickets:
        if not ticket.create_date:
            continue
        local_dt = fields.Datetime.context_timestamp(ticket, ticket.create_date)
        counts[local_dt.hour // 2] += 1
    return _build_bar_chart_png(_FRANJAS_HORARIAS, [("Tickets", _BLUE, counts)])


def _priority_chart(tickets):
    order = ["Baja", "Media", "Alta", "Muy Alta"]
    resolved = {label: 0 for label in order}
    pending = {label: 0 for label in order}
    for ticket in tickets:
        label = _PRIORITY_LABELS.get(ticket.priority or "0", "Baja")
        if ticket.stage_id.closed:
            resolved[label] += 1
        else:
            pending[label] += 1
    return _build_bar_chart_png(
        order,
        [
            ("Resueltos", _NAVY, [resolved[label] for label in order]),
            ("Pendientes", _BLUE, [pending[label] for label in order]),
        ],
    )


def _agent_chart(tickets):
    counts = {}
    for ticket in tickets:
        name = ticket.user_id.name or "Sin asignar"
        counts[name] = counts.get(name, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    labels = [name for name, _count in ordered]
    values = [count for _name, count in ordered]
    return _build_bar_chart_png(labels, [("Tickets", _NAVY, values)])


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
                "weekday_chart_b64": _weekday_chart(tickets) if tickets else False,
                "hourly_chart_b64": _hourly_chart(tickets) if tickets else False,
                "priority_chart_b64": _priority_chart(tickets) if tickets else False,
                "agent_chart_b64": _agent_chart(tickets) if tickets else False,
            }

        return {
            "doc_ids": docids,
            "doc_model": "helpdesk.report.monthly.wizard",
            "docs": wizards,
            "report_data": report_data,
        }
