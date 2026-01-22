FROM python:3.12.2

# Build arguments for version information (injected by CI/CD)
ARG VCON_SERVER_VERSION=dev
ARG VCON_SERVER_GIT_COMMIT=unknown
ARG VCON_SERVER_BUILD_TIME=unknown

# Set version info as environment variables (available at runtime)
ENV VCON_SERVER_VERSION=${VCON_SERVER_VERSION}
ENV VCON_SERVER_GIT_COMMIT=${VCON_SERVER_GIT_COMMIT}
ENV VCON_SERVER_BUILD_TIME=${VCON_SERVER_BUILD_TIME}

RUN apt-get update && \
    apt-get install -y libavdevice-dev ffmpeg

# Install SoX dependency
# https://pysox.readthedocs.io/en/latest/#installation
RUN apt-get install -y libsox-fmt-all sox

# This is required in order to wait for Redis
RUN apt-get install -y redis-tools
RUN pip install --upgrade pip

# Install watchdog
RUN pip install watchdog

WORKDIR /app

# Install Poetry
RUN pip install poetry==2.1.3
RUN poetry config virtualenvs.create false

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock* /app/

# Regenerate lock file if needed and install dependencies
RUN poetry lock --no-update || poetry lock
RUN poetry install --only=main --no-interaction

# Install OpenTelemetry instrumentation libraries for detected packages
RUN opentelemetry-bootstrap -a install

# Copy the rest of the application
COPY . /app

ENV PYTHONPATH "${PYTHONPATH}:/app/:/app/server/"

ENTRYPOINT ["/app/docker/wait_for_redis.sh"]

CMD [ "opentelemetry-instrument", "python", "./server/main.py" ]
