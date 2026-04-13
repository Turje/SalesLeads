FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY core/ core/
COPY api/ api/
COPY config/ config/
COPY agents/ agents/
COPY pipeline/ pipeline/
COPY seed_data.py .

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist frontend/dist

# Create data directory for persistent SQLite
RUN mkdir -p /data

# Environment
ENV DATABASE_PATH=/data/salesleads.db
ENV CORS_ORIGINS=*
ENV OLLAMA_BASE_URL=http://localhost:11434
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Seed on first run, then start server
CMD python3 -c "import seed_data; seed_data.seed()" && \
    uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
