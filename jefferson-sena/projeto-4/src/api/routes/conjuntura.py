"""Rotas da API de conjuntura habitacional."""

import uuid
from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.catalog.database import get_db_session, init_db
from src.catalog.repository import CatalogRepository

router = APIRouter(prefix="/api", tags=["conjuntura"])


class MetricaResponse(BaseModel):
    """Resposta JSON de uma métrica operacional com linhagem."""

    chave: str
    valor_absoluto: Optional[float]
    unidade: str
    periodo_referencia: str
    fonte_pdf_url: str
    documento_id: str
    pagina_origem: Optional[int]
    trecho_evidencia: Optional[str]


class ConjunturaResponse(BaseModel):
    """Conjunto de métricas de uma empresa em um período."""

    empresa: str
    ano: int
    trimestre: int
    metricas: list[MetricaResponse]


class DocumentoResponse(BaseModel):
    """Metadados de um documento PDF ingerido."""

    id: str
    empresa: str
    ano: int
    trimestre: int
    tipo_documento: str
    source_url: str
    file_hash_sha256: str
    status: str
    ingested_at: str
    processed_at: Optional[str]


def get_repo() -> Generator[CatalogRepository, None, None]:
    """
    Dependência FastAPI que fornece CatalogRepository com sessão gerenciada.

    Yields:
        Repositório ativo; fecha sessão ao final da requisição.
    """
    init_db()
    session = get_db_session()
    try:
        yield CatalogRepository(session)
    finally:
        session.close()


@router.get("/conjuntura", response_model=list[ConjunturaResponse])
def get_conjuntura(
    empresa: Optional[str] = Query(None, description="Filtrar por empresa"),
    ano: Optional[int] = Query(None, description="Filtrar por ano"),
    trimestre: Optional[int] = Query(None, ge=1, le=4, description="Filtrar por trimestre"),
    repo: CatalogRepository = Depends(get_repo),
) -> list[ConjunturaResponse]:
    """
    Lista métricas de conjuntura com filtros opcionais.

    Args:
        empresa: Nome parcial da construtora.
        ano: Ano de referência.
        trimestre: Trimestre (1-4).

    Returns:
        Lista de ConjunturaResponse com métricas e linhagem ao PDF.
    """
    docs = repo.query_conjuntura(empresa=empresa, ano=ano, trimestre=trimestre)
    results: list[ConjunturaResponse] = []

    for doc in docs:
        metrics = repo.get_metrics_for_document(doc.id)
        results.append(
            ConjunturaResponse(
                empresa=doc.empresa,
                ano=doc.ano,
                trimestre=doc.trimestre,
                metricas=[
                    MetricaResponse(
                        chave=m.metric_key,
                        valor_absoluto=float(m.valor_absoluto) if m.valor_absoluto is not None else None,
                        unidade=m.unidade,
                        periodo_referencia=m.periodo_referencia,
                        fonte_pdf_url=m.source_url,
                        documento_id=str(m.document_id),
                        pagina_origem=m.pagina_origem,
                        trecho_evidencia=(
                            m.raw_llm_evidence.get("trecho_evidencia")
                            if m.raw_llm_evidence
                            else None
                        ),
                    )
                    for m in metrics
                ],
            )
        )
    return results


@router.get("/conjuntura/{empresa}", response_model=list[ConjunturaResponse])
def get_conjuntura_empresa(
    empresa: str, repo: CatalogRepository = Depends(get_repo)
) -> list[ConjunturaResponse]:
    """
    Retorna série temporal de métricas de uma empresa específica.

    Args:
        empresa: Nome da construtora (path parameter).

    Returns:
        Todas as conjunturas disponíveis para a empresa.
    """
    return get_conjuntura(empresa=empresa, ano=None, trimestre=None, repo=repo)


@router.get("/documentos", response_model=list[DocumentoResponse])
def list_documentos(
    empresa: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    repo: CatalogRepository = Depends(get_repo),
) -> list[DocumentoResponse]:
    """
    Lista documentos PDF ingeridos no catálogo.

    Args:
        empresa: Filtro opcional por nome da empresa.
        status: Filtro opcional por status (pending, completed, etc.).

    Returns:
        Metadados dos documentos ordenados por data de ingestão.
    """
    docs = repo.list_documents(empresa=empresa, status=status)
    return [
        DocumentoResponse(
            id=str(d.id),
            empresa=d.empresa,
            ano=d.ano,
            trimestre=d.trimestre,
            tipo_documento=d.tipo_documento,
            source_url=d.source_url,
            file_hash_sha256=d.file_hash_sha256,
            status=d.status,
            ingested_at=d.ingested_at.isoformat(),
            processed_at=d.processed_at.isoformat() if d.processed_at else None,
        )
        for d in docs
    ]


@router.get("/documentos/{document_id}/metricas", response_model=ConjunturaResponse)
def get_documento_metricas(
    document_id: str, repo: CatalogRepository = Depends(get_repo)
) -> ConjunturaResponse:
    """
    Retorna métricas extraídas de um documento com linhagem completa.

    Args:
        document_id: UUID do documento no catálogo.

    Returns:
        ConjunturaResponse com todas as métricas do documento.

    Raises:
        HTTPException 400: Se document_id não for UUID válido.
        HTTPException 404: Se documento não existir.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de documento inválido")

    doc = repo.get_document_by_id(doc_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    metrics = repo.get_metrics_for_document(doc.id)
    return ConjunturaResponse(
        empresa=doc.empresa,
        ano=doc.ano,
        trimestre=doc.trimestre,
        metricas=[
            MetricaResponse(
                chave=m.metric_key,
                valor_absoluto=float(m.valor_absoluto) if m.valor_absoluto is not None else None,
                unidade=m.unidade,
                periodo_referencia=m.periodo_referencia,
                fonte_pdf_url=m.source_url,
                documento_id=str(m.document_id),
                pagina_origem=m.pagina_origem,
                trecho_evidencia=(
                    m.raw_llm_evidence.get("trecho_evidencia") if m.raw_llm_evidence else None
                ),
            )
            for m in metrics
        ],
    )
