"""Testes unitários do pipeline UDA (sem chamadas à API LLM)."""

from decimal import Decimal
from pathlib import Path

import pytest

from src.contracts.conjuntura import ExtracaoConjuntura, MetricaOperacional
from src.extraction.chunker import chunk_document
from src.extraction.parser import PageContent, parse_pdf
from src.ingestion.downloader import infer_period_from_text


class TestContratoSemantico:
    """Testes de validação do contrato semântico Pydantic."""

    def test_metrica_valida(self):
        """Aceita métrica com valor absoluto positivo e evidência textual."""
        m = MetricaOperacional(
            chave="unidades_vendidas",
            valor_absoluto=Decimal("12340"),
            unidade="unidades",
            periodo="3T25",
            pagina=4,
            trecho_evidencia="12.340 unidades vendidas",
        )
        assert m.valor_absoluto == Decimal("12340")

    def test_metrica_null_permitida(self):
        """Permite valor_absoluto null quando métrica ausente no documento."""
        m = MetricaOperacional(
            chave="vgv",
            valor_absoluto=None,
            unidade="milhoes_R$",
            periodo="3T25",
        )
        assert m.valor_absoluto is None

    def test_valor_negativo_rejeitado(self):
        """Rejeita valores absolutos negativos."""
        with pytest.raises(ValueError):
            MetricaOperacional(
                chave="vso",
                valor_absoluto=Decimal("-1"),
                unidade="percentual_absoluto",
                periodo="3T25",
            )

    def test_extracao_conjuntura_trimestre_invalido(self):
        """Rejeita trimestre fora do intervalo 1-4."""
        with pytest.raises(ValueError):
            ExtracaoConjuntura(empresa="MRV", ano=2025, trimestre=5, metricas=[])


class TestInferPeriod:
    """Testes de inferência de ano/trimestre a partir de URL ou nome de arquivo."""

    def test_url_3t25(self):
        """Extrai ano 2025 e trimestre 3 de URL com padrão 3T."""
        ano, trim = infer_period_from_text("https://ri.mrv.com.br/previa-operacional-2025-3T.pdf")
        assert ano == 2025
        assert trim == 3

    def test_url_q2(self):
        """Extrai ano 2024 e trimestre 2 de nome com padrão Q2."""
        ano, trim = infer_period_from_text("resultados_2024_Q2.pdf")
        assert ano == 2024
        assert trim == 2


class TestChunking:
    """Testes da estratégia híbrida de chunking semântico."""

    def test_full_scan_documento_curto(self):
        """Documentos com <=15 páginas incluem todas as páginas (full-scan)."""
        pages = [
            PageContent(page_number=i, text=f"Vendas unidades VSO estoque página {i}", is_likely_image=False)
            for i in range(1, 6)
        ]
        chunks = chunk_document(pages)
        assert len(chunks) == 5

    def test_chunking_longo_filtra_irrelevante(self):
        """Documentos longos filtram páginas sem keywords operacionais."""
        pages = [
            PageContent(page_number=1, text="Sumário executivo institucional", is_likely_image=False),
            PageContent(page_number=2, text="VSO 24,5% unidades vendidas 12.340", is_likely_image=False),
        ] + [
            PageContent(page_number=i, text=f"Página institucional {i}", is_likely_image=False)
            for i in range(3, 20)
        ]
        chunks = chunk_document(pages)
        relevant = [c for c in chunks if "VSO" in c.text or c.is_image]
        assert len(relevant) >= 1

    def test_pagina_imagem_detectada(self):
        """Páginas sem texto são marcadas como is_image para vision."""
        pages = [PageContent(page_number=1, text="", is_likely_image=True)]
        chunks = chunk_document(pages)
        assert chunks[0].is_image is True


class TestParser:

    @pytest.fixture
    def boletim_path(self) -> Path | None:
        """Retorna caminho do PDF fixture do Boletim 3T25 se existir."""
        path = Path(__file__).parent / "fixtures" / "exemplo_Boletim_Conjuntura_2025_3T.pdf"
        return path if path.exists() else None

    def test_parse_boletim_se_existir(self, boletim_path):
        """Verifica extração de texto do Boletim de Conjuntura de exemplo."""
        if boletim_path is None:
            pytest.skip("Fixture PDF não disponível")
        pages = parse_pdf(boletim_path)
        assert len(pages) > 0
        assert any(len(p.text) > 0 for p in pages)


class TestHashDedup:
    """Testes de cálculo de hash SHA-256 para deduplicação."""

    def test_hash_deterministico(self, tmp_path):
        """Hash de arquivo e bytes idênticos deve ser igual e ter 64 caracteres."""
        from src.catalog.repository import compute_bytes_hash, compute_file_hash

        content = b"%PDF-1.4 test content"
        f = tmp_path / "test.pdf"
        f.write_bytes(content)
        assert compute_file_hash(f) == compute_bytes_hash(content)
        assert len(compute_file_hash(f)) == 64
