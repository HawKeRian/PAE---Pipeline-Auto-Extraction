FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PAE_ENVIRONMENT=production \
    PAE_DATA_DIR=/app/data \
    PAE_GENERATED_DIR=/app/generated \
    PAE_DATABASE_PATH=/app/data/pae.sqlite3 \
    PAE_ENABLE_MOCK_UI=false

WORKDIR /app
RUN apt-get update && \
    apt-get install --yes --no-install-recommends libodbc2 && \
    rm -rf /var/lib/apt/lists/*
RUN groupadd --system pae && useradd --system --gid pae --home-dir /app pae
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir -r requirements.txt && \
    python -m pip install --no-cache-dir --no-deps . && \
    mkdir -p /app/data /app/generated && chown -R pae:pae /app

USER pae
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3))['status']=='ready'"

CMD ["uvicorn", "pae.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
