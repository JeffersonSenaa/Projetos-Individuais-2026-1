"""Aplicação FastAPI do pipeline UDA habitacional."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes.conjuntura import router as conjuntura_router
from src.catalog.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia ciclo de vida da aplicação FastAPI.

    Inicializa tabelas do banco na subida do servidor.
    """
    init_db()
    yield


app = FastAPI(
    title="Pipeline UDA — Setor Habitacional",
    description="API de métricas operacionais extraídas de relatórios de RI via LLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(conjuntura_router)


@app.get("/health")
def health() -> dict:
    """Endpoint de health check para monitoramento e Docker. """
    return {"status": "ok", "service": "uda-habitacional"}
