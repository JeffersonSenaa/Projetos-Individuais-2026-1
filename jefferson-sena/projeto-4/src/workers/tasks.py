"""Tarefas Celery para processamento assíncrono de documentos."""

import logging
import uuid
from pathlib import Path

from celery import Celery

from src.catalog.database import get_db_session, init_db
from src.catalog.models import DocumentStatus
from src.catalog.repository import CatalogRepository
from src.config import get_settings
from src.extraction.extractor import UDAExtractor

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "uda_habitacional",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: str) -> dict:
    """
    Processa um documento PDF da fila: extração LLM + persistência com linhagem.

    Atualiza status do documento: pending → processing → completed/failed.
    Em falha, reagenda até 3 tentativas com intervalo de 60 segundos.

    Args:
        document_id: UUID do documento no catálogo.

    Returns:
        Dicionário com status, document_id e metrics_count em caso de sucesso.
    """
    init_db()
    session = get_db_session()
    repo = CatalogRepository(session)

    try:
        doc = repo.get_document_by_id(uuid.UUID(document_id))
        if not doc:
            return {"status": "error", "message": "Documento não encontrado"}

        repo.update_document_status(doc, DocumentStatus.PROCESSING)
        pdf_path = Path(doc.storage_path)

        if not pdf_path.exists():
            repo.update_document_status(doc, DocumentStatus.FAILED, "Arquivo PDF não encontrado")
            return {"status": "error", "message": "PDF não encontrado"}

        extractor = UDAExtractor()
        extraction = extractor.extract_from_pdf(
            pdf_path=pdf_path,
            empresa=doc.empresa,
            ano=doc.ano,
            trimestre=doc.trimestre,
        )

        repo.save_extraction(doc, extraction)
        repo.update_document_status(doc, DocumentStatus.COMPLETED)

        return {
            "status": "completed",
            "document_id": document_id,
            "metrics_count": len(extraction.metricas),
        }
    except Exception as exc:
        logger.exception("Erro ao processar documento %s", document_id)
        try:
            doc = repo.get_document_by_id(uuid.UUID(document_id))
            if doc:
                repo.update_document_status(doc, DocumentStatus.FAILED, str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        session.close()
