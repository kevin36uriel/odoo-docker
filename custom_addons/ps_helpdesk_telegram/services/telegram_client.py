import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TelegramError(Exception):
    def __init__(self, message, retryable=True):
        super().__init__(message)
        self.retryable = retryable


class TelegramConfigurationError(TelegramError):
    def __init__(self, message):
        super().__init__(message, retryable=False)


class TelegramClient:
    @staticmethod
    def is_enabled():
        value = os.getenv("TELEGRAM_ENABLED", "0").strip().lower()
        return value in {"1", "true", "yes", "on"}

    @staticmethod
    def _read_secret(name):
        secret_file = os.getenv(f"{name}_FILE")

        if secret_file:
            try:
                with open(secret_file, encoding="utf-8") as file:
                    return file.read().strip()
            except OSError as error:
                raise TelegramConfigurationError(
                    f"No se pudo leer {name}_FILE."
                ) from error

        return os.getenv(name, "").strip()

    @staticmethod
    def _get_timeout():
        value = os.getenv("TELEGRAM_READ_TIMEOUT", "10")

        try:
            return float(value)
        except ValueError as error:
            raise TelegramConfigurationError(
                "TELEGRAM_READ_TIMEOUT debe ser numerico."
            ) from error

    def __init__(self):
        self.token = self._read_secret("TELEGRAM_BOT_TOKEN")

        if not self.token:
            raise TelegramConfigurationError(
                "TELEGRAM_BOT_TOKEN no esta configurado."
            )

        self.default_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        self.api_base_url = os.getenv(
            "TELEGRAM_API_BASE_URL",
            "https://api.telegram.org",
        ).rstrip("/")
        self.timeout = self._get_timeout()

    def send_message(self, text, chat_id=None):
        target_chat_id = (chat_id or self.default_chat_id).strip()

        if not target_chat_id:
            raise TelegramConfigurationError(
                "No hay Telegram Chat ID configurado para el destino."
            )

        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        endpoint = (
            f"{self.api_base_url}/bot{self.token}/sendMessage"
        )
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_body = response.read()
        except HTTPError as error:
            retryable = error.code == 429 or error.code >= 500
            raise TelegramError(
                f"Telegram respondio con HTTP {error.code}.",
                retryable=retryable,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise TelegramError(
                "No fue posible comunicarse con Telegram.",
                retryable=True,
            ) from None

        try:
            result = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TelegramError(
                "Telegram devolvio una respuesta invalida.",
                retryable=True,
            ) from None

        if not result.get("ok"):
            error_code = result.get("error_code", 0)
            retryable = error_code == 429 or error_code >= 500
            raise TelegramError(
                f"Telegram rechazo el mensaje. Codigo: {error_code}.",
                retryable=retryable,
            )

        message = result.get("result") or {}
        return str(message.get("message_id") or "")
