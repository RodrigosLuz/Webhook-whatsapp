# Dockerfile (prod, multi-stage) - usa Python 3.13 slim
FROM python:3.13-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependências do sistema necessárias --- mantenha leve
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copia requirements e gera wheels (opcional)
COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --wheel-dir /wheels -r requirements.txt

# Stage runtime
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=3000

# Usuário não-root
RUN groupadd -r appgrp && useradd -r -g appgrp appuser
WORKDIR /app

# Instala runtime deps a partir das wheels
COPY --from=builder /wheels /wheels
COPY requirements.txt /app/
RUN if [ -d /wheels ]; then pip install --no-index --find-links /wheels -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi

# Copia código
COPY . /app

# Ajusta permissões
RUN chown -R appuser:appgrp /app

USER appuser

EXPOSE 3000

# Recomendo usar gunicorn (ajuste workers conforme CPUs)
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:3000", "run:app"]
