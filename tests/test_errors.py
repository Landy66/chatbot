"""Tests für Fehlerklassifikation, Secret-Redaktion und Logging (AC-10, AC-11)."""

from __future__ import annotations

import logging

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from ai_assistant.agent import create_agent
from ai_assistant.chat_service import ChatService
from ai_assistant.config import Settings
from ai_assistant.errors import (
    AssistantTimeoutError,
    AuthenticationError,
    ConnectionError,
    ModelAccessError,
    RateLimitError,
    classify_error,
    redact_secret_string,
)
from ai_assistant.logging_config import RedactingFormatter
from ai_assistant.models import ErrorEvent, SessionState


def test_redact_secret_string() -> None:
    """AC-11: Prüft, dass Secrets zuverlässig aus Strings entfernt werden."""
    secret = "sk-proj-1234567890abcdefghijklmnop"
    text = f"Fehler bei Anfrage mit Schlüssel {secret} an OpenAI."
    redacted = redact_secret_string(text, secret)
    assert secret not in redacted
    assert "[REDACTED_SECRET]" in redacted or "[REDACTED_API_KEY]" in redacted

    groq_secret = "gsk_1234567890abcdef1234567890"
    text_groq = f"Fehler mit Schlüssel {groq_secret} an Groq."
    redacted_groq = redact_secret_string(text_groq)
    assert groq_secret not in redacted_groq
    assert "[REDACTED_API_KEY]" in redacted_groq


def test_redacting_formatter() -> None:
    """AC-11: Prüft, dass der RedactingFormatter Secrets in Log-Records maskiert."""
    secret = "sk-super-secret-key-to-hide"
    RedactingFormatter.register_secret(secret)
    formatter = RedactingFormatter(fmt="%(message)s")

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg=f"Traceback mit Key {secret} aufgetreten.",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert secret not in formatted
    assert "[REDACTED_SECRET]" in formatted


def test_classify_error_types() -> None:
    """AC-10: Prüft die korrekte Klassifizierung verschiedener Exception-Typen."""
    secret = "sk-test-secret-123"

    # 401
    exc_401 = Exception(f"401 Unauthorized: invalid_api_key {secret}")
    res_401 = classify_error(exc_401, secret)
    assert isinstance(res_401, AuthenticationError)
    assert secret not in res_401.user_message
    assert "Authentifizierungsfehler" in res_401.user_message

    # 403 / 404
    exc_404 = Exception(f"404 The model `gpt-5-mini` does not exist for key {secret}")
    res_404 = classify_error(exc_404, secret)
    assert isinstance(res_404, ModelAccessError)
    assert secret not in res_404.user_message
    assert "Modellzugriffsfehler" in res_404.user_message

    # 429
    exc_429 = Exception("429 Rate limit exceeded. Please try again later.")
    res_429 = classify_error(exc_429, secret)
    assert isinstance(res_429, RateLimitError)
    assert "Ratenbegrenzung" in res_429.user_message

    # Timeout
    exc_timeout = TimeoutError("Request timed out after 30 seconds.")
    res_timeout = classify_error(exc_timeout, secret)
    assert isinstance(res_timeout, AssistantTimeoutError)
    assert "Zeitüberschreitung" in res_timeout.user_message

    # Connection
    exc_conn = Exception("APIConnectionError: Failed to connect to api.openai.com")
    res_conn = classify_error(exc_conn, secret)
    assert isinstance(res_conn, ConnectionError)
    assert "Verbindungsfehler" in res_conn.user_message


@pytest.mark.asyncio
async def test_error_flow_in_chat_service(test_settings: Settings) -> None:
    """AC-10: Fehler liefern sichere Meldungen, verändern den erfolgreichen Verlauf nicht."""

    async def failing_stream(messages: list[ModelMessage], info: AgentInfo):
        raise Exception("401 Unauthorized: invalid_api_key sk-secret-error-123")
        yield "Never yielded"

    agent = create_agent(test_settings, model=FunctionModel(stream_function=failing_stream))
    chat_service = ChatService(agent, test_settings)
    session_state = SessionState()

    events = [ev async for ev in chat_service.stream_chat(session_state, "Frage")]
    assert len(events) == 1
    assert isinstance(events[0], ErrorEvent)
    assert "Authentifizierungsfehler" in events[0].error_message
    assert "sk-secret-error-123" not in events[0].error_message
    # Erfolgreicher Verlauf bleibt unberührt
    assert len(session_state.messages) == 0
    assert session_state.is_busy is False
