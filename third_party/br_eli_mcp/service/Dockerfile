# Imagem do serviço br-eli-mcp (implantação separada no Railway).
# Contexto de build: third_party/br_eli_mcp. Dependências fixadas por hash.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app/service \
    BR_ELI_CACHE_DIR=/tmp/br-eli/cache \
    BR_ELI_AUDIT_DIR=/tmp/br-eli/audit \
    OTEL_SDK_DISABLED=true

WORKDIR /app

COPY lock/requirements.txt /app/lock/requirements.txt
RUN pip install --require-hashes -r /app/lock/requirements.txt

COPY src /app/src
COPY service /app/service

RUN useradd -m -u 1000 brel \
    && mkdir -p /tmp/br-eli/cache /tmp/br-eli/audit \
    && chown -R brel:brel /tmp/br-eli /app
USER brel

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app:app --app-dir /app/service --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --no-server-header"]
