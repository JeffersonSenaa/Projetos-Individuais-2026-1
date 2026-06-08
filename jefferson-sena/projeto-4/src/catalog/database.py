"""Conexão e inicialização do banco de dados."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.catalog.models import Base
from src.config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    """
    Retorna engine SQLAlchemy singleton conectada ao PostgreSQL.

    Returns:
        Engine configurada com pool_pre_ping para reconexão automática.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """
    Retorna factory de sessões SQLAlchemy (singleton).

    Returns:
        sessionmaker vinculado à engine do banco.
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_db_session() -> Session:
    """Abre e retorna uma nova sessão de banco de dados."""
    return get_session_factory()()


def init_db() -> None:
    """Cria todas as tabelas definidas nos modelos se ainda não existirem."""
    Base.metadata.create_all(bind=get_engine())
