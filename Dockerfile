# ─────────────────────────────────────────────────────────────────────────
# ttp-similarity-engine -- YILDIZ TTP Benzerlik İstasyonu
#
#   docker compose up --build          # http://localhost:8000
#
# Asamalar:
#   web     : Svelte arayuzu derlenir ve birim testleri kosar (Node 24)
#   builder : Python bagimliliklari wheel olarak toplanir (Python 3.11)
#   final   : yalnizca calisma zamani; arayuz web/dist olarak icine kopyalanir
# ─────────────────────────────────────────────────────────────────────────

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm test && npm run build


FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim AS final

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements.txt \
 && rm -rf /wheels

COPY ttp_similarity/ ./ttp_similarity/
COPY check_setup.py pyproject.toml .python-version ./
COPY tests/ ./tests/
COPY --from=web /web/dist ./web/dist

RUN mkdir -p data/raw data/interim data/processed data/mock outputs/figures outputs/reports

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Veri seti yoksa ilk acilista indirilip derlenir (~54 MB, bir kez).
CMD ["python", "-m", "ttp_similarity.api", "--host", "0.0.0.0", "--port", "8000", "--auto-build"]
