# Estratégia de Chunking Híbrido

## Status

Aceito

## Contexto

Relatórios de RI variam de comunicados curtos (5–15 páginas) a documentos extensos (80+ páginas). Duas estratégias são possíveis:

1. **Full-Scan:** enviar texto integral ao LLM
2. **Chunking Semântico:** segmentar e filtrar trechos relevantes

## Decisão

Adotar **chunking híbrido**:

| Condição | Estratégia |
|----------|-----------|
| Documento ≤ 15 páginas | Full-scan por página |
| Documento > 15 páginas | Chunking com filtro por keywords operacionais |
| Página com < 50 chars de texto | Vision (GPT-4o) para slides rasterizados |

Keywords de filtro: `vendas`, `vso`, `estoque`, `unidades`, `receita`, `vgv`, `margem`, `obras`, `operacional`, `previa`, `resultado`.

## Consequências

### Positivas

- Redução de 60–80% no consumo de tokens em documentos longos
- Full-scan garante cobertura completa em prévias operacionais curtas
- Vision fallback trata layouts em slides (ex: MRV) sem coordenadas fixas

### Negativas

- Keywords podem filtrar páginas relevantes com vocabulário atípico
- Mitigação: fallback que inclui página 1 se nenhum chunk for selecionado

## Alternativas descartadas (Inviáveis)

- **Full-scan sempre:** inviável economicamente em relatórios longos
- **LOTUS/Palimpzest:** menos controle sobre linhagem e contrato semântico
- **Coordenadas/regex de layout:** proibido pelo escopo para extração de métricas
