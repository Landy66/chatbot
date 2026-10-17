"""Fehlerdefinitionen und sichere Fehlerklassifikation für den KI-Assistenten."""

from __future__ import annotations

import asyncio
import re


def redact_secret_string(text: str, secret: str | list[str] | tuple[str, ...] | None = None) -> str:
    """Entfernt sensible Schlüssel und typische API-Key-Muster aus Texten."""
    if not text:
        return text

    result = text
    if isinstance(secret, (list, tuple, set)):
        for s in secret:
            if s and s.strip():
                result = result.replace(s.strip(), "[REDACTED_SECRET]")
    elif secret and secret.strip():
        result = result.replace(secret.strip(), "[REDACTED_SECRET]")

    # Reduziert typische OpenAI-Key-Muster (sk-...), Google (AIza...) und Groq (gsk_...)
    result = re.sub(r"sk-[a-zA-Z0-9_-]{10,}", "[REDACTED_API_KEY]", result)
    result = re.sub(r"AIza[a-zA-Z0-9_-]{20,}", "[REDACTED_API_KEY]", result)
    result = re.sub(r"gsk_[a-zA-Z0-9_-]{20,}", "[REDACTED_API_KEY]", result)
    return result


class AssistantError(Exception):
    """Basisklasse für alle anwendungsspezifischen Fehler."""

    def __init__(self, user_message: str, internal_details: str = "") -> None:
        self.user_message = user_message
        self.internal_details = internal_details
        super().__init__(user_message)


class ConfigurationError(AssistantError):
    """Fehler in der Konfiguration (z. B. fehlender API-Schlüssel)."""


class InputValidationError(AssistantError):
    """Ungültige Benutzereingabe (z. B. zu lang oder nur Whitespace)."""


class AuthenticationError(AssistantError):
    """Authentifizierungsfehler beim Modellanbieter (401)."""


class ModelAccessError(AssistantError):
    """Fehlende Berechtigung oder Modell nicht verfügbar (403/404)."""


class RateLimitError(AssistantError):
    """Ratenbegrenzung beim Modellanbieter erreicht (429)."""


class ConnectionError(AssistantError):
    """Netzwerk- oder Verbindungsfehler zum Modellanbieter."""


class AssistantTimeoutError(AssistantError):
    """Zeitüberschreitung bei der Verarbeitung oder Anfrage."""


class QueueFullError(AssistantError):
    """Warteschlange für gleichzeitige Anfragen ist voll."""


class RunCancelledError(AssistantError):
    """Der laufende Modellaufruf wurde durch den Nutzer abgebrochen."""


class UnexpectedError(AssistantError):
    """Unerwarteter Systemfehler."""


def classify_error(exc: Exception, secret_to_redact: str | None = None) -> AssistantError:
    """Klassifiziert eine beliebige Exception in eine sichere AssistantError-Klasse.

    Garantiert eine benutzerfreundliche deutsche Fehlermeldung ohne
    Offenlegung von API-Schlüsseln oder sensiblen Systemdaten.
    """
    if isinstance(exc, AssistantError):
        exc.user_message = redact_secret_string(exc.user_message, secret_to_redact)
        return exc

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return AssistantTimeoutError(
            user_message=(
                "Zeitüberschreitung: Die Anfrage an den Assistenten hat das "
                "Zeitlimit überschritten."
            ),
            internal_details=redact_secret_string(str(exc), secret_to_redact),
        )

    if isinstance(exc, asyncio.CancelledError):
        return RunCancelledError(
            user_message="Die Antwortgenerierung wurde abgebrochen.",
            internal_details="asyncio.CancelledError",
        )

    # Prüfe OpenAI- und Pydantic-AI-Fehlertypen
    exc_type = type(exc).__name__
    raw_msg = str(exc)
    safe_raw_msg = redact_secret_string(raw_msg, secret_to_redact)
    status_code = getattr(exc, "status_code", None)

    if (
        status_code == 401
        or exc_type == "AuthenticationError"
        or "401" in safe_raw_msg
        or "invalid_api_key" in safe_raw_msg
        or "unauthorized" in safe_raw_msg.lower()
    ):
        return AuthenticationError(
            user_message=("Authentifizierungsfehler: Der API-Key ist ungültig oder abgelaufen."),
            internal_details=safe_raw_msg,
        )

    if (
        status_code in (403, 404)
        or exc_type in ("PermissionDeniedError", "NotFoundError")
        or "403" in safe_raw_msg
        or "404" in safe_raw_msg
        or "model_not_found" in safe_raw_msg
        or "does not exist" in safe_raw_msg.lower()
    ):
        return ModelAccessError(
            user_message=(
                "Modellzugriffsfehler: Das gewählte Modell ist nicht verfügbar oder "
                "der API-Key besitzt keine Zugriffsberechtigung."
            ),
            internal_details=safe_raw_msg,
        )

    if (
        status_code == 429
        or exc_type == "RateLimitError"
        or "429" in safe_raw_msg
        or "rate_limit" in safe_raw_msg.lower()
        or "quota" in safe_raw_msg.lower()
        or "credit" in safe_raw_msg.lower()
        or "billing" in safe_raw_msg.lower()
        or "resource_exhausted" in safe_raw_msg.lower()
    ):
        return RateLimitError(
            user_message=(
                "Ratenbegrenzung oder Kontingentlimit erreicht (429/Quota). "
                "Bitte kurz warten oder Kontingent beim Modellanbieter prüfen."
            ),
            internal_details=safe_raw_msg,
        )

    if (
        exc_type in ("APITimeoutError", "TimeoutError")
        or isinstance(exc, (TimeoutError, asyncio.TimeoutError))
        or "timed out" in safe_raw_msg.lower()
    ):
        return AssistantTimeoutError(
            user_message=(
                "Zeitüberschreitung: Die Anfrage an den Assistenten hat das "
                "Zeitlimit überschritten."
            ),
            internal_details=safe_raw_msg,
        )

    if (
        status_code in (500, 502, 503, 504)
        or exc_type in ("APIConnectionError", "ConnectError", "NetworkError")
        or "connection" in safe_raw_msg.lower()
    ):
        return ConnectionError(
            user_message=(
                "Verbindungsfehler: Der Modellanbieter konnte nicht erreicht werden. "
                "Bitte Internetverbindung prüfen."
            ),
            internal_details=safe_raw_msg,
        )

    return UnexpectedError(
        user_message="Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es erneut.",
        internal_details=safe_raw_msg,
    )
