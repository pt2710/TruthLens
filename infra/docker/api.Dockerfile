FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY libs /app/libs

RUN python -m pip install uv && python -m uv sync --group dev

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "truthlens_api.main:app", "--app-dir", "apps/api/src", "--host", "0.0.0.0", "--port", "8000"]
