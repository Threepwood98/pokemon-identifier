FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

# ── Dependencias del sistema ─────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Instalar dependencias Python ─────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-descargar el modelo ViT durante el BUILD ─────────────────────
RUN python -c "\
from transformers import pipeline; \
print('Descargando modelo ViT...'); \
pipe = pipeline('image-classification', model='imzynoxprince/pokemons-image-classifier-gen1-gen9'); \
print('Modelo descargado correctamente.')"

# ── Copiar código fuente ──────────────────────────────────────────────
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# ── Usar shell form para que $PORT se expanda correctamente ───────────
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1