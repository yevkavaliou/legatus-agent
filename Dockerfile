# BUILDER
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir -r requirements.txt

# APP ASSEMBLER
FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /app/data \
             /app/prompts \
             /app/reports \
             /app/project_data \
             /app/hf_cache

COPY --from=builder /opt/venv /opt/venv

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

COPY . .

ENV PATH="/opt/venv/bin:$PATH"
ENV RUNNING_IN_DOCKER=true
ENV ENV HF_HOME="/app/hf_cache"

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["legatus"]
