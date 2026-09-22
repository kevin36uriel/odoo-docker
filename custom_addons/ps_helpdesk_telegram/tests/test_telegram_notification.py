import os
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from ..models.telegram_notification import TelegramNotification
from ..services.telegram_client import TelegramClient


class TestTelegramNotification(TransactionCase):
    def _telegram_environment(self):
        return {
            "TELEGRAM_ENABLED": "1",
            "TELEGRAM_CHAT_ID": "-1000000000000",
            "ODOO_INTERNAL_URL": "https://odoo.test",
        }

    def _create_ticket(self, **values):
        ticket_values = {
            "name": "Ticket de prueba Telegram",
            "description": "Descripcion que no debe enviarse",
            "priority": "3",
            "user_id": False,
        }
        ticket_values.update(values)
        return self.env["helpdesk.ticket"].create(ticket_values)

    def _create_second_user(self):
        return self.env["res.users"].create(
            {
                "name": "Segundo tecnico Telegram",
                "login": "telegram_second_technician",
                "email": "telegram_second_technician@example.com",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def _create_telegram_team(self, chat_id=False):
        return self.env["helpdesk.ticket.team"].create(
            {
                "name": "Equipo Telegram de prueba",
                "user_ids": [(4, self.env.user.id)],
                "telegram_chat_id": chat_id,
            }
        )

    def test_unassigned_ticket_creates_one_queue_entry(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()

        notifications = self.env["ps.telegram.notification"].search(
            [("ticket_id", "=", ticket.id)]
        )

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications.event_type, "unassigned_create")
        self.assertFalse(notifications.target_chat_id)
        self.assertEqual(notifications.state, "pending")

    def test_assigned_ticket_creates_assigned_queue_entry(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            team = self._create_telegram_team("-1000000000001")
            ticket = self._create_ticket(
                team_id=team.id,
                user_id=self.env.user.id,
            )

        notifications = self.env[
            "ps.telegram.notification"
        ].search([("ticket_id", "=", ticket.id)])

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications.event_type, "assigned_create")
        self.assertEqual(notifications.target_chat_id, "-1000000000001")

    def test_assigned_ticket_does_not_create_unassigned_event(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            team = self._create_telegram_team("-1000000000002")
            ticket = self._create_ticket(
                team_id=team.id,
                user_id=self.env.user.id,
                priority="1",
            )

        unassigned_count = self.env[
            "ps.telegram.notification"
        ].search_count(
            [
                ("ticket_id", "=", ticket.id),
                ("event_type", "=", "unassigned_create"),
            ]
        )

        self.assertEqual(unassigned_count, 0)

    def test_queue_error_does_not_rollback_ticket(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            with patch.object(
                TelegramNotification,
                "create",
                side_effect=RuntimeError("queue failure"),
            ):
                ticket = self._create_ticket()

        self.assertTrue(ticket.exists())
        self.assertTrue(ticket.number)

    def test_message_contains_only_allowed_ticket_data(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            notification = self.env[
                "ps.telegram.notification"
            ].search([("ticket_id", "=", ticket.id)], limit=1)
            message = notification._build_message(ticket)

        self.assertIn(ticket.number, message)
        self.assertIn(ticket.name, message)
        self.assertIn("Muy alta", message)
        self.assertNotIn("Very High", message)
        self.assertIn("Sin equipo", message)
        self.assertIn(f"id={ticket.id}", message)
        self.assertNotIn("Descripcion que no debe enviarse", message)
        self.assertNotIn("partner_email", message)

    def test_assigned_message_contains_responsible_and_excludes_sensitive_data(
        self,
    ):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            team = self._create_telegram_team("-1000000000003")
            ticket = self._create_ticket(
                team_id=team.id,
                user_id=self.env.user.id,
                priority="1",
            )
            notification = self.env[
                "ps.telegram.notification"
            ].search([("ticket_id", "=", ticket.id)], limit=1)
            message = notification._build_event_message()

        self.assertIn("Ticket asignado", message)
        self.assertIn(ticket.user_id.name, message)
        self.assertIn("Media", message)
        self.assertIn("-1000000000003", notification.target_chat_id)
        self.assertNotIn("Descripcion que no debe enviarse", message)
        self.assertNotIn("partner_email", message)

    def test_priority_labels_are_spanish(self):
        expected_labels = {
            "0": "Baja",
            "1": "Media",
            "2": "Alta",
            "3": "Muy alta",
        }

        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            for priority, expected_label in expected_labels.items():
                ticket = self._create_ticket(priority=priority)
                notification = self.env[
                    "ps.telegram.notification"
                ].search([("ticket_id", "=", ticket.id)], limit=1)

                self.assertIn(expected_label, notification._build_event_message())

    @patch(
        "odoo.addons.ps_helpdesk_telegram.models.telegram_notification.TelegramClient"
    )
    def test_successful_send_marks_notification_sent(self, telegram_client):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            notification = self.env[
                "ps.telegram.notification"
            ].search([("ticket_id", "=", ticket.id)], limit=1)

            telegram_client.return_value.send_message.return_value = "123"
            notification._send_one()

        self.assertEqual(notification.state, "sent")
        self.assertEqual(notification.telegram_message_id, "123")

    @patch(
        "odoo.addons.ps_helpdesk_telegram.models.telegram_notification.TelegramClient"
    )
    def test_cron_processes_pending_notifications(self, telegram_client):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            telegram_client.return_value.send_message.return_value = "456"

            self.env["ps.telegram.notification"]._cron_process_pending()

        notification = self.env[
            "ps.telegram.notification"
        ].search([("ticket_id", "=", ticket.id)], limit=1)

        self.assertEqual(notification.state, "sent")
        self.assertEqual(notification.telegram_message_id, "456")

    def test_later_assignment_creates_global_assignment_event(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            ticket.write({"user_id": self.env.user.id})
            ticket.write({"user_id": self.env.user.id})

        notifications = self.env["ps.telegram.notification"].search(
            [("ticket_id", "=", ticket.id)]
        )

        self.assertEqual(len(notifications), 2)
        self.assertEqual(
            notifications.filtered(
                lambda notification: notification.event_type
                == "unassigned_to_assigned"
            ).event_type,
            "unassigned_to_assigned",
        )
        assignment_notification = notifications.filtered(
            lambda notification: notification.event_type
            == "unassigned_to_assigned"
        )
        self.assertFalse(assignment_notification.target_chat_id)
        self.assertIsNone(assignment_notification._get_destination_chat_id())
        self.assertIn(
            "Ticket asignado",
            assignment_notification._build_event_message(),
        )
        self.assertIn("Muy alta", assignment_notification._build_event_message())

    def test_reassignment_does_not_create_stage_three_event(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            second_user = self._create_second_user()
            team = self._create_telegram_team(
                "-1000000000004",
            )
            team.write({"user_ids": [(4, second_user.id)]})
            ticket = self._create_ticket(
                team_id=team.id,
                user_id=self.env.user.id,
            )
            ticket.write({"user_id": second_user.id})

        stage_three_count = self.env[
            "ps.telegram.notification"
        ].search_count(
            [
                ("ticket_id", "=", ticket.id),
                ("event_type", "=", "unassigned_to_assigned"),
            ]
        )

        self.assertEqual(stage_three_count, 0)

    def test_write_on_multiple_unassigned_tickets_creates_one_event_each(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            tickets = self.env["helpdesk.ticket"].create(
                [
                    {
                        "name": "Ticket multiple 1",
                        "description": "Descripcion 1",
                        "priority": "1",
                        "user_id": False,
                    },
                    {
                        "name": "Ticket multiple 2",
                        "description": "Descripcion 2",
                        "priority": "2",
                        "user_id": False,
                    },
                ]
            )
            tickets.write({"user_id": self.env.user.id})

        self.assertEqual(
            self.env["ps.telegram.notification"].search_count(
                [
                    ("ticket_id", "in", tickets.ids),
                    ("event_type", "=", "unassigned_to_assigned"),
                ]
            ),
            2,
        )

    def test_unrelated_write_does_not_create_stage_three_event(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            ticket.write(
                {
                    "name": "Titulo actualizado",
                    "priority": "2",
                    "description": "Descripcion actualizada",
                }
            )

        self.assertEqual(
            self.env["ps.telegram.notification"].search_count(
                [
                    ("ticket_id", "=", ticket.id),
                    ("event_type", "=", "unassigned_to_assigned"),
                ]
            ),
            0,
        )

    def test_assignment_queue_error_does_not_rollback_ticket(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            with patch.object(
                TelegramNotification,
                "create",
                side_effect=RuntimeError("queue failure"),
            ):
                ticket.write({"user_id": self.env.user.id})

        self.assertEqual(ticket.user_id, self.env.user)
        self.assertTrue(ticket.exists())

    def test_assignment_write_does_not_call_telegram_directly(self):
        with patch.dict(os.environ, self._telegram_environment(), clear=False):
            ticket = self._create_ticket()
            with patch.object(TelegramClient, "send_message") as send_message:
                ticket.write({"user_id": self.env.user.id})

        send_message.assert_not_called()
