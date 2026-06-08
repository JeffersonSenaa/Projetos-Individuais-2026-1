"""Repositório do catálogo com deduplicação e linhagem."""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.catalog.models import Document, DocumentStatus, MetricValue
from src.contracts.conjuntura import ExtracaoConjuntura


def compute_file_hash(file_path: Path) -> str:
    """
    Calcula SHA-256 do conteúdo binário de um arquivo PDF.

    Usado para idempotência: evita reprocessar o mesmo PDF no LLM.

    Args:
        file_path: Caminho do arquivo no disco.

    Returns:
        Hash hexadecimal de 64 caracteres.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


def compute_bytes_hash(content: bytes) -> str:
    """
    Calcula SHA-256 de bytes em memória (ex.: PDF recém-baixado).

    Args:
        content: Conteúdo binário do PDF.

    Returns:
        Hash hexadecimal SHA-256.
    """
    return hashlib.sha256(content).hexdigest()


class CatalogRepository:
    """Acesso ao catálogo de documentos e métricas com suporte a linhagem."""

    def __init__(self, session: Session):
        """
        Inicializa o repositório com uma sessão SQLAlchemy ativa.

        Args:
            session: Sessão de banco vinculada à transação corrente.
        """
        self.session = session

    def document_exists_by_hash(self, file_hash: str) -> bool:
        """
        Verifica se um documento com o hash informado já foi ingerido.

        Args:
            file_hash: SHA-256 do conteúdo do PDF.

        Returns:
            True se o documento já existir no catálogo.
        """
        return (
            self.session.query(Document).filter(Document.file_hash_sha256 == file_hash).first()
            is not None
        )

    def get_document_by_hash(self, file_hash: str) -> Document | None:
        """
        Busca documento pelo hash SHA-256.

        Args:
            file_hash: Hash do arquivo PDF.

        Returns:
            Documento encontrado ou None.
        """
        return self.session.query(Document).filter(Document.file_hash_sha256 == file_hash).first()

    def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        """
        Busca documento pelo UUID.

        Args:
            document_id: Identificador único do documento.

        Returns:
            Documento encontrado ou None.
        """
        return self.session.query(Document).filter(Document.id == document_id).first()

    def create_document(
        self,
        empresa: str,
        ano: int,
        trimestre: int,
        source_url: str,
        file_hash: str,
        storage_path: str,
        tipo_documento: str = "previa_operacional",
    ) -> Document:
        """
        Registra um novo documento no catálogo com status pending.

        Args:
            empresa: Nome da construtora.
            ano: Ano de referência.
            trimestre: Trimestre (1-4).
            source_url: URL original do PDF na Central de Resultados.
            file_hash: SHA-256 do conteúdo binário.
            storage_path: Caminho local onde o PDF foi salvo.
            tipo_documento: Tipo do relatório (padrão: previa_operacional).

        Returns:
            Documento persistido com id gerado.
        """
        doc = Document(
            empresa=empresa,
            ano=ano,
            trimestre=trimestre,
            tipo_documento=tipo_documento,
            source_url=source_url,
            file_hash_sha256=file_hash,
            storage_path=storage_path,
            status=DocumentStatus.PENDING.value,
        )
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return doc

    def update_document_status(
        self,
        doc: Document,
        status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document:
        """
        Atualiza o status de processamento de um documento.

        Define processed_at automaticamente quando status for COMPLETED.

        Args:
            doc: Documento a atualizar.
            status: Novo status (pending, processing, completed, failed).
            error_message: Mensagem de erro opcional (usado em failed).

        Returns:
            Documento atualizado.
        """
        doc.status = status.value
        doc.error_message = error_message
        if status == DocumentStatus.COMPLETED:
            doc.processed_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(doc)
        return doc

    def save_extraction(self, doc: Document, extraction: ExtracaoConjuntura) -> list[MetricValue]:
        """
        Persiste métricas extraídas com linhagem ao documento e PDF de origem.

        Faz upsert por (document_id, metric_key): atualiza se já existir.

        Args:
            doc: Documento processado.
            extraction: Resultado validado do contrato semântico.

        Returns:
            Lista de MetricValue persistidos.
        """
        saved: list[MetricValue] = []
        for metric in extraction.metricas:
            valor = float(metric.valor_absoluto) if metric.valor_absoluto is not None else None
            existing = (
                self.session.query(MetricValue)
                .filter(
                    MetricValue.document_id == doc.id,
                    MetricValue.metric_key == metric.chave,
                )
                .first()
            )
            evidence = {
                "trecho_evidencia": metric.trecho_evidencia,
                "empresa": extraction.empresa,
                "ano": extraction.ano,
                "trimestre": extraction.trimestre,
            }
            if existing:
                existing.valor_absoluto = valor
                existing.unidade = metric.unidade
                existing.periodo_referencia = metric.periodo
                existing.pagina_origem = metric.pagina
                existing.chunk_id = f"p{metric.pagina}" if metric.pagina else None
                existing.raw_llm_evidence = evidence
                saved.append(existing)
            else:
                mv = MetricValue(
                    document_id=doc.id,
                    metric_key=metric.chave,
                    valor_absoluto=valor,
                    unidade=metric.unidade,
                    periodo_referencia=metric.periodo,
                    pagina_origem=metric.pagina,
                    chunk_id=f"p{metric.pagina}" if metric.pagina else None,
                    source_url=doc.source_url,
                    raw_llm_evidence=evidence,
                )
                self.session.add(mv)
                saved.append(mv)
        self.session.commit()
        return saved

    def query_conjuntura(
        self,
        empresa: str | None = None,
        ano: int | None = None,
        trimestre: int | None = None,
    ) -> list[Document]:
        """
        Consulta documentos processados com filtros opcionais.

        Retorna apenas documentos com status completed.

        Args:
            empresa: Filtro parcial por nome (case-insensitive).
            ano: Filtro por ano.
            trimestre: Filtro por trimestre.

        Returns:
            Lista de documentos ordenados por empresa, ano e trimestre decrescentes.
        """
        q = self.session.query(Document).filter(
            Document.status == DocumentStatus.COMPLETED.value
        )
        if empresa:
            q = q.filter(Document.empresa.ilike(f"%{empresa}%"))
        if ano:
            q = q.filter(Document.ano == ano)
        if trimestre:
            q = q.filter(Document.trimestre == trimestre)
        return q.order_by(Document.empresa, Document.ano.desc(), Document.trimestre.desc()).all()

    def list_documents(
        self,
        empresa: str | None = None,
        status: str | None = None,
    ) -> list[Document]:
        """
        Lista documentos do catálogo com filtros opcionais.

        Args:
            empresa: Filtro parcial por nome da empresa.
            status: Filtro por status (pending, processing, completed, failed).

        Returns:
            Documentos ordenados por data de ingestão decrescente.
        """
        q = self.session.query(Document)
        if empresa:
            q = q.filter(Document.empresa.ilike(f"%{empresa}%"))
        if status:
            q = q.filter(Document.status == status)
        return q.order_by(Document.ingested_at.desc()).all()

    def get_metrics_for_document(self, document_id: uuid.UUID) -> list[MetricValue]:
        """
        Retorna todas as métricas extraídas de um documento.

        Args:
            document_id: UUID do documento.

        Returns:
            Lista de MetricValue com linhagem ao PDF original.
        """
        return (
            self.session.query(MetricValue)
            .filter(MetricValue.document_id == document_id)
            .all()
        )
