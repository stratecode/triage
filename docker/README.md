# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Docker Local Development

This directory contains Docker configurations for running TrIAge locally, replicating the AWS serverless stack.

## Files

- `Dockerfile.api` - API service (FastAPI + Lambda handlers)
- `Dockerfile.scheduler` - Scheduler service (EventBridge simulation)
- `local_api.py` - FastAPI application that wraps Lambda handlers
- `scheduler.py` - Cron-based scheduler for plan generation

## Quick Start

From the project root:

```bash
# Start the stack
make docker-up

# Or using the script directly
./scripts/docker-local.sh up
```

## Architecture

```
┌─────────────────────────────────────────┐
│  Docker Compose Network                 │
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │   API        │    │  Scheduler   │  │
│  │   :8000      │◄───│  (croniter)  │  │
│  │              │    │              │  │
│  │  FastAPI     │    │  HTTP Client │  │
│  │  + Lambda    │    │              │  │
│  │  handlers    │    │              │  │
│  └──────────────┘    └──────────────┘  │
│         │                               │
│  ┌──────────────┐                       │
│  │ Logs Viewer  │                       │
│  │   :8080      │                       │
│  │  (Dozzle)    │                       │
│  └──────────────┘                       │
└─────────────────────────────────────────┘
```

## Services

### API Service
- **Port**: 8000
- **Base Image**: python:3.11-slim
- **Purpose**: REST API with Lambda handlers
- **Health Check**: `/api/v1/health`

### Scheduler Service
- **Purpose**: Automated plan generation
- **Schedule**: Configurable via `SCHEDULE_CRON` env var
- **Default**: `0 7 * * 1-5` (7 AM weekdays)

### Logs Viewer
- **Port**: 8080
- **Image**: amir20/dozzle
- **Purpose**: Real-time log viewing in browser

## Environment Variables

Required in `.env`:

```bash
# JIRA
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token

# JWT
JWT_SECRET=your-secret-here

# Scheduler (optional)
SCHEDULE_CRON=0 7 * * 1-5
LOG_LEVEL=DEBUG
```

## Development Workflow

### 1. Code Changes

Code is mounted as volumes, so changes are reflected immediately:

```yaml
volumes:
  - ./triage:/app/triage:ro
  - ./lambda:/app/lambda:ro
```

After changes:
```bash
make docker-restart
```

### 2. View Logs

```bash
# Terminal
make docker-logs

# Browser
open http://localhost:8080
```

### 3. Debug

```bash
# Open shell in API container
docker-compose exec api /bin/bash

# Test Python code
python
>>> from triage.jira_client import JiraClient
>>> # Your debugging code
```

### 4. Test

```bash
# Automated tests
make docker-test

# Manual test
curl http://localhost:8000/api/v1/health
```

## Building Images

### Development Build
```bash
docker-compose build
```

### Production-like Build
```bash
docker-compose build --no-cache
```

### Multi-platform Build
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile.api \
  -t triage-api:latest .
```

## Troubleshooting

### Port Conflicts

Change ports in `docker-compose.yml`:
```yaml
api:
  ports:
    - "8001:8000"  # Use different port
```

### Memory Issues

Increase Docker memory:
```bash
# Docker Desktop: Settings > Resources > Memory
# Or in docker-compose.yml:
api:
  deploy:
    resources:
      limits:
        memory: 1G
```

### Volume Permissions

If you get permission errors:
```bash
# Fix ownership
sudo chown -R $(id -u):$(id -g) logs/
```

## Differences from AWS

| Feature | AWS | Docker Local |
|---------|-----|--------------|
| API Gateway | AWS API Gateway | FastAPI |
| Lambda | AWS Lambda | Python functions |
| Secrets Manager | AWS Secrets Manager | Environment variables |
| EventBridge | AWS EventBridge | croniter |
| CloudWatch Logs | AWS CloudWatch | Local files + Dozzle |
| Cold starts | Yes (1-3s) | No |
| Scaling | Automatic | Manual |

## Performance

Local stack is faster than AWS for development:
- No cold starts
- No network latency
- Faster iteration cycles

But remember:
- AWS has better scaling
- AWS has better security
- AWS has better monitoring

## Security

Local environment is for development only:
- Secrets in `.env` file (not encrypted)
- No network isolation
- No IAM controls
- JWT secret in plain text

Never use local setup for production data!

## Next Steps

1. Test locally: `make docker-test`
2. Verify functionality
3. Deploy to AWS: `make deploy-dev`
4. Compare behavior

## See Also

- [Docker Local Setup Guide](../docs/DOCKER_LOCAL_SETUP.md)
- [AWS Deployment Guide](../docs/AWS_DEPLOYMENT.md)
- [Main README](../README.md)
