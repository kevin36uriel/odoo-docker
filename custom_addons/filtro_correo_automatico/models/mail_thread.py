import email
import logging
from xmlrpc import client as xmlrpclib

from odoo import models

_logger = logging.getLogger(__name__)

# (RFC 2076 / uso de facto en newsletters y notificaciones automáticas).
AUTO_PRECEDENCE_VALUES = {"bulk", "auto_reply", "junk", "list"}


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def message_process(self, model, message, custom_values=None,
                         save_original=False, strip_attachments=False,
                         thread_id=None):

        reason = self._filtro_correo_automatico_detect(message)
        if reason:
            _logger.info(
                "filtro_correo_automatico: correo descartado antes de crear/actualizar "
                "registro en '%s' (%s)", model, reason,
            )
            return False
        return super().message_process(
            model, message, custom_values=custom_values,
            save_original=save_original, strip_attachments=strip_attachments,
            thread_id=thread_id,
        )

    def _filtro_correo_automatico_detect(self, message):
        """Devuelve una razón (str) si el mensaje trae headers de correo
        generado por máquina, o None si parece correo humano normal."""
        raw = message
        if isinstance(raw, xmlrpclib.Binary):
            raw = bytes(raw.data)
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        try:
            parsed = email.message_from_bytes(raw, policy=email.policy.SMTP)
        except Exception:
            # Si no se puede parsear aquí, se deja que el flujo normal
            # de message_process falle o procese el correo como corresponda.
            return None

        auto_submitted = (parsed.get("Auto-Submitted") or "").strip().lower()
        if auto_submitted and auto_submitted != "no":
            return "Auto-Submitted: %s" % auto_submitted

        precedence = (parsed.get("Precedence") or "").strip().lower()
        if precedence in AUTO_PRECEDENCE_VALUES:
            return "Precedence: %s" % precedence

        if parsed.get("X-Auto-Response-Suppress"):
            return "header X-Auto-Response-Suppress presente"

        if parsed.get("List-Id") or parsed.get("List-Unsubscribe"):
            return "header List-Id/List-Unsubscribe presente"

        return None
