# Build the React application.
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Run the FastAPI application and serve the built SPA from the same origin.
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt installs the repository itself with `-e .`; copy the complete
# packaging boundary before dependency installation so local, CI, and container
# imports all exercise the same installed package contract.
COPY pyproject.toml README.md ./
COPY backend/requirements.txt ./backend/requirements.txt
COPY backend/ ./backend/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip check

COPY alembic.ini ./alembic.ini
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
