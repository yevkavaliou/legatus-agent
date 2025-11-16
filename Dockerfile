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
             /app/project_data

COPY --from=builder /opt/venv /opt/venv

COPY . .

ENV PATH="/opt/venv/bin:$PATH"

ENV RUNNING_IN_DOCKER=true

CMD ["python", "-m", "src.legatus_ai.legatus"]
