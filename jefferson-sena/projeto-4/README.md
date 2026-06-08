# Pipeline UDA — Setor Habitacional

Pipeline para coleta, extração semântica (LLM) e API de métricas operacionais do setor habitacional.

> **Relatório acadêmico de entrega:** [relatorio-entrega.md](relatorio-entrega.md)  
> **Documentação técnica:** [docs/arquitetura.md](docs/arquitetura.md)

---

## Pré-requisitos

- Docker e `docker-compose`
- Chave do Google Gemini ([AI Studio](https://aistudio.google.com/apikey)) ou OpenAI

## Configuração

```bash
cd jefferson-sena/projeto-4
cp .env.example .env
# Edite .env — mínimo: GEMINI_API_KEY
```

Exemplo `.env`:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=sua-chave-aqui
GEMINI_MODEL=gemini-2.0-flash
```

## Subir o sistema

```bash
docker-compose up --build -d
```

| Serviço    | Porta | Função |
|-----------|-------|--------|
| api       | 8000  | REST API FastAPI |
| postgres  | 5433  | Catálogo e métricas |
| redis     | 6380  | Fila Celery |
| worker    | —     | Processamento LLM |
| scheduler | —     | Scan diário das Centrais de RI |

API: http://localhost:8000/docs

## Comandos úteis

```bash
# Extração de teste (Boletim 3T25)
make cli-no-persist

# Extração + persistência no banco
make cli

# Scan manual das fontes RI
make scan

# Testes
make test
```

### CLI manual

```bash
# Dentro do Docker (recomendado)
docker-compose exec api python -m src.cli \
  tests/fixtures/exemplo_Boletim_Conjuntura_2025_3T.pdf \
  --empresa "Conjuntura" --ano 2025 --trimestre 3

# Só JSON, sem banco
docker-compose exec api python -m src.cli arquivo.pdf \
  --empresa MRV --ano 2025 --trimestre 1 --no-persist
```

## Endpoints da API

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/conjuntura?empresa=MRV&ano=2025&trimestre=3"
curl http://localhost:8000/api/conjuntura/MRV
curl http://localhost:8000/api/documentos
curl http://localhost:8000/api/documentos/{uuid}/metricas
```

## Estrutura do projeto

```
projeto-4/
├── src/
│   ├── ingestion/     # scraper, downloader, scheduler
│   ├── extraction/    # parser, chunker, extractor LLM
│   ├── contracts/     # contrato semântico Pydantic
│   ├── catalog/       # PostgreSQL + linhagem
│   ├── workers/       # Celery
│   └── api/           # FastAPI
├── config/sources.yaml
├── tests/
└── docs/
```

## Problemas comuns

### Cota / API key (Gemini ou OpenAI)

Durante os testes houve problemas relacionado ao LLM, para mitigar os custos foi utilizado duas possibilidades sendo o gemini ou Open AI.

- Gemini: https://aistudio.google.com/apikey
- OpenAI: `LLM_PROVIDER=openai` + créditos em https://platform.openai.com/account/billing

### `could not translate host name "postgres"`

Foi utilizado a porta 5433 para saída do postgres (problema relacionado a conflito de projetos mas facilmente contornado).

CLI rodando fora do Docker com `DATABASE_URL=...@postgres:5432/...`.

- Use `docker-compose exec api python -m src.cli ...`
- Ou `--no-persist`
- Ou `DATABASE_URL=...@localhost:5433/uda_habitacional` no `.env`

## Documentação

- [Relatório de entrega](relatorio-entrega.md)
- [Arquitetura](docs/arquitetura.md)
- [Contrato semântico](docs/contrato-semantico.md)
- [ADR: Chunking híbrido](docs/adr/001-chunking-hibrido.md)
- [Setup Gemini](docs/gemini-setup.md)
- [Evidências de extração](docs/evidencias-extracao.md)
