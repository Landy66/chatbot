"""Gemeinsame Test-Fixtures und deterministische Fakes für Unit- und Integrationstests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic import SecretStr
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from ai_assistant.agent import create_agent
from ai_assistant.chat_service import ChatService
from ai_assistant.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Liefert deterministische Test-Einstellungen mit sicherem Dummy-Key."""
    return Settings(
        openai_api_key=SecretStr("sk-dummy-test-secret-key-12345"),
        openai_model="gpt-5-mini",
        app_host="127.0.0.1",
        app_port=7860,
        log_level="DEBUG",
        max_input_chars=1000,
        max_context_turns=5,
        max_context_chars=5000,
        max_ui_turns=20,
        max_output_tokens=500,
        run_timeout_seconds=5.0,
        max_retries=2,
        max_concurrent_runs=2,
        max_queue_size=4,
    )


def create_fake_streaming_model(
    chunks: list[str] | None = None,
    delay: float = 0.01,
) -> FunctionModel:
    """Erzeugt ein deterministisches Streaming-Fake-Modell mit Pydantic AI FunctionModel."""
    if chunks is None:
        chunks = ["Hallo ", "ich bin ", "ein KI-Assistent."]

    async def stream_fn(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str]:
        for c in chunks:
            yield c
            if delay > 0:
                await asyncio.sleep(delay)

    return FunctionModel(stream_function=stream_fn)


@pytest.fixture
def fake_agent(test_settings: Settings) -> Agent[None, str]:
    """Erzeugt einen Agenten mit deterministischem Fake-Modell."""
    model = create_fake_streaming_model()
    return create_agent(test_settings, model=model)


@pytest.fixture
def fake_chat_service(fake_agent: Agent[None, str], test_settings: Settings) -> ChatService:
    """Erzeugt einen ChatService mit deterministischem Fake-Agenten."""
    return ChatService(fake_agent, test_settings)
