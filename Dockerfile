FROM node:22-bookworm-slim

ARG CODEX_VERSION=0.146.0

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin \
    HOME=/data/home \
    PRISM_DATA_DIR=/data/prism \
    PRISM_INBOX_DIR=/data/prism/inbox \
    PRISM_VERSION=0.2.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash bubblewrap ca-certificates curl git openssh-client procps python3 python3-venv tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

RUN npm install --global "@openai/codex@${CODEX_VERSION}" \
    && codex --version

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN chmod 0755 /app/docker-entrypoint.sh

EXPOSE 8001
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent "http://127.0.0.1:${PORT:-8001}/api/health" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
