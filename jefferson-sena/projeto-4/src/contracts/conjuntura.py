"""Contrato semântico para extração de métricas do setor habitacional."""

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


MetricKey = Literal[
    "unidades_vendidas",
    "vgv",
    "vso",
    "estoque_unidades",
    "obras_andamento",
    "receita_liquida",
    "margem_bruta",
]

MetricUnit = Literal["unidades", "R$", "milhoes_R$", "percentual_absoluto"]


class MetricaOperacional(BaseModel):
    """Métrica operacional extraída de um relatório de RI."""

    chave: MetricKey
    valor_absoluto: Optional[Decimal] = Field(
        default=None,
        description="Valor bruto absoluto; null se ausente no documento",
    )
    unidade: MetricUnit
    periodo: str = Field(description="Período de referência, ex: 3T25")
    pagina: Optional[int] = None
    trecho_evidencia: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Trecho literal do PDF que comprova o valor",
    )

    @field_validator("valor_absoluto")
    @classmethod
    def validate_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Garante que valores absolutos presentes não sejam negativos."""
        if v is not None and v < 0:
            raise ValueError("valor_absoluto deve ser >= 0")
        return v


class ExtracaoConjunturaParcial(BaseModel):
    """Resposta parcial do LLM para um único chunk de documento."""

    metricas: list[MetricaOperacional] = Field(default_factory=list)


class ExtracaoConjuntura(BaseModel):
    """Contrato semântico completo após merge de todos os chunks do PDF."""

    empresa: str
    ano: int
    trimestre: int = Field(ge=1, le=4)
    metricas: list[MetricaOperacional] = Field(default_factory=list)

    @field_validator("trimestre")
    @classmethod
    def validate_trimestre(cls, v: int) -> int:
        """Valida que o trimestre está no intervalo 1 a 4."""
        if v not in (1, 2, 3, 4):
            raise ValueError("trimestre deve estar entre 1 e 4")
        return v
