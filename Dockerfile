# CodeIQ pipeline image: clone -> ts-morph extract -> LLM descriptions -> ChromaDB index
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Node.js is needed for the ts-morph extractor (src/ts_extract/extract.mjs)
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so source edits don't invalidate these layers
COPY requirements.txt package.json ./
RUN pip install -r requirements.txt \
    && npm install --omit=dev

COPY src/ src/
COPY app/ app/
COPY Makefile ./
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Shiny chat UI (docker compose up app)
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
