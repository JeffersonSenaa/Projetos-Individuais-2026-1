# Contrato Semântico — Métricas Operacionais

O contrato semântico (`src/contracts/conjuntura.py`) define o schema Pydantic que o LLM deve respeitar. É a principal barreira contra alucinações.

## Métricas suportadas

| Chave | Descrição | Unidade típica |
|-------|-----------|----------------|
| `unidades_vendidas` | Unidades vendidas no período | `unidades` |
| `vgv` | Valor Geral de Vendas | `milhoes_R$` ou `R$` |
| `vso` | Velocidade de Vendas sobre Oferta | `percentual_absoluto` |
| `estoque_unidades` | Unidades em estoque | `unidades` |
| `obras_andamento` | Obras em andamento | `unidades` |
| `receita_liquida` | Receita líquida | `milhoes_R$` |
| `margem_bruta` | Margem bruta | `percentual_absoluto` |

## Regras de negócio

### Valores absolutos (obrigatório)

- Extrair **valores brutos**: "12.340 unidades", "R$ 2,5 bi"
- **Ignorar** variações percentuais de marketing: "+15% vs 3T24"

### Valores ausentes

- Se a métrica não aparecer no trecho → `valor_absoluto: null`
- Nunca inferir, calcular ou inventar valores

### Convenção VSO

- Percentual absoluto: 24,5% → `24.5` (não `0.245`)

### Validação Pydantic pós-LLM

- `trimestre` ∈ {1, 2, 3, 4}
- `valor_absoluto >= 0` quando presente
- `trecho_evidencia`: citação literal do PDF (até 500 chars) para auditoria

## Prompt do sistema

Definido em `src/extraction/prompts.py`. Instrui o LLM a:

1. Responder estritamente conforme o schema JSON
2. Priorizar evidência textual
3. Tratar ambiguidade monetária como null

## Exemplo de saída válida

```json
{
  "empresa": "MRV",
  "ano": 2025,
  "trimestre": 3,
  "metricas": [
    {
      "chave": "unidades_vendidas",
      "valor_absoluto": 12340,
      "unidade": "unidades",
      "periodo": "3T25",
      "pagina": 4,
      "trecho_evidencia": "12.340 unidades vendidas no 3T25"
    },
    {
      "chave": "vgv",
      "valor_absoluto": null,
      "unidade": "milhoes_R$",
      "periodo": "3T25",
      "pagina": null,
      "trecho_evidencia": null
    }
  ]
}
```

## Linhagem

Cada métrica persistida em `metric_values` mantém:

- `source_url`: link original do PDF na Central de Resultados
- `document_id`: FK para `documents`
- `pagina_origem` e `chunk_id`: localização no documento
- `raw_llm_evidence`: JSON com trecho de evidência e metadados
