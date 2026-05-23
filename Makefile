.PHONY: test lint format run-router run-console seed smoke clean

# Development commands
test:
	pytest tests/

lint:
	ruff check .

format:
	ruff format .

# Runner commands
run-router:
	uvicorn router.server:app --host 0.0.0.0 --port 8080 --reload

run-console:
	cd console && pnpm dev

# Demo & Script commands
seed:
	python3 scripts/seed_demo_data.py

smoke:
	python3 scripts/smoke_test.py

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
