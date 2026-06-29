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
        if not self.line_ids:
            raise UserError(_("Primero genere el reporte antes de exportar."))

        try:
            import xlsxwriter
        except ImportError:
            raise UserError(
                _("La librería xlsxwriter no está disponible. Contacte al administrador.")
            )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Reporte Mensual")

        # --- Formatos ---
        title_fmt = workbook.add_format(
            {"bold": True, "font_size": 14, "font_color": "#4B5EA6"}
        )
        period_fmt = workbook.add_format({"italic": True, "font_color": "#555555"})
        summary_label_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#f0f4ff", "border": 1,
             "align": "center", "font_color": "#555555", "font_size": 9}
        )
        summary_value_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#f0f4ff", "border": 1,
             "align": "center", "font_size": 14, "font_color": "#4B5EA6"}
        )
        header_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#4B5EA6", "font_color": "white",
             "border": 1, "align": "center", "valign": "vcenter"}
        )
        footer_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#d3d3d3", "border": 1, "valign": "vcenter"}
        )
        footer_right_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#d3d3d3", "border": 1,
             "align": "right", "valign": "vcenter"}
        )

        def _row_fmts(even):
            bg = "#f2f2f2" if even else "white"
            base = {"border": 1, "valign": "vcenter", "bg_color": bg}
            return (
                workbook.add_format(base),
                workbook.add_format({**base, "align": "center"}),
                workbook.add_format({**base, "align": "right"}),
                workbook.add_format({**base, "align": "right", "num_format": "0.0"}),
            )

        odd_fmts = _row_fmts(False)
        even_fmts = _row_fmts(True)

        # --- Anchos de columna ---
        sheet.set_column(0, 0, 11)   # Mes
        sheet.set_column(1, 1, 22)   # Equipo
        sheet.set_column(2, 2, 22)   # Agente
        sheet.set_column(3, 3, 16)   # Etapa
        sheet.set_column(4, 4, 11)   # Prioridad
        sheet.set_column(5, 5, 8)    # Total
        sheet.set_column(6, 6, 11)   # Resueltos
        sheet.set_column(7, 7, 11)   # Pendientes
        sheet.set_column(8, 8, 20)   # Tiempo prom.

        row = 0

        # Título
        sheet.merge_range(row, 0, row, 8, "Reporte Mensual de Tickets", title_fmt)
        row += 1

        # Período
        sheet.merge_range(
            row, 0, row, 8,
            f"Período: {self.date_from} — {self.date_to}",
            period_fmt,
        )
        row += 2

        # Resumen
        sheet.write(row, 0, "Total tickets", summary_label_fmt)
        sheet.write(row, 1, "Resueltos", summary_label_fmt)
        sheet.write(row, 2, "Pendientes", summary_label_fmt)
        row += 1
        sheet.write(row, 0, self.total_tickets, summary_value_fmt)
        sheet.write(row, 1, self.total_resolved, summary_value_fmt)
        sheet.write(row, 2, self.total_pending, summary_value_fmt)
        row += 2

        # Encabezado de tabla
        headers = [
            "Mes", "Equipo", "Agente", "Etapa", "Prioridad",
            "Total", "Resueltos", "Pendientes", "Tiempo prom. (hrs)",
        ]
        for col, h in enumerate(headers):
            sheet.write(row, col, h, header_fmt)
        sheet.freeze_panes(row + 1, 0)
        row += 1

        # Filas de datos
        for i, line in enumerate(self.line_ids):
            f, fc, fr, ff = even_fmts if i % 2 else odd_fmts
            sheet.write(row, 0, line.month, f)
            sheet.write(row, 1, line.team_name, f)
            sheet.write(row, 2, line.user_name, f)
            sheet.write(row, 3, line.stage_name, f)
            sheet.write(row, 4, line.priority, fc)
            sheet.write(row, 5, line.total_tickets, fr)
            sheet.write(row, 6, line.resolved_tickets, fr)
            sheet.write(row, 7, line.pending_tickets, fr)
            sheet.write(row, 8, line.avg_resolution_hours, ff)
            row += 1

        # Fila de totales
        sheet.merge_range(row, 0, row, 4, "TOTAL", footer_fmt)
        sheet.write(row, 5, self.total_tickets, footer_right_fmt)
        sheet.write(row, 6, self.total_resolved, footer_right_fmt)
        sheet.write(row, 7, self.total_pending, footer_right_fmt)
        sheet.write(row, 8, "", footer_fmt)

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
