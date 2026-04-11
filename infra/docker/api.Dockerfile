FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=apps/api/src:libs/shared-schemas/python:libs/feature-extractors/src:libs/data-pipeline/src:libs/dataset-governance/src:libs/policy-engine/python:libs/explanation-engine/python:libs/evaluation/src:libs/model-serving/python

COPY pyproject.toml README.md /app/
COPY apps/api /app/apps/api
COPY apps/labeling-ui/public /app/apps/labeling-ui/public
COPY libs /app/libs
COPY configs /app/configs
COPY datasets/manifests /app/datasets/manifests
COPY datasets/dataset_cards /app/datasets/dataset_cards
COPY artifacts /app/artifacts

RUN python -m pip install uv && python -m uv sync --no-dev
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "truthlens_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
