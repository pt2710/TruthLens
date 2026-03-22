PYTHON := py -m uv

.PHONY: bootstrap test lint typecheck build api extension

bootstrap:
	$(PYTHON) sync --group dev
	pnpm install

test:
	$(PYTHON) run pytest
	pnpm test

lint:
	$(PYTHON) run ruff check .
	pnpm lint

typecheck:
	$(PYTHON) run mypy .
	pnpm typecheck

build:
	pnpm build

api:
	$(PYTHON) run uvicorn truthlens_api.main:app --app-dir apps/api/src --reload

extension:
	pnpm --filter @truthlens/extension build
