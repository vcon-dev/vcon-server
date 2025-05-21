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

# Install pip and PyTorch
RUN pip install --upgrade pip && \
    pip install torch torchvision torchaudio

# Install Poetry and project dependencies
COPY pyproject.toml poetry.lock /app/
RUN pip install poetry==1.8.0 && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-root

# Copy application code
COPY . /app

# Set environment variables
ENV PYTHONPATH=/app/:/app/server/

# Set entrypoint and command
ENTRYPOINT ["/app/docker/wait_for_redis.sh"]
CMD ["python", "./server/conserver.py"]