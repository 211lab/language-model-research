FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        curl \
        docker-compose \
        docker.io \
        findutils \
        git \
        jq \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# The established switcher invokes `docker compose`. Debian's package provides
# legacy `docker-compose`, so the small shim preserves the switcher's command
# contract while talking to the mounted Docker socket.
COPY services/backend/docker /usr/local/bin/docker
RUN chmod +x /usr/local/bin/docker

COPY backend /app
ENV PYTHONPATH=/workspace/operator/backend:/app
WORKDIR /app
