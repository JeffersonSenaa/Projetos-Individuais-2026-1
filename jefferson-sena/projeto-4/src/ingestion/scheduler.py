"""Orquestrador de scan periódico das fontes RI."""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.catalog.database import get_db_session, init_db
from src.catalog.repository import CatalogRepository
from src.config import get_settings
from src.ingestion.downloader import PDFDownloader
from src.ingestion.scraper import RIScraper
from src.workers.tasks import process_document_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_scan() -> None:
    """
    Executa um ciclo completo de ingestão das Centrais de Resultados.

    Fluxo:
    1. Varre sources.yaml via RIScraper.
    2. Baixa PDFs novos via PDFDownloader (dedup por hash).
    3. Enfileira processamento LLM via Celery para documentos criados.
    """
    logger.info("Iniciando scan das Centrais de Resultados...")
    init_db()
    session = get_db_session()
    repo = CatalogRepository(session)
    scraper = RIScraper()
    downloader = PDFDownloader(repo)

    pdfs = scraper.scan_all_sources()
    created = 0
    skipped = 0

    for pdf in pdfs:
        status, doc_id = downloader.ingest_pdf_url(url=pdf.url, empresa=pdf.empresa)
        if status == "created" and doc_id:
            process_document_task.delay(doc_id)
            created += 1
        elif status == "skipped":
            skipped += 1

    logger.info("Scan concluído: %d novos, %d ignorados (duplicados)", created, skipped)
    session.close()


def main() -> None:
    """
    Ponto de entrada do scheduler.

    - Com argumento '--once': executa um único scan e encerra.
    - Sem argumentos: executa scan imediato e agenda cron diário (SCAN_CRON_HOUR/MINUTE).
    """
    settings = get_settings()

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_scan()
        return

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_scan,
        CronTrigger(hour=settings.scan_cron_hour, minute=settings.scan_cron_minute),
        id="ri_scan",
        name="Scan Centrais de Resultados",
    )
    logger.info(
        "Scheduler iniciado (cron: %02d:%02d BRT). Use --once para execução imediata.",
        settings.scan_cron_hour,
        settings.scan_cron_minute,
    )
    run_scan()
    scheduler.start()


if __name__ == "__main__":
    main()
