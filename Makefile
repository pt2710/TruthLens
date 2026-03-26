PYTHON := py -m uv

.PHONY: bootstrap test lint typecheck build api extension data train eval smoke

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

data:
	$(PYTHON) run python scripts/run_truthlens_module.py truthlens_trainer.pipeline

train:
	$(PYTHON) run python scripts/run_truthlens_module.py truthlens_trainer.train

eval:
	$(PYTHON) run python scripts/run_truthlens_module.py truthlens_trainer.simulate

smoke:
	$(PYTHON) run python scripts/run_truthlens_module.py truthlens_trainer.smoke
