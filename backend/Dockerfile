FROM python:3.12-slim AS base

# Security: nonroot user
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS runtime
COPY backend/ /app/backend/
COPY pyproject.toml /app/pyproject.toml

# Create data directory
RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]