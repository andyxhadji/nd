FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy source first (needed for install)
COPY pyproject.toml .
COPY nd/ nd/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy tests (optional, for testing in container)
COPY tests/ tests/

# Default command (override in compose)
CMD ["python", "-m", "nd.triage"]
