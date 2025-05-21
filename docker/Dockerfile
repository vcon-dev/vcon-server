FROM python:3.12.2

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libavdevice-dev \
    ffmpeg \
    libsox-fmt-all \
    sox \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Poetry with specific version
RUN pip install poetry==1.8.0 && \
    poetry config virtualenvs.create false

# Copy dependency files
COPY pyproject.toml poetry.lock* /app/

# Fix PyTorch installation to use compatible versions for Python 3.12
RUN pip install --upgrade pip && \
    pip install torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0 && \
    # Install MSAL for dataverse tests
    pip install msal

# Handle the lock file
RUN poetry lock --no-update && \
    # Install all dependencies including test dependencies
    poetry install --with test --no-interaction --no-root

# Copy application code
COPY . /app

# Set environment variables
ENV PYTHONPATH=/app/:/app/server/

# Set entrypoint and command
ENTRYPOINT ["/app/docker/wait_for_redis.sh"]
CMD ["python", "./server/conserver.py"]