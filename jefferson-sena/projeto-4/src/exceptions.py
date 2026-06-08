"""Exceções com mensagens orientadas ao usuário."""


class PipelineError(Exception):
    """Erro base do pipeline UDA."""


class LLMConfigurationError(PipelineError):
    """Problema de configuração ou cota do provedor LLM."""


# Alias para compatibilidade
OpenAIConfigurationError = LLMConfigurationError


class DatabaseConnectionError(PipelineError):
    """Problema de conexão com o PostgreSQL."""


def format_llm_error(exc: Exception, provider: str = "openai") -> LLMConfigurationError:
    msg = str(exc).lower()

    if provider == "gemini":
        if "api key" in msg or "api_key_invalid" in msg or "permission_denied" in msg:
            return LLMConfigurationError(
                "GEMINI_API_KEY inválida. Gere uma chave gratuita em "
                "https://aistudio.google.com/apikey e configure no .env"
            )
        if "quota" in msg or "resource_exhausted" in msg or "429" in msg:
            return LLMConfigurationError(
                "Cota do Gemini esgotada (erro 429). Aguarde o reset do limite gratuito "
                "ou verifique uso em https://aistudio.google.com/"
            )
        if "rate" in msg or "limit" in msg:
            return LLMConfigurationError(
                "Limite de requisições do Gemini atingido. Aguarde e tente novamente."
            )
        return LLMConfigurationError(f"Erro na API Gemini: {exc}")

    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return LLMConfigurationError(
            "Cota da OpenAI esgotada (erro 429). "
            "Adicione créditos em https://platform.openai.com/account/billing "
            "ou troque para Gemini: LLM_PROVIDER=gemini no .env"
        )
    if "invalid_api_key" in msg or "incorrect api key" in msg:
        return LLMConfigurationError(
            "OPENAI_API_KEY inválida. Atualize o arquivo .env com uma chave válida."
        )
    if "rate_limit" in msg:
        return LLMConfigurationError(
            "Limite de requisições da OpenAI atingido (rate limit). Aguarde e tente novamente."
        )
    return LLMConfigurationError(f"Erro na API OpenAI: {exc}")


def format_openai_error(exc: Exception) -> LLMConfigurationError:
    """Wrapper legado que formata erros assumindo provedor OpenAI."""
    return format_llm_error(exc, provider="openai")


def format_database_error(exc: Exception) -> DatabaseConnectionError:
    msg = str(exc).lower()
    if "postgres" in msg and ("name resolution" in msg or "could not translate host" in msg):
        return DatabaseConnectionError(
            "Não foi possível resolver o host 'postgres'. "
            "Você está rodando o CLI fora do Docker, mas o DATABASE_URL aponta para o host interno do Compose. "
            "Soluções:\n"
            "  1) Rodar dentro do container: docker-compose exec api python -m src.cli ...\n"
            "  2) Usar só extração: adicione --no-persist\n"
            "  3) No .env local use: DATABASE_URL=postgresql://uda:uda_secret@localhost:5433/uda_habitacional"
        )
    return DatabaseConnectionError(f"Erro de conexão com o banco: {exc}")
