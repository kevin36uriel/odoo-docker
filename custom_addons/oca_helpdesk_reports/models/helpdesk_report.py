from odoo import fields, models


class HelpdeskReportMonthlyLine(models.TransientModel):
    _name = "helpdesk.report.monthly.line"
    _description = "Línea de reporte mensual de tickets"
    _order = "month, team_name, user_name"

    wizard_id = fields.Many2one(
        "helpdesk.report.monthly.wizard", required=True, ondelete="cascade"
    )
    month = fields.Char(string="Mes")
    team_name = fields.Char(string="Equipo")
    user_name = fields.Char(string="Agente")
    stage_name = fields.Char(string="Etapa")
    priority = fields.Char(string="Prioridad")
    total_tickets = fields.Integer(string="Total tickets")
    resolved_tickets = fields.Integer(string="Resueltos")
    pending_tickets = fields.Integer(string="Pendientes")
    avg_resolution_hours = fields.Float(
        string="Tiempo prom. resolución (hrs)", digits=(10, 1)
    )
