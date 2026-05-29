## Build stage: kata CLI
# nd shells out to `kata` for task management. The CLI is a thin client. The
# kata daemon runs as its own compose service (`kata-daemon`); agent containers
# share its network namespace and reach it via KATA_SERVER=http://127.0.0.1:7878.
FROM golang:1.26.3-bookworm AS kata-build
ENV CGO_ENABLED=0
RUN go install go.kenn.io/kata/cmd/kata@latest

## Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Claude CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install roborev
RUN curl -fsSL https://roborev.io/install.sh | bash

# Install Claude Code CLI via npm (official package)
RUN npm install -g @anthropic-ai/claude-code \
    && rm -f /usr/bin/claude \
    && ln -sf /usr/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/bin/claude

# kata CLI from the builder stage
COPY --from=kata-build /go/bin/kata /usr/local/bin/kata

# Copy source first (needed for install)
COPY pyproject.toml .
COPY nd/ nd/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy tests (optional, for testing in container)
COPY tests/ tests/

# Default command (override in compose)
CMD ["python", "-m", "nd.triage"]
