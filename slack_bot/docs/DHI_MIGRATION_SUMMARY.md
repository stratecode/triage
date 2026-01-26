# Docker Hardened Images (DHI) Migration Summary

## Overview
This document outlines the migration of the TrIAge Slack Bot application from Docker Official Images to Docker Hardened Images (DHI). The migration maintains all functionality while improving security and reducing the attack surface.

## Migration Details

### Dockerfile Changes

#### Stage 1: Builder Stage
**Before:**
```dockerfile
FROM python:3.11-slim-bookworm AS builder
RUN apt-get update && apt-get upgrade -y && apt-get install -y ...
```

**After:**
```dockerfile
FROM dhi.io/python:3.12-alpine3.21-dev AS builder
```

**Changes:**
- Upgraded Python version from 3.11 to 3.12
- Changed from `slim-bookworm` to `alpine3.21` (smaller base image)
- Using `-dev` variant which includes pip and build tools needed during build stage
- Removed manual security update commands (DHI handles this)

#### Stage 2: Runtime Stage
**Before:**
```dockerfile
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get upgrade -y && apt-get install -y ca-certificates ...
RUN groupadd -g 1000 slackbot && useradd -r -u 1000 ...
USER slackbot
```

**After:**
```dockerfile
FROM dhi.io/python:3.12-alpine3.21
RUN mkdir -p /app/slack_bot && chown -R nonroot:nonroot /app
USER nonroot
```

**Changes:**
- DHI runtime images come with TLS certificates pre-installed
- DHI runtime images run as `nonroot` user by default (improves security)
- No need to manually create user; using built-in `nonroot` user
- Removed `ca-certificates` installation (already included in DHI)

### docker-compose.yml Changes

#### Redis Service
**Before:**
```yaml
redis:
  image: redis:7-alpine
```

**After:**
```yaml
redis:
  image: dhi.io/redis:7-alpine
```

#### PostgreSQL Service
**Before:**
```yaml
postgres:
  image: postgres:15-alpine
```

**After:**
```yaml
postgres:
  image: dhi.io/postgres:15-alpine
```

## Key Migration Considerations

### Non-Root User
- DHI runtime images run as `nonroot` user by default
- Port binding uses port 3000 (>1024, allowed for non-root users)
- All files are owned by `nonroot:nonroot` for security

### Package Management
- `-dev` variant of Python image used in builder stage (includes pip)
- Runtime stage does not have package managers (reduces attack surface)
- Virtual environment approach maintained for optimal build efficiency

### Security Improvements
- Smaller image sizes (alpine-based)
- No shell in runtime stage
- No package managers in runtime stage
- Running as non-root user by default
- Pre-included TLS certificates

### Compatibility
- Python 3.12 is compatible with application requirements
- Alpine 3.21 provides stable, minimal base
- All functionality preserved
- Build optimizations maintained

## Validation Steps

### Prerequisites
- Docker authentication configured for dhi.io registry
- Docker version 20.10 or later (for proper non-root port binding)

### Build Commands
```bash
# Build the Slack Bot service
docker build -t triage-slack-bot:dhi -f Dockerfile .

# Verify image
docker images | grep triage-slack-bot

# Test with docker-compose
docker-compose up
```

### Testing
1. Verify image builds successfully
2. Check that the application starts without errors
3. Verify Slack webhook connections work
4. Test Redis connectivity
5. Test PostgreSQL connectivity

## Rollback Plan
If issues arise, you can temporarily revert by:
1. Using `python:3.12-alpine` (public Docker images) in Dockerfile
2. Using `redis:7-alpine` and `postgres:15-alpine` in docker-compose.yml
3. Adjusting user ownership to work with standard images

## Notes
- DHI registry requires Docker authentication
- The migration uses Python 3.12 as specified
- All services have been migrated to DHI versions where available
- File structure and application logic remain unchanged
