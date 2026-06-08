"""Factory do cliente LLM (Gemini ou OpenAI) com Instructor."""

from __future__ import annotations

import instructor

from src.config import Settings, get_settings


def create_llm_client(settings: Settings | None = None):
    """
    Cria cliente Instructor configurado conforme LLM_PROVIDER.

    Args:
        settings: Configurações opcionais; usa get_settings() se omitido.

    Returns:
        Cliente Instructor com suporte a saída estruturada Pydantic.
        - gemini: via instructor.from_provider('google/{model}')
        - openai: via instructor.from_openai(OpenAI(...))
    """
    settings = settings or get_settings()

    if settings.llm_provider == "gemini":
        return instructor.from_provider(
            f"google/{settings.gemini_model}",
            api_key=settings.gemini_api_key,
        )

    from openai import OpenAI

    return instructor.from_openai(OpenAI(api_key=settings.openai_api_key))
