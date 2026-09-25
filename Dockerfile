# ─────────────────────────────────────────────────────────────────────────
# ttp-similarity-engine -- Dockerfile
# Temel imaj: python:3.11-slim (pyproject.toml: requires-python >=3.11,<3.12)
#
# Kullanim:
#   docker compose up --build            # tavsiye edilen
#
#   docker build -t ttp-similarity-engine .
#   docker run -p 8501:8501 \
#     -v "${PWD}/data:/app/data" \
#     -v "${PWD}/outputs:/app/outputs" \
#     ttp-similarity-engine
# ─────────────────────────────────────────────────────────────────────────

# ── 1. BUILDER: tum bagimliliklar wheel olarak derlenir ──────────────────
FROM python:3.11-slim AS builder

# numpy/scipy C uzantilari icin derleyici gerekir
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc g++ \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .

# Wheelleri /wheels dizinine cek; final asamada pip --no-index ile kurulur
RUN pip install --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── 2. FINAL: minimal calisma imaji ──────────────────────────────────────
FROM python:3.11-slim AS final

# libgomp1: sklearn/numpy OpenMP destegi icin gerekli
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Onceden derlenmiş wheelleri al (internet gerekmez)
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --no-index --find-links /wheels -r requirements.txt \
 && rm -rf /wheels

# Kaynak kodu kopyala
COPY ttp_similarity/ ./ttp_similarity/
COPY check_setup.py pyproject.toml ./

# Veri ve cikti dizinleri (volume mount oncesi bos yapi olusturulur)
RUN mkdir -p \
        data/raw \
        data/interim \
        data/processed \
        data/mock \
        outputs/figures \
        outputs/reports

# ── Ortam degiskenleri ───────────────────────────────────────────────────
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8501

# Saglik kontrolu: Streamlit /healthz endpoint'i
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/healthz')" || exit 1

# Varsayilan komut: Streamlit arayuzunu baslat
CMD ["streamlit", "run", "ttp_similarity/app/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]