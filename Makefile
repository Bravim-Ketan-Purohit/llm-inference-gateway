.PHONY: dev test lint typecheck fmt ci bench bench-cloud infra-fmt infra-validate clean

dev:
	uvicorn gateway.api.app:app --reload --port 7501

services:
	docker compose -f docker-compose.dev.yml up -d

services-down:
	docker compose -f docker-compose.dev.yml down

test:
	pytest -q

lint:
	ruff check .

fmt:
	ruff format .
	ruff check --fix .

typecheck:
	mypy gateway/cache gateway/backends gateway/usage --strict

ci: lint typecheck test

bench:
	python -m bench.run --arm A --workload mixed --concurrency 16 --duration 60

bench-all:
	python -m bench.run --arm A --workload repeat-heavy --concurrency 16 --duration 60
	python -m bench.run --arm A --workload unique --concurrency 16 --duration 60
	python -m bench.run --arm A --workload mixed --concurrency 16 --duration 60
	python -m bench.run --arm B --workload repeat-heavy --concurrency 16 --duration 60
	python -m bench.run --arm B --workload unique --concurrency 16 --duration 60
	python -m bench.run --arm B --workload mixed --concurrency 16 --duration 60

sweep:
	python -m eval.sweep --tau-range 0.80:0.99:0.01

infra-fmt:
	terraform -chdir=infra fmt

infra-validate:
	terraform -chdir=infra init -backend=false
	terraform -chdir=infra validate

bench-cloud:
	@echo "=== Cloud benchmark: GPU EC2 ==="
	@echo "Estimated cost: ~$$1.00/hr (g5.xlarge)"
	@trap 'echo "Destroying..."; terraform -chdir=infra destroy -auto-approve' EXIT; \
	terraform -chdir=infra apply -auto-approve && \
	python -m bench.run --arm C --workload mixed --concurrency 1 --duration 60 --remote && \
	python -m bench.run --arm D --workload mixed --concurrency 1 --duration 60 --remote

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
