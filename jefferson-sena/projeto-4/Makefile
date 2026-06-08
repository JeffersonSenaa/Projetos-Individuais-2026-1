.PHONY: up down build logs cli cli-no-persist scan test

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f api

cli:
	docker-compose exec api python -m src.cli tests/fixtures/exemplo_Boletim_Conjuntura_2025_3T.pdf \
		--empresa "Conjuntura" --ano 2025 --trimestre 3

cli-no-persist:
	docker-compose exec api python -m src.cli tests/fixtures/exemplo_Boletim_Conjuntura_2025_3T.pdf \
		--empresa "Conjuntura" --ano 2025 --trimestre 3 --no-persist

scan:
	docker-compose exec scheduler python -m src.ingestion.scheduler --once

test:
	PYTHONPATH=. .venv/bin/python -m pytest tests/ -v
