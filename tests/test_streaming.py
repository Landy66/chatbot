"""Tests für echtes Streaming und Memory-Aktualisierung (AC-03, AC-04)."""

from __future__ import annotations

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse

from ai_assistant.chat_service import ChatService
from ai_assistant.models import ChunkEvent, CompletedEvent, SessionState


@pytest.mark.asyncio
async def test_deterministic_streaming_three_chunks(fake_chat_service: ChatService) -> None:
    """AC-03: Deterministischer Test zeigt mindestens 3 wachsende Zwischenstände vor Abschluss."""
    session_state = SessionState()
    prompt = "Hallo Test"

    events = []
    chunk_contents = []

    async for event in fake_chat_service.stream_chat(session_state, prompt):
        events.append(event)
        if isinstance(event, ChunkEvent):
            chunk_contents.append(event.content)

    # Mindestens 3 Chunks
    assert len(chunk_contents) >= 3, f"Zu wenige Chunks: {chunk_contents}"

    # Wachsende Zwischenstände
    for i in range(1, len(chunk_contents)):
        assert len(chunk_contents[i]) > len(chunk_contents[i - 1])

    # Letztes Ereignis muss CompletedEvent sein
    assert isinstance(events[-1], CompletedEvent)
    assert events[-1].full_text == "Hallo ich bin ein KI-Assistent."
    assert events[-1].usage.total_tokens is not None


@pytest.mark.asyncio
async def test_memory_multi_turn_history(fake_chat_service: ChatService) -> None:
    """AC-04: Zweiter Lauf erhält vollständige erste Frage und Antwort genau einmal."""
    session_state = SessionState()

    # 1. Turn
    async for _ in fake_chat_service.stream_chat(session_state, "Erste Frage"):
        pass

    assert len(session_state.messages) == 2
    assert isinstance(session_state.messages[0], ModelRequest)
    assert isinstance(session_state.messages[1], ModelResponse)

    # 2. Turn
    async for _ in fake_chat_service.stream_chat(session_state, "Zweite Frage"):
        pass

    # Nach dem 2. Turn müssen genau 4 Nachrichten existieren: Req 1, Resp 1, Req 2, Resp 2
    assert len(session_state.messages) == 4
    # Prüfe, dass keine Duplikate existieren
    requests = [m for m in session_state.messages if isinstance(m, ModelRequest)]
    responses = [m for m in session_state.messages if isinstance(m, ModelResponse)]
    assert len(requests) == 2
    assert len(responses) == 2
