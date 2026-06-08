#!/usr/bin/env python3
"""CLI para processamento manual de PDFs locais."""

import argparse
import json
import sys
from pathlib import Path

from src.catalog.database import get_db_session, init_db
from src.catalog.models import DocumentStatus
from src.catalog.repository import CatalogRepository, compute_file_hash
from src.config import get_settings
from src.exceptions import DatabaseConnectionError, LLMConfigurationError, format_database_error
from src.extraction.extractor import UDAExtractor


def _validate_llm_key() -> None:
    """
    Verifica se a chave do provedor LLM ativo está configurada no .env.

    Raises:
        LLMConfigurationError: Se a chave estiver ausente ou for placeholder.
    """
    settings = get_settings()
    if settings.llm_provider == "gemini":
        key = settings.gemini_api_key.strip()
        if not key or key in ("your-gemini-key-here", "AIza-your-key-here"):
            raise LLMConfigurationError(
                "GEMINI_API_KEY não configurada. Gere uma chave gratuita em "
                "https://aistudio.google.com/apikey e adicione ao .env"
            )
        return

    key = settings.openai_api_key.strip()
    if not key or key == "sk-your-key-here":
        raise LLMConfigurationError(
            "OPENAI_API_KEY não configurada. Edite o .env ou use LLM_PROVIDER=gemini."
        )


def process_local_pdf(
    pdf_path: Path,
    empresa: str,
    ano: int,
    trimestre: int,
    source_url: str = "local://manual",
    persist: bool = True,
) -> dict:
    """
    Processa um PDF local: extração LLM com deduplicação e persistência opcional.

    Fluxo:
    1. Valida chave LLM e existência do arquivo.
    2. Calcula SHA-256 do PDF.
    3. Extrai métricas via UDAExtractor.
    4. Se persist=True, grava no catálogo (ignora se hash já existir).

    Args:
        pdf_path: Caminho do arquivo PDF.
        empresa: Nome da construtora ou entidade.
        ano: Ano de referência.
        trimestre: Trimestre (1-4).
        source_url: URL de origem para linhagem (padrão: local://manual).
        persist: Se True, salva no PostgreSQL; se False, só retorna JSON.

    Returns:
        Dicionário com métricas extraídas e metadados (status, document_id).

    Raises:
        FileNotFoundError: Se o PDF não existir.
        LLMConfigurationError: Se a API LLM falhar.
        DatabaseConnectionError: Se persist=True e o banco estiver inacessível.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    _validate_llm_key()
    file_hash = compute_file_hash(pdf_path)
    extractor = UDAExtractor()
    extraction = extractor.extract_from_pdf(pdf_path, empresa, ano, trimestre)

    result = {
        "empresa": extraction.empresa,
        "ano": extraction.ano,
        "trimestre": extraction.trimestre,
        "file_hash": file_hash,
        "metricas": [
            {
                "chave": m.chave,
                "valor_absoluto": str(m.valor_absoluto) if m.valor_absoluto is not None else None,
                "unidade": m.unidade,
                "periodo": m.periodo,
                "pagina": m.pagina,
                "trecho_evidencia": m.trecho_evidencia,
            }
            for m in extraction.metricas
        ],
    }

    if not persist:
        return result

    try:
        init_db()
        session = get_db_session()
        repo = CatalogRepository(session)
    except Exception as exc:
        raise format_database_error(exc) from exc
    settings = get_settings()

    if repo.document_exists_by_hash(file_hash):
        doc = repo.get_document_by_hash(file_hash)
        result["status"] = "skipped"
        result["document_id"] = str(doc.id) if doc else None
        session.close()
        return result

    dest_dir = settings.pdf_storage / empresa / str(ano) / f"T{trimestre}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / pdf_path.name
    if not dest_path.exists():
        dest_path.write_bytes(pdf_path.read_bytes())

    doc = repo.create_document(
        empresa=empresa,
        ano=ano,
        trimestre=trimestre,
        source_url=source_url,
        file_hash=file_hash,
        storage_path=str(dest_path),
    )
    repo.update_document_status(doc, DocumentStatus.PROCESSING)
    repo.save_extraction(doc, extraction)
    repo.update_document_status(doc, DocumentStatus.COMPLETED)

    result["status"] = "completed"
    result["document_id"] = str(doc.id)
    session.close()
    return result


def main() -> None:
    """Ponto de entrada da CLI: parseia argumentos e imprime resultado JSON."""
    parser = argparse.ArgumentParser(description="Pipeline UDA — processamento local de PDF")
    parser.add_argument("pdf", type=Path, help="Caminho do PDF")
    parser.add_argument("--empresa", required=True, help="Nome da construtora")
    parser.add_argument("--ano", type=int, required=True, help="Ano de referência")
    parser.add_argument("--trimestre", type=int, required=True, choices=[1, 2, 3, 4])
    parser.add_argument("--source-url", default="local://manual")
    parser.add_argument("--no-persist", action="store_true", help="Apenas extrair, sem salvar no banco")
    args = parser.parse_args()

    try:
        result = process_local_pdf(
            pdf_path=args.pdf,
            empresa=args.empresa,
            ano=args.ano,
            trimestre=args.trimestre,
            source_url=args.source_url,
            persist=not args.no_persist,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (LLMConfigurationError, DatabaseConnectionError, FileNotFoundError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
