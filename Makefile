.PHONY: setup ingest run test lint typecheck eval docker fmt

setup:
	pip install -r requirements-dev.txt

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
