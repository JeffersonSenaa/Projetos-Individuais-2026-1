"""Motor de extração UDA com LLM (Gemini ou OpenAI) + Instructor."""

import base64
import logging
from pathlib import Path

from src.config import get_settings
from src.contracts.conjuntura import (
    ExtracaoConjuntura,
    ExtracaoConjunturaParcial,
    MetricaOperacional,
)
from src.exceptions import format_llm_error
from src.extraction.chunker import DocumentChunk, chunk_document
from src.extraction.llm_client import create_llm_client
from src.extraction.parser import parse_pdf, render_page_as_png
from src.extraction.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, VISION_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class UDAExtractor:
    """Extrai métricas de PDFs usando LLM com contrato semântico Pydantic."""

    def __init__(self) -> None:
        """Inicializa cliente LLM conforme LLM_PROVIDER (gemini ou openai)."""
        settings = get_settings()
        self.provider = settings.llm_provider
        self.model = settings.gemini_model if self.provider == "gemini" else settings.openai_model
        self.vision_model = (
            settings.gemini_vision_model if self.provider == "gemini" else settings.openai_vision_model
        )
        self.client = create_llm_client(settings)

    def extract_from_pdf(
        self,
        pdf_path: Path,
        empresa: str,
        ano: int,
        trimestre: int,
    ) -> ExtracaoConjuntura:
        """
        Pipeline completo de extração: parse → chunk → LLM → merge.

        Para cada chunk, chama o LLM e mescla métricas por chave, preferindo
        valores com evidência textual quando há duplicatas.

        Args:
            pdf_path: Caminho do PDF a processar.
            empresa: Nome da construtora ou entidade do relatório.
            ano: Ano de referência do trimestre.
            trimestre: Trimestre (1-4).

        Returns:
            ExtracaoConjuntura validada pelo contrato semântico Pydantic.
        """
        pages = parse_pdf(pdf_path)
        chunks = chunk_document(pages)
        all_metrics: dict[str, MetricaOperacional] = {}

        for chunk in chunks:
            partial = self._extract_chunk(pdf_path, chunk, empresa, ano, trimestre)
            for metric in partial.metricas:
                existing = all_metrics.get(metric.chave)
                if existing is None or (
                    metric.valor_absoluto is not None
                    and (existing.valor_absoluto is None or metric.trecho_evidencia)
                ):
                    all_metrics[metric.chave] = metric

        return ExtracaoConjuntura(
            empresa=empresa,
            ano=ano,
            trimestre=trimestre,
            metricas=list(all_metrics.values()),
        )

    def _call_llm(self, messages: list, response_model, model: str | None = None):
        """
        Envia mensagens ao LLM via Instructor com saída estruturada Pydantic.

        Args:
            messages: Lista de mensagens no formato chat (system/user).
            response_model: Classe Pydantic esperada na resposta.
            model: Modelo opcional (ex.: vision); usa self.model se omitido.

        Returns:
            Instância validada de response_model.

        Raises:
            LLMConfigurationError: Em falhas de API, cota ou chave inválida.
        """
        try:
            return self.client.create(
                model=model or self.model,
                response_model=response_model,
                messages=messages,
                max_retries=2,
            )
        except Exception as e:
            logger.warning("Falha na chamada LLM (%s): %s", self.provider, e)
            raise format_llm_error(e, self.provider) from e

    def _extract_chunk(
        self,
        pdf_path: Path,
        chunk: DocumentChunk,
        empresa: str,
        ano: int,
        trimestre: int,
    ) -> ExtracaoConjunturaParcial:
        """
        Extrai métricas de um único chunk de texto ou imagem.

        Args:
            pdf_path: Caminho do PDF (necessário para vision em slides).
            chunk: Trecho do documento a processar.
            empresa: Nome da empresa.
            ano: Ano de referência.
            trimestre: Trimestre de referência.

        Returns:
            Métricas parciais encontradas neste chunk.
        """
        if chunk.is_image:
            return self._extract_vision(pdf_path, chunk, empresa, ano, trimestre)

        if not chunk.text.strip():
            return ExtracaoConjunturaParcial(metricas=[])

        user_prompt = USER_PROMPT_TEMPLATE.format(
            empresa=empresa,
            ano=ano,
            trimestre=trimestre,
            pagina=chunk.page_number,
            chunk_text=chunk.text[:12000],
        )

        return self._call_llm(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ExtracaoConjunturaParcial,
        )

    def _extract_vision(
        self,
        pdf_path: Path,
        chunk: DocumentChunk,
        empresa: str,
        ano: int,
        trimestre: int,
    ) -> ExtracaoConjunturaParcial:
        """
        Extrai métricas de slide rasterizado via modelo multimodal (vision).

        Renderiza a página como PNG e envia imagem + prompt ao LLM.
        Formato da imagem varia conforme o provedor (Gemini Part vs OpenAI base64).

        Args:
            pdf_path: Caminho do PDF.
            chunk: Chunk marcado como is_image=True.
            empresa: Nome da empresa.
            ano: Ano de referência.
            trimestre: Trimestre de referência.

        Returns:
            Métricas visíveis na imagem do slide.
        """
        png_bytes = render_page_as_png(pdf_path, chunk.page_number)
        user_prompt = VISION_PROMPT_TEMPLATE.format(
            empresa=empresa,
            ano=ano,
            trimestre=trimestre,
            pagina=chunk.page_number,
        )

        if self.provider == "gemini":
            from google.genai import types

            user_content = [
                user_prompt,
                types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            ]
        else:
            b64 = base64.b64encode(png_bytes).decode("utf-8")
            user_content = [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            ]

        return self._call_llm(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_model=ExtracaoConjunturaParcial,
            model=self.vision_model,
        )


def merge_extractions(extractions: list[ExtracaoConjunturaParcial]) -> list[MetricaOperacional]:
    """
    Mescla métricas de múltiplos chunks, deduplicando por chave.

    Prefere entradas com valor_absoluto preenchido e trecho_evidencia presente.

    Args:
        extractions: Lista de extrações parciais por chunk.

    Returns:
        Lista única de métricas mescladas.
    """
    merged: dict[str, MetricaOperacional] = {}
    for ext in extractions:
        for metric in ext.metricas:
            existing = merged.get(metric.chave)
            if existing is None or (
                metric.valor_absoluto is not None
                and (existing.valor_absoluto is None or metric.trecho_evidencia)
            ):
                merged[metric.chave] = metric
    return list(merged.values())
