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

ARG TARGETPLATFORM

RUN if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        # 1. AMD64 (Servers): Install CPU-only versions specifically
        pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu; \
        # 2. Remove torch lines from requirements.txt so pip doesn't try to reinstall the heavy CUDA versions
        #    We use 'sed' to delete lines starting with torch
        sed -i '/^torch/d' requirements.txt; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

# APP ASSEMBLER
FROM python:3.11-slim

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

RUN mkdir -p /app/data \
             /app/prompts \
             /app/reports \
             /app/project_data \
             /app/hf_cache \
    && chown -R appuser:appuser /app

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

COPY --chown=appuser:appuser . .

ENV PATH="/opt/venv/bin:$PATH"
ENV RUNNING_IN_DOCKER=true
ENV HF_HOME="/app/hf_cache"

USER appuser

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "src.legatus_ai.legatus"]
