FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[api]"

COPY footverse/ ./footverse/
COPY frontend/dist/ ./frontend/dist/

EXPOSE 8000

CMD ["uvicorn", "footverse.api:app", "--host", "0.0.0.0", "--port", "8000"]
