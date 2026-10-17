"""Tests für Isolation, Reset, Stop, Doppelsenden und Limits (AC-05 bis AC-09)."""

from __future__ import annotations

import asyncio

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from ai_assistant.agent import create_agent
from ai_assistant.chat_service import ChatService
from ai_assistant.config import Settings
from ai_assistant.models import (
    ChunkEvent,
    CompletedEvent,
    ErrorEvent,
    SessionState,
)


@pytest.mark.asyncio
async def test_session_isolation(fake_chat_service: ChatService) -> None:
    """AC-05: Zwei interleavte Sessions sehen ausschließlich eigene Nachrichten."""
    session_a = SessionState()
    session_b = SessionState()

    async for _ in fake_chat_service.stream_chat(session_a, "Frage A1"):
        pass

    async for _ in fake_chat_service.stream_chat(session_b, "Frage B1"):
        pass

    assert len(session_a.messages) == 2
    assert len(session_b.messages) == 2
    assert session_a.session_id != session_b.session_id


@pytest.mark.asyncio
async def test_reset_discards_active_run_and_clears_history(test_settings: Settings) -> None:
    """AC-06: Nach Reset sind UI und History leer; verspätete Chunks und Commit werden verworfen."""
    started_event = asyncio.Event()

    async def slow_stream(messages: list[ModelMessage], info: AgentInfo):
        yield "Teil 1 "
        started_event.set()
        await asyncio.sleep(0.5)
        yield "Teil 2"

    agent = create_agent(test_settings, model=FunctionModel(stream_function=slow_stream))
    chat_service = ChatService(agent, test_settings)
    session_state = SessionState()

    async def run_client():
        events = []
        try:
            async for ev in chat_service.stream_chat(session_state, "Frage vor Reset"):
                events.append(ev)
        except asyncio.CancelledError:
            pass
        return events

    task = asyncio.create_task(run_client())
    await started_event.wait()

    # Reset durchführen während des Laufs
    chat_service.reset_session(session_state)

    try:
        events = await task
    except asyncio.CancelledError:
        events = []

    # Nach Reset ist SessionState vollständig geleert
    assert len(session_state.messages) == 0
    assert session_state.active_run_id is None
    assert session_state.is_busy is False
    # Der Lauf darf nicht als Completed abgeschlossen worden sein
    assert not any(isinstance(ev, CompletedEvent) for ev in events)


@pytest.mark.asyncio
async def test_stop_releases_session_and_marks_partial(test_settings: Settings) -> None:
    """AC-07: Stop gibt UI lokal frei; Teilantwort wird nicht in History übernommen."""
    started_event = asyncio.Event()

    async def slow_stream(messages: list[ModelMessage], info: AgentInfo):
        yield "Erster Teil "
        started_event.set()
        await asyncio.sleep(1.0)
        yield "Zweiter Teil"

    agent = create_agent(test_settings, model=FunctionModel(stream_function=slow_stream))
    chat_service = ChatService(agent, test_settings)
    session_state = SessionState()

    async def run_client():
        events = []
        try:
            async for ev in chat_service.stream_chat(session_state, "Lange Frage"):
                events.append(ev)
        except asyncio.CancelledError:
            pass
        return events

    task = asyncio.create_task(run_client())
    await started_event.wait()

    # Lokales Stop auslösen
    chat_service.stop_session(session_state)
    await asyncio.sleep(0.05)
    task.cancel()

    assert session_state.is_busy is False
    assert session_state.active_run_id is None
    # Teilantwort darf NICHT in die autoritative History übernommen worden sein
    assert len(session_state.messages) == 0

    # Neuer Lauf muss sofort möglich sein
    events_new = []
    async for ev in chat_service.stream_chat(session_state, "Neue kurze Frage"):
        events_new.append(ev)

    assert any(isinstance(ev, ChunkEvent) for ev in events_new)
    assert any(isinstance(ev, CompletedEvent) for ev in events_new)
    assert len(session_state.messages) == 2


@pytest.mark.asyncio
async def test_prevent_concurrent_runs_in_same_session(test_settings: Settings) -> None:
    """AC-08: Zwei gleichzeitige Sendesignale erzeugen höchstens einen aktiven Lauf."""
    started_event = asyncio.Event()

    async def hanging_stream(messages: list[ModelMessage], info: AgentInfo):
        yield "Start "
        started_event.set()
        await asyncio.sleep(0.5)
        yield "Ende"

    agent = create_agent(test_settings, model=FunctionModel(stream_function=hanging_stream))
    chat_service = ChatService(agent, test_settings)
    session_state = SessionState()

    async def client_1():
        events = []
        async for ev in chat_service.stream_chat(session_state, "Frage 1"):
            events.append(ev)
        return events

    async def client_2():
        events = []
        async for ev in chat_service.stream_chat(session_state, "Frage 2 (Doppelklick)"):
            events.append(ev)
        return events

    task1 = asyncio.create_task(client_1())
    await started_event.wait()

    # Zweiter Aufruf während der erste noch läuft
    task2 = asyncio.create_task(client_2())

    events1 = await task1
    events2 = await task2

    # Client 2 muss mit Fehler abgewiesen worden sein
    assert any(
        isinstance(ev, ErrorEvent) and ev.error_type == "ConcurrentRunError" for ev in events2
    )
    # Client 1 muss regulär abgeschlossen sein
    assert any(isinstance(ev, CompletedEvent) for ev in events1)


@pytest.mark.asyncio
async def test_input_limits_and_validation(fake_chat_service: ChatService) -> None:
    """AC-09: Eingabegrenze wird vor Modellaufruf geprüft und leere Eingabe abgewiesen."""
    session_state = SessionState()

    # Leere Eingabe
    empty_events = [ev async for ev in fake_chat_service.stream_chat(session_state, "   ")]
    assert len(empty_events) == 1
    assert isinstance(empty_events[0], ErrorEvent)
    assert "Bitte gib eine Nachricht ein" in empty_events[0].error_message

    # Zu lange Eingabe (max_input_chars ist in test_settings auf 1000 gesetzt)
    too_long = "X" * 1500
    too_long_events = [ev async for ev in fake_chat_service.stream_chat(session_state, too_long)]
    assert len(too_long_events) == 1
    assert isinstance(too_long_events[0], ErrorEvent)
    assert "überschreitet das Limit" in too_long_events[0].error_message


@pytest.mark.asyncio
async def test_consecutive_messages_in_same_session(fake_chat_service: ChatService) -> None:
    """AC-08/AC-05: Aufeinanderfolgende Nachrichten in derselben Sitzung blockieren nicht."""
    session_state = SessionState()

    # 1. Nachricht
    events1 = [ev async for ev in fake_chat_service.stream_chat(session_state, "Nachricht 1")]
    assert any(isinstance(ev, CompletedEvent) for ev in events1)
    assert not any(isinstance(ev, ErrorEvent) for ev in events1)
    assert session_state.is_busy is False
    assert len(session_state.messages) == 2

    # 2. Nachricht in derselben Sitzung
    events2 = [ev async for ev in fake_chat_service.stream_chat(session_state, "Nachricht 2")]
    assert any(isinstance(ev, CompletedEvent) for ev in events2)
    assert not any(isinstance(ev, ErrorEvent) for ev in events2)
    assert session_state.is_busy is False
    assert len(session_state.messages) == 4
