from odoo import fields, models


class HelpdeskTicketTeam(models.Model):
    _inherit = "helpdesk.ticket.team"

    telegram_chat_id = fields.Char(
        string="Telegram Chat ID",
        copy=False,
        groups="helpdesk_mgmt.group_helpdesk_manager",
        help="Telegram group destination for tickets assigned to this team.",
    )
