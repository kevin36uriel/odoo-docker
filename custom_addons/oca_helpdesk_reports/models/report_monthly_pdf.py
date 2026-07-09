import base64
import io

from odoo import _, models

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

_MAX_CHART_ROWS = 10


def _format_date_es(d):
    if not d:
        return ""
    return "%d de %s de %d" % (d.day, _MESES_ES[d.month], d.year)


def _build_chart_png(rows, width=1400):
    """rows: [(label, completed, pending), ...], ya ordenadas y acotadas."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font_title = ImageFont.truetype(_FONT_BOLD, 34)
        font_label = ImageFont.truetype(_FONT_REGULAR, 24)
        font_value = ImageFont.truetype(_FONT_BOLD, 24)
        font_legend = ImageFont.truetype(_FONT_REGULAR, 24)
    except OSError:
        font_title = font_label = font_value = font_legend = ImageFont.load_default()

    top_pad = 96
    bar_h = 46
    bar_gap = 24
    bottom_pad = 90
    label_col = 340
    right_pad = 90
    bar_area = width - label_col - right_pad

    height = top_pad + len(rows) * (bar_h + bar_gap) + bottom_pad
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    draw.text(
        (40, 34),
        "Tickets por agente — completados vs. pendientes",
        font=font_title,
        fill=_NAVY,
    )

    max_total = max((c + p for _l, c, p in rows), default=0) or 1

    y = top_pad
    for label, completed, pending in rows:
        total = completed + pending
        draw.rectangle([label_col, y, label_col + bar_area, y + bar_h], fill=_TRACK)
        c_w = int(bar_area * completed / max_total)
        p_w = int(bar_area * pending / max_total)
        if c_w:
            draw.rectangle([label_col, y, label_col + c_w, y + bar_h], fill=_NAVY)
        if p_w:
            draw.rectangle(
                [label_col + c_w, y, label_col + c_w + p_w, y + bar_h], fill=_BLUE
            )

        text = label if len(label) <= 28 else label[:26] + "…"
        tw = draw.textlength(text, font=font_label)
        draw.text(
            (label_col - 20 - tw, y + bar_h / 2 - 14), text, font=font_label, fill=_TEXT
        )
        draw.text(
            (label_col + bar_area + 16, y + bar_h / 2 - 13),
            str(total),
            font=font_value,
            fill=_TEXT,
        )
        y += bar_h + bar_gap

    ly = height - bottom_pad + 26
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

            by_agent = {}
            for ticket in tickets:
                agent = ticket.user_id.name or _("Sin asignar")
                row = by_agent.setdefault(agent, {"completed": 0, "pending": 0})
                if ticket.stage_id.closed:
                    row["completed"] += 1
                else:
                    row["pending"] += 1

            agent_rows = sorted(
                by_agent.items(),
                key=lambda kv: kv[1]["completed"] + kv[1]["pending"],
                reverse=True,
            )
            chart_rows = [
                (name, v["completed"], v["pending"])
                for name, v in agent_rows[:_MAX_CHART_ROWS]
            ]
            rest = agent_rows[_MAX_CHART_ROWS:]
            if rest:
                chart_rows.append(
                    (
                        _("Otros (%s agentes)") % len(rest),
                        sum(v["completed"] for _n, v in rest),
                        sum(v["pending"] for _n, v in rest),
                    )
                )

            report_data[wizard.id] = {
                "completed": completed[: self._max_listed],
                "completed_extra": max(0, len(completed) - self._max_listed),
                "pending": pending[: self._max_listed],
                "pending_extra": max(0, len(pending) - self._max_listed),
                "date_from_es": _format_date_es(wizard.date_from),
                "date_to_es": _format_date_es(wizard.date_to),
                "chart_b64": _build_chart_png(chart_rows) if chart_rows else False,
            }

        return {
            "doc_ids": docids,
            "doc_model": "helpdesk.report.monthly.wizard",
            "docs": wizards,
            "report_data": report_data,
        }
