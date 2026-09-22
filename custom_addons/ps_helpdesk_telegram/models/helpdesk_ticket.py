import logging

from odoo import api, models

from ..services.telegram_client import TelegramClient


_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)

        if not TelegramClient.is_enabled():
            return tickets

        notification_model = self.env["ps.telegram.notification"].sudo()

        for ticket in tickets:
            if ticket.user_id:
                event_type = "assigned_create"
                target_chat_id = ticket.team_id.telegram_chat_id or False
            else:
                event_type = "unassigned_create"
                target_chat_id = False

            values = {
                "ticket_id": ticket.id,
                "event_type": event_type,
                "target_chat_id": target_chat_id,
            }

            # The savepoint prevents a queue problem from rolling back the ticket.
            try:
                with self.env.cr.savepoint():
                    notification_model.create(values)
            except Exception:
                _logger.error(
                    "No se pudo registrar la notificacion Telegram "
                    "del ticket %s. Tipo de error: %s",
                    ticket.id,
                    "queue_create_error",
                )

        return tickets

    def write(self, vals):
        was_unassigned = {
            ticket.id: not ticket.user_id
            for ticket in self
        }
        result = super().write(vals)

        if not TelegramClient.is_enabled():
            return result

        transitioned_tickets = self.filtered(
            lambda ticket: was_unassigned.get(ticket.id, False)
            and bool(ticket.user_id)
        )
        if not transitioned_tickets:
            return result

        notification_model = self.env["ps.telegram.notification"].sudo()
        for ticket in transitioned_tickets:
            values = {
                "ticket_id": ticket.id,
                "event_type": "unassigned_to_assigned",
                "target_chat_id": False,
            }

            # The savepoint prevents a queue problem from rolling back the assignment.
            try:
                with self.env.cr.savepoint():
                    notification_model.create(values)
            except Exception:
                _logger.error(
                    "No se pudo registrar la notificacion Telegram "
                    "de asignacion del ticket %s. Tipo de error: %s",
                    ticket.id,
                    "queue_create_error",
                )

        return result
