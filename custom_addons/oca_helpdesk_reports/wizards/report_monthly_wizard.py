import base64
import io
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_PRIORITY_LABELS = {
    "0": "Baja",
    "1": "Media",
    "2": "Alta",
    "3": "Muy Alta",
}


class HelpdeskReportMonthlyWizard(models.TransientModel):
    _name = "helpdesk.report.monthly.wizard"
    _description = "Reporte mensual de tickets"

    date_from = fields.Date(
        string="Fecha desde",
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string="Fecha hasta",
        required=True,
        default=fields.Date.today,
    )
    team_id = fields.Many2one("helpdesk.ticket.team", string="Equipo")
    user_id = fields.Many2one("res.users", string="Agente")
    line_ids = fields.One2many(
        "helpdesk.report.monthly.line", "wizard_id", string="Resultados"
    )
    report_generated = fields.Boolean(default=False)
    total_tickets = fields.Integer(
        string="Total tickets", compute="_compute_totals", store=False
    )
    total_resolved = fields.Integer(
        string="Resueltos", compute="_compute_totals", store=False
    )
    total_pending = fields.Integer(
        string="Pendientes", compute="_compute_totals", store=False
    )

    @api.depends("line_ids")
    def _compute_totals(self):
        for rec in self:
            rec.total_tickets = sum(rec.line_ids.mapped("total_tickets"))
            rec.total_resolved = sum(rec.line_ids.mapped("resolved_tickets"))
            rec.total_pending = sum(rec.line_ids.mapped("pending_tickets"))

    def _build_domain(self):
        domain = []
        if self.date_from:
            domain.append(
                ("create_date", ">=", datetime.combine(self.date_from, datetime.min.time()))
            )
        if self.date_to:
            domain.append(
                ("create_date", "<=", datetime.combine(self.date_to, datetime.max.time()))
            )
        if self.team_id:
            domain.append(("team_id", "=", self.team_id.id))
        if self.user_id:
            domain.append(("user_id", "=", self.user_id.id))
        return domain

    def action_generate_report(self):
        self.line_ids.unlink()
        domain = self._build_domain()
        tickets = self.env["helpdesk.ticket"].search(domain, limit=10001)
        if len(tickets) > 10000:
            raise UserError(
                _(
                    "La consulta supera 10,000 registros. "
                    "Por favor, reduzca el rango de fechas."
                )
            )

        groups = {}
        for ticket in tickets:
            month_key = (
                ticket.create_date.strftime("%Y-%m") if ticket.create_date else "N/A"
            )
            key = (
                month_key,
                ticket.team_id.name or "",
                ticket.user_id.name or "",
                ticket.stage_id.name or "",
                ticket.priority or "1",
            )
            if key not in groups:
                groups[key] = {
                    "month": month_key,
                    "team_name": ticket.team_id.name or "",
                    "user_name": ticket.user_id.name or _("Sin asignar"),
                    "stage_name": ticket.stage_id.name or "",
                    "priority": _PRIORITY_LABELS.get(ticket.priority or "1", ""),
                    "total": 0,
                    "resolved": 0,
                    "pending": 0,
                    "resolution_times": [],
                }
            g = groups[key]
            g["total"] += 1
            if ticket.stage_id.closed:
                g["resolved"] += 1
                if ticket.closed_date and ticket.assigned_date:
                    diff = (ticket.closed_date - ticket.assigned_date).total_seconds() / 3600
                    if diff >= 0:
                        g["resolution_times"].append(diff)
            else:
                g["pending"] += 1

        vals_list = []
        for g in groups.values():
            avg = (
                sum(g["resolution_times"]) / len(g["resolution_times"])
                if g["resolution_times"]
                else 0.0
            )
            vals_list.append(
                {
                    "wizard_id": self.id,
                    "month": g["month"],
                    "team_name": g["team_name"],
                    "user_name": g["user_name"],
                    "stage_name": g["stage_name"],
                    "priority": g["priority"],
                    "total_tickets": g["total"],
                    "resolved_tickets": g["resolved"],
                    "pending_tickets": g["pending"],
                    "avg_resolution_hours": avg,
                }
            )

        if vals_list:
            self.env["helpdesk.report.monthly.line"].create(vals_list)
        self.report_generated = True

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_export_pdf(self):
        if not self.line_ids:
            raise UserError(_("Primero genere el reporte antes de exportar."))
        return (
            self.env.ref("oca_helpdesk_reports.action_report_monthly_pdf")
            .report_action(self)
        )

    def action_export_excel(self):
        if not self.report_generated:
            raise UserError(_("Primero genere el reporte antes de exportar."))

        try:
            import xlsxwriter
        except ImportError:
            raise UserError(
                _("La librería xlsxwriter no está disponible. Contacte al administrador.")
            )

        domain = self._build_domain()
        tickets = self.env["helpdesk.ticket"].search(domain, order="create_date desc")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Reporte")

        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#17375E",
            "font_color": "white",
            "align": "center",
            "valign": "vcenter",
            "font_size": 11,
        })

        fmt_blue_left   = workbook.add_format({"bg_color": "#D6E4F0", "valign": "vcenter", "align": "left",   "font_size": 11})
        fmt_blue_center = workbook.add_format({"bg_color": "#D6E4F0", "valign": "vcenter", "align": "center", "font_size": 11})
        fmt_white_left  = workbook.add_format({"bg_color": "white",   "valign": "vcenter", "align": "left",   "font_size": 11})
        fmt_white_center= workbook.add_format({"bg_color": "white",   "valign": "vcenter", "align": "center", "font_size": 11})

        sheet.set_column(0, 0, 65)   # Incidencia
        sheet.set_column(1, 1, 17)   # Fecha de creación
        sheet.set_column(2, 2, 17)   # Hora de creación
        sheet.set_column(3, 3, 12)   # Prioridad
        sheet.set_column(4, 4, 10)   # Nivel
        sheet.set_default_row(18)

        headers = [
            "Incidencia", "Fecha de creación", "Hora de creación", "Prioridad", "Nivel"
        ]
        for col, h in enumerate(headers):
            sheet.write(0, col, h, header_fmt)
        sheet.set_row(0, 22)
        sheet.autofilter(0, 0, 0, 4)
        sheet.freeze_panes(1, 0)

        for i, ticket in enumerate(tickets):
            blue_row = (i % 2 == 0)
            txt_fmt    = fmt_blue_left   if blue_row else fmt_white_left
            center_fmt = fmt_blue_center if blue_row else fmt_white_center
            row = i + 1

            if ticket.create_date:
                local_dt = fields.Datetime.context_timestamp(ticket, ticket.create_date)
                date_str = local_dt.strftime("%-d/%-m/%Y")
                time_str = (
                    local_dt.strftime("%-I:%M:%S %p")
                    .lower()
                    .replace("am", "a.m.")
                    .replace("pm", "p.m.")
                )
            else:
                date_str = ""
                time_str = ""

            sheet.write(row, 0, ticket.name or "", txt_fmt)
            sheet.write(row, 1, date_str, center_fmt)
            sheet.write(row, 2, time_str, center_fmt)
            sheet.write(row, 3, _PRIORITY_LABELS.get(ticket.priority or "0", ""), center_fmt)
            sheet.write(row, 4, "", center_fmt)

        workbook.close()

        attachment = self.env["ir.attachment"].create({
            "name": f"reporte_tickets_{self.date_from}_{self.date_to}.xlsx",
            "type": "binary",
            "datas": base64.b64encode(output.getvalue()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }

    def action_configurar_diseno(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "base.document.layout",
            "view_mode": "form",
            "target": "new",
        }
