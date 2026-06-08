"""Download de PDFs com cálculo de hash e persistência."""

import logging
import re
from pathlib import Path

import httpx

from src.catalog.repository import CatalogRepository, compute_bytes_hash
from src.config import get_settings

logger = logging.getLogger(__name__)

PERIOD_PATTERNS = [
    re.compile(r"(\d{4}).*?([1-4])[\s_-]?t", re.IGNORECASE),
    re.compile(r"(\d{4}).*?q([1-4])", re.IGNORECASE),
    re.compile(r"(\d{4}).*?trimestre[\s_-]?([1-4])", re.IGNORECASE),
]


def infer_period_from_text(text: str) -> tuple[int | None, int | None]:
    """
    Infere ano e trimestre a partir de URL ou nome de arquivo.

    Busca padrões como '2025-3T', '2024_Q2' ou 'trimestre_3'.

    Args:
        text: URL ou nome do arquivo PDF.

    Returns:
        Tupla (ano, trimestre) ou (None, None) se não identificado.
    """
    for pattern in PERIOD_PATTERNS:
        match = pattern.search(text)
        if match:
            ano = int(match.group(1))
            trimestre = int(match.group(2)) if match.lastindex >= 2 else None
            if trimestre is None:
                t_match = re.search(r"([1-4])[\s_-]?t", text, re.IGNORECASE)
                trimestre = int(t_match.group(1)) if t_match else 1
            return ano, trimestre
    year_match = re.search(r"(20\d{2})", text)
    if year_match:
        return int(year_match.group(1)), 1
    return None, None


def download_pdf(url: str, dest_dir: Path, filename: str | None = None) -> tuple[Path, str]:
    """
    Baixa um PDF de uma URL e salva no diretório de destino.

    Args:
        url: URL pública do PDF.
        dest_dir: Diretório onde o arquivo será salvo.
        filename: Nome opcional; usa hash curto se omitido.

    Returns:
        Tupla (caminho_do_arquivo, sha256_hex).

    Raises:
        httpx.HTTPError: Se o download falhar.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "UDA-Habitacional-Bot/1.0 (projeto-academico-unb)"}

    with httpx.Client(follow_redirects=True, timeout=60.0, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        content = response.content

    file_hash = compute_bytes_hash(content)
    name = filename or f"{file_hash[:12]}.pdf"
    dest_path = dest_dir / name
    dest_path.write_bytes(content)
    return dest_path, file_hash


class PDFDownloader:
    """Gerencia download e registro de PDFs com deduplicação por hash."""

    def __init__(self, repo: CatalogRepository):
        """
        Args:
            repo: Repositório do catálogo para verificar duplicatas.
        """
        self.repo = repo
        self.settings = get_settings()

    def ingest_pdf_url(
        self,
        url: str,
        empresa: str,
        ano: int | None = None,
        trimestre: int | None = None,
        tipo_documento: str = "previa_operacional",
    ) -> tuple[str, str | None]:
        """
        Baixa PDF da URL e registra no catálogo se for novo (hash inédito).

        Args:
            url: URL do PDF na Central de Resultados.
            empresa: Nome da construtora.
            ano: Ano opcional; inferido da URL se omitido.
            trimestre: Trimestre opcional; inferido da URL se omitido.
            tipo_documento: Tipo do relatório.

        Returns:
            Tupla (status, document_id):
            - ('created', uuid) se novo documento foi registrado
            - ('skipped', None) se hash já existia
            - ('error', None) em falha de download ou persistência
        """
        try:
            inferred_ano, inferred_trim = infer_period_from_text(url)
            ano = ano or inferred_ano or 2025
            trimestre = trimestre or inferred_trim or 1

            dest_dir = self.settings.pdf_storage / empresa / str(ano) / f"T{trimestre}"
            dest_path, file_hash = download_pdf(url, dest_dir)

            if self.repo.document_exists_by_hash(file_hash):
                logger.info("PDF já processado (hash=%s), ignorando", file_hash[:12])
                dest_path.unlink(missing_ok=True)
                return "skipped", None

            doc = self.repo.create_document(
                empresa=empresa,
                ano=ano,
                trimestre=trimestre,
                source_url=url,
                file_hash=file_hash,
                storage_path=str(dest_path),
                tipo_documento=tipo_documento,
            )
            return "created", str(doc.id)
        except Exception as e:
            logger.exception("Erro ao ingerir PDF %s: %s", url, e)
            return "error", None
