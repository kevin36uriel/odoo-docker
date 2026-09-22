import logging
import os
from datetime import timedelta
from html import escape

from odoo import api, fields, models

from ..services.telegram_client import (
    TelegramClient,
    TelegramConfigurationError,
    TelegramError,
)


_logger = logging.getLogger(__name__)

_PRIORITY_LABELS = {
    "0": "Baja",
    "1": "Media",
    "2": "Alta",
    "3": "Muy alta",
}


class TelegramNotification(models.Model):
    _name = "ps.telegram.notification"
    _description = "Telegram Notification"
    _order = "create_date, id"

    _sql_constraints = [
        (
            "ticket_event_unique",
            "unique(ticket_id, event_type)",
            "Ya existe una notificacion para este evento del ticket.",
        ),
    ]

    ticket_id = fields.Many2one(
        "helpdesk.ticket",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        selection=[
            ("unassigned_create", "Ticket creado sin tecnico"),
            ("assigned_create", "Ticket creado con tecnico"),
            ("unassigned_to_assigned", "Ticket asignado"),
        ],
        required=True,
        default="unassigned_create",
        index=True,
    )
    target_chat_id = fields.Char(copy=False)
    state = fields.Selection(
        selection=[
            ("pending", "Pendiente"),
            ("sent", "Enviada"),
            ("failed", "Fallida"),
        ],
        required=True,
        default="pending",
        index=True,
    )
    attempts = fields.Integer(default=0)
    next_attempt_at = fields.Datetime(
        default=fields.Datetime.now,
        index=True,
    )
    sent_at = fields.Datetime()
    telegram_message_id = fields.Char()
    last_error = fields.Text()

    @api.model
    def _get_batch_size(self):
        value = os.getenv("TELEGRAM_QUEUE_BATCH_SIZE", "5")

        try:
            return max(1, int(value))
        except ValueError:
            return 5

    @api.model
    def _get_max_attempts(self):
        value = os.getenv("TELEGRAM_MAX_ATTEMPTS", "3")

        try:
            return max(1, int(value))
        except ValueError:
            return 3

    @api.model
    def _get_retry_delay(self, attempt):
        value = os.getenv("TELEGRAM_RETRY_BACKOFF", "60")

        try:
            base_delay = max(1, int(value))
        except ValueError:
            base_delay = 60

        return base_delay * (2 ** max(attempt - 1, 0))

    def _get_ticket_url(self, ticket):
        base_url = os.getenv("ODOO_INTERNAL_URL", "").strip()

        if not base_url:
            raise TelegramConfigurationError(
                "ODOO_INTERNAL_URL no esta configurado."
            )

        return (
            f"{base_url.rstrip('/')}/web"
            f"#model=helpdesk.ticket"
            f"&id={ticket.id}"
            f"&view_type=form"
        )

    def _get_destination_chat_id(self):
        self.ensure_one()

        if self.target_chat_id:
            return self.target_chat_id

        if self.event_type in {
            "unassigned_create",
            "unassigned_to_assigned",
        }:
            # Keep the existing global destination for unassigned tickets.
            return None

        team_chat_id = self.ticket_id.team_id.telegram_chat_id
        if team_chat_id:
            return team_chat_id

        raise TelegramConfigurationError(
            "El equipo del ticket no tiene Telegram Chat ID configurado."
        )

    def _get_priority_label(self, ticket):
        return _PRIORITY_LABELS.get(ticket.priority, "Sin definir")

    def _build_message(self, ticket):
        title = (ticket.name or "Sin titulo")[:500]
        priority = self._get_priority_label(ticket)
        team = ticket.team_id.display_name or "Sin equipo"
        ticket_url = self._get_ticket_url(ticket)

        return "\n".join(
            [
                "<b>Nuevo ticket sin tecnico</b>",
                "",
                f"<b>Numero:</b> {escape(str(ticket.number))}",
                f"<b>Titulo:</b> {escape(title)}",
                f"<b>Prioridad:</b> {escape(str(priority))}",
                f"<b>Equipo:</b> {escape(team)}",
                "",
                (
                    f'<a href="{escape(ticket_url, quote=True)}">'
                    "Abrir ticket en Odoo"
                    "</a>"
                ),
            ]
        )

    def _build_assigned_message(self, ticket):
        title = (ticket.name or "Sin titulo")[:500]
        priority = self._get_priority_label(ticket)
        team = ticket.team_id.display_name or "Sin equipo"
        responsible = ticket.user_id.name or "Sin tecnico"
        ticket_url = self._get_ticket_url(ticket)

        return "\n".join(
            [
                "🎫 <b>Ticket asignado</b>",
                "",
                f"<b>Numero:</b> {escape(str(ticket.number))}",
                f"<b>Titulo:</b> {escape(title)}",
                f"<b>Prioridad:</b> {escape(str(priority))}",
                f"<b>Equipo:</b> {escape(team)}",
                f"👤 <b>Responsable:</b> {escape(responsible)}",
                "",
                (
                    f'<a href="{escape(ticket_url, quote=True)}">'
                    "Abrir ticket en Odoo"
                    "</a>"
                ),
            ]
        )

    def _build_event_message(self):
        self.ensure_one()

        if self.event_type in {
            "assigned_create",
            "unassigned_to_assigned",
        }:
            return self._build_assigned_message(self.ticket_id)

        return self._build_message(self.ticket_id)

    def _register_failure(self, error):
        self.ensure_one()

        attempt = self.attempts + 1
        max_attempts = self._get_max_attempts()
        values = {
            "attempts": attempt,
            "last_error": str(error)[:2000],
        }

        if not error.retryable or attempt >= max_attempts:
            values.update(
                {
                    "state": "failed",
                    "next_attempt_at": False,
                }
            )
        else:
            delay = self._get_retry_delay(attempt)
            values.update(
                {
                    "state": "pending",
                    "next_attempt_at": fields.Datetime.now()
                    + timedelta(seconds=delay),
                }
            )

        self.write(values)

    def _send_one(self):
        self.ensure_one()

        try:
            client = TelegramClient()
            message_id = client.send_message(
                self._build_event_message(),
                chat_id=self._get_destination_chat_id(),
            )
        except TelegramError as error:
            self._register_failure(error)
            _logger.warning(
                "No se pudo enviar la notificacion Telegram del registro %s.",
                self.id,
            )
        except Exception:
            error = TelegramError(
                "Error interno al preparar la notificacion Telegram.",
                retryable=True,
            )
            self._register_failure(error)
            _logger.error(
                "Error interno al procesar la notificacion Telegram %s.",
                self.id,
            )
        else:
            self.write(
                {
                    "state": "sent",
                    "sent_at": fields.Datetime.now(),
                    "telegram_message_id": message_id,
                    "last_error": False,
                }
            )

    @api.model
    def _cron_process_pending(self):
        if not TelegramClient.is_enabled():
            return

        limit = self._get_batch_size()
        now = fields.Datetime.now()

        self.env.cr.execute(
            """
            SELECT id
              FROM ps_telegram_notification
             WHERE state = 'pending'
               AND (
                    next_attempt_at IS NULL
                    OR next_attempt_at <= %s
               )
             ORDER BY next_attempt_at NULLS FIRST, id
             LIMIT %s
             FOR UPDATE SKIP LOCKED
            """,
            (now, limit),
        )

        notification_ids = [row[0] for row in self.env.cr.fetchall()]

        for notification in self.browse(notification_ids):
            notification._send_one()
