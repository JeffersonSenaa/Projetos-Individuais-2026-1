"""Modelos SQLAlchemy do catálogo de dados."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Classe base declarativa do SQLAlchemy para todos os modelos."""


class DocumentStatus(str, enum.Enum):
    """Estados do ciclo de vida de um documento no pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """Registro de um PDF ingerido com metadados e status de processamento."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trimestre: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tipo_documento: Mapped[str] = mapped_column(String(100), default="previa_operacional")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING.value, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    metric_values: Mapped[list["MetricValue"]] = relationship(back_populates="document")


class MetricValue(Base):
    """Métrica operacional extraída com linhagem ao documento e PDF de origem."""

    __tablename__ = "metric_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    metric_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    valor_absoluto: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    unidade: Mapped[str] = mapped_column(String(30), nullable=False)
    periodo_referencia: Mapped[str] = mapped_column(String(20), nullable=False)
    pagina_origem: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_llm_evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="metric_values")

    __table_args__ = (
        UniqueConstraint("document_id", "metric_key", name="uq_document_metric"),
    )
