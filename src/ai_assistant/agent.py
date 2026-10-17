"""Agenten-Factory und Initialisierung für den KI-Assistenten."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel, GroqModelSettings
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from ai_assistant.config import Settings
from ai_assistant.prompts import SYSTEM_PROMPT


def create_agent(
    settings: Settings,
    model: Model | str | None = None,
) -> Agent[None, str]:
    """Erstellt eine wiederverwendbare Pydantic-AI-Agenteninstanz.

    Führt keine API- oder Netzwerkverbindungen beim Erstellen aus.
    Unterstützt OpenAI (OpenAIResponsesModel), Google Gemini (GoogleModel) und Groq (GroqModel).
    """
    configured_model: Model
    model_settings: Any = None

    if model is not None and not isinstance(model, str):
        configured_model = model
    elif settings.llm_provider == "groq" or (
        isinstance(model, str) and ("groq" in model.lower() or "llama" in model.lower())
    ):
        api_key = settings.groq_api_key.get_secret_value()
        provider = GroqProvider(api_key=api_key)
        model_name = model if isinstance(model, str) else settings.groq_model
        configured_model = GroqModel(
            model_name=model_name,
            provider=provider,
        )
        model_settings = GroqModelSettings(
            max_tokens=settings.max_output_tokens,
        )
    elif settings.llm_provider == "google" or (
        isinstance(model, str) and "gemini" in model.lower()
    ):
        api_key = settings.gemini_api_key.get_secret_value()
        provider = GoogleProvider(api_key=api_key)
        model_name = model if isinstance(model, str) else settings.gemini_model
        configured_model = GoogleModel(
            model_name=model_name,
            provider=provider,
        )
        model_settings = ModelSettings(
            max_tokens=settings.max_output_tokens,
        )
    else:
        api_key = settings.openai_api_key.get_secret_value()
        provider = OpenAIProvider(api_key=api_key)
        model_name = model if isinstance(model, str) else settings.openai_model
        configured_model = OpenAIResponsesModel(
            model_name=model_name,
            provider=provider,
        )
        model_settings = OpenAIResponsesModelSettings(
            openai_store=False,
            max_tokens=settings.max_output_tokens,
        )

    return Agent(
        configured_model,
        system_prompt=SYSTEM_PROMPT,
        model_settings=model_settings,
        output_type=str,
    )
