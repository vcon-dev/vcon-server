FROM python:3.12.2

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

# Copy the rest of the application
COPY . /app

ENV PYTHONPATH "${PYTHONPATH}:/app/:/app/server/"

ENTRYPOINT ["/app/docker/wait_for_redis.sh"]

CMD [ "python", "./server/conserver.py" ]
