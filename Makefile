.PHONY: setup setup-native ingest run test lint typecheck eval docker docker-gpu fmt

setup:
	pip install -r requirements-dev.txt

# Native (no-Docker) bootstrap: venv + runtime deps. Append ARGS=--gpu for CUDA torch.
setup-native:
	./scripts/setup.sh $(ARGS)

ingest:
	python -m app.ingest

run:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check app tests
	ruff format --check app tests

fmt:
	ruff format app tests
	ruff check --fix app tests

typecheck:
	mypy app

eval:
	python eval/run_eval.py

docker:
	docker compose up --build

docker-gpu:
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
