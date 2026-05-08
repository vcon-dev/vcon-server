# Dev / test image — installs all dependency groups (conserver + api + dev).
# Used by docker-compose for local development and CI tests.
FROM python:3.12-slim

ARG VCON_SERVER_VERSION=dev
ARG VCON_SERVER_GIT_COMMIT=unknown
ARG VCON_SERVER_BUILD_TIME=unknown

ENV VCON_SERVER_VERSION=${VCON_SERVER_VERSION}
ENV VCON_SERVER_GIT_COMMIT=${VCON_SERVER_GIT_COMMIT}
ENV VCON_SERVER_BUILD_TIME=${VCON_SERVER_BUILD_TIME}

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libavdevice-dev \
        ffmpeg \
        libsox-fmt-all \
        sox \
        libpq5 \
        redis-tools \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

COPY pyproject.toml uv.lock /app/

# Install all groups (conserver + api + dev) so the image works for both
# running services and running pytest.
# Venv at /opt/venv so docker-compose volume mounts don't wipe it.
RUN uv venv --seed /opt/venv && \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --group conserver --group api --group dev
ENV PATH="/opt/venv/bin:$PATH"

# Auto-install OTel instrumentation packages for the installed libraries.
# || true: bootstrap raises on version conflicts between auto-detected packages;
# instrumentation still works for packages that installed cleanly.
RUN opentelemetry-bootstrap -a install || true

COPY . /app

ENV PYTHONPATH="/app:/app/common:/app/conserver:/app/api"

ENTRYPOINT ["/app/docker/wait_for_redis.sh"]
CMD ["opentelemetry-instrument", "python", "/app/conserver/main.py"]
