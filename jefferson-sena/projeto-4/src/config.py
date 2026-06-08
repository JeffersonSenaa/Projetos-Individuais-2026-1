"""Configurações centralizadas do pipeline UDA."""

import os
import socket
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_postgres_host(url: str) -> str:
    if "@postgres:" not in url:
        return url
    try:
        socket.gethostbyname("postgres")
        return url
    except OSError:
        port = os.getenv("POSTGRES_HOST_PORT", "5433")
        return url.replace("@postgres:5432", f"@localhost:{port}")


class Settings(BaseSettings):
    """Variáveis de ambiente carregadas do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "gemini"  # "gemini" ou "openai"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_vision_model: str = "gemini-2.0-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o"

    database_url: str = "postgresql://uda:uda_secret@localhost:5433/uda_habitacional"
    postgres_host_port: int = 5433
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    pdf_storage_path: str = "./data/pdfs"
    scan_cron_hour: int = 6
    scan_cron_minute: int = 0

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @field_validator("database_url", mode="after")
    @classmethod
    def adapt_database_url_for_local(cls, value: str) -> str:
        """Valida e adapta DATABASE_URL para execução local ou em container."""
        return _resolve_postgres_host(value)

    @property
    def pdf_storage(self) -> Path:
        """Retorna o diretório de armazenamento de PDFs, criando-o se necessário."""
        path = Path(self.pdf_storage_path)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Retorna instância singleton das configurações (cache em memória)."""
    return Settings()
