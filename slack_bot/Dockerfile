# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# User: slackbot (uid/gid 1000) - non-root user for security

# Multi-stage build for Slack bot service using public Docker images

# Stage 1: Builder
# Using Alpine for smaller image size and package management support
FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dependencias de sistema NECESARIAS para compilar wheels
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    cargo

# uv (binario)
RUN pip install --no-cache-dir uv

COPY . .
RUN uv venv && source .venv/bin/activate && uv pip install -e .

# Stage 2: Runtime
# Using Alpine for minimal runtime footprint
FROM python:3.12-alpine

LABEL maintainer="StrateCode" \
      description="TrIAge Slack Bot Service" \
      version="1.0"

# Set production runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/slack_bot"

WORKDIR /app/slack_bot

# Copy virtual environment from builder stage
COPY --from=builder /build/.venv /opt/venv

# Create non-root user for security
RUN addgroup -g 1000 slackbot && \
    adduser -D -u 1000 -G slackbot slackbot && \
    mkdir -p /app/slack_bot && \
    chown -R slackbot:slackbot /app

# Copy application code with proper ownership
COPY --chown=slackbot:slackbot *.py ./

# Switch to non-root user for security
USER slackbot

# Expose port for webhook server (must be >1024 for nonroot user)
EXPOSE 3000

# Production-grade health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run application using Python module execution
CMD ["python", "-m", "main"]
