# Docker Hardened Images (DHI) - Building and Testing Guide

## Overview
This guide provides instructions for building and testing the TrIAge Slack Bot with Docker Hardened Images.

## Prerequisites

### Docker Version
- Docker version 20.10 or later
- Docker Desktop (if using local development)

### Registry Authentication
DHI images are hosted at `dhi.io` registry and require authentication.

#### Step 1: Obtain Docker Hub Account
1. Create account at https://hub.docker.com (if not already created)
2. Note your Docker Hub username and password (or access token)

#### Step 2: Login to DHI Registry
```bash
# Login to Docker Hub (required for DHI)
docker login

# When prompted:
# Username: <your-docker-hub-username>
# Password: <your-docker-hub-password-or-token>
```

#### Step 3: Verify Authentication
```bash
docker pull dhi.io/python:3.12-alpine3.21-dev
```

## Building the Application

### Build with DHI (Primary Method)
```bash
# Build the Slack Bot service
docker build -t triage-slack-bot:dhi -f Dockerfile .

# Verify the build
docker images | grep triage-slack-bot

# Check image size
docker images --format "table {{.Repository}}\t{{.Size}}" | grep triage-slack-bot
```

### Build with Fallback Images (If DHI Unavailable)
If you don't have DHI registry access, edit the Dockerfile and replace:

```dockerfile
# Change from:
FROM dhi.io/python:3.12-alpine3.21-dev AS builder
FROM dhi.io/python:3.12-alpine3.21

# Change to:
FROM python:3.12-alpine AS builder
FROM python:3.12-alpine
```

Then adjust the USER handling (comment out nonroot, use 1000:1000 or create custom user).

## Running with Docker Compose

### Using DHI Images
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f slack-bot

# Stop services
docker-compose down
```

### Environment Configuration
Ensure `.env` file is properly configured:
- SLACK_BOT_TOKEN
- SLACK_SIGNING_SECRET
- Database credentials
- Redis connection settings

## Testing the Application

### Health Check
```bash
# Check Slack Bot health
docker exec triage-slack-bot python -c "import main; print('OK')"

# Or use the built-in health check
curl -f http://localhost:3000/health || echo "Service not responding"
```

### Redis Connectivity
```bash
docker exec triage-redis redis-cli ping
# Expected output: PONG
```

### PostgreSQL Connectivity
```bash
docker exec triage-postgres pg_isready -U triage
# Expected output: accepting connections
```

### Application Logs
```bash
# View application logs
docker-compose logs slack-bot

# Follow logs in real-time
docker-compose logs -f slack-bot
```

## Troubleshooting

### Build Fails with 401 Unauthorized
**Issue:** `failed to authorize: failed to fetch anonymous token`

**Solution:**
1. Ensure you're logged in: `docker login`
2. Check credentials are correct
3. Verify internet connectivity
4. Use fallback public images (see above)

### Non-Root User Permission Issues
**Issue:** Application can't write to directories

**Solution:**
- Ensure volumes are owned by appropriate user
- Check file permissions in COPY commands
- Verify --chown flags are set correctly

### Port Binding Errors
**Issue:** Application can't bind to ports

**Solution:**
- Non-root users can only bind to ports >1024
- Port 3000 is correctly configured (>1024)
- Check for port conflicts: `lsof -i :3000`

### Health Check Failing
**Issue:** Container starts but health check fails

**Solution:**
- Wait longer for startup: increase `start-period` in HEALTHCHECK
- Verify application is running: `docker exec triage-slack-bot ps aux`
- Check application logs: `docker-compose logs slack-bot`

## Performance Comparison

### Image Size
```bash
# Original (Python 3.11-slim-bookworm)
# Approximately 150-180MB

# DHI (Python 3.12-alpine3.21)
# Approximately 80-100MB
# Savings: 40-50% smaller

# Benefits:
# - Faster pulls
# - Faster pushes
# - Less storage
# - Reduced attack surface
```

## Security Improvements

### What Changed
1. **Reduced Attack Surface**: Alpine base + no shell in runtime
2. **Non-Root User**: Runs as `nonroot` by default (uid/gid: varies per image)
3. **Minimal Tools**: No package managers in runtime stage
4. **Pre-Verified**: DHI images are regularly scanned

### Verification
```bash
# Check image contents
docker run --rm -it dhi.io/python:3.12-alpine3.21 sh
# This will fail - no shell in runtime image

docker run --rm -it dhi.io/python:3.12-alpine3.21-dev sh
# This works - dev image includes shell for debugging
```

## Migration Verification Checklist

- [ ] Docker version is 20.10 or later
- [ ] Authenticated to DHI registry (docker login successful)
- [ ] Dockerfile builds without errors
- [ ] Docker image is created and appears in `docker images`
- [ ] docker-compose.yml file is updated with DHI images
- [ ] `docker-compose up` starts all services
- [ ] Redis is accessible and responds to ping
- [ ] PostgreSQL is accessible and responds to pg_isready
- [ ] Slack Bot logs show successful startup
- [ ] Health check endpoint responds correctly
- [ ] Application can connect to Slack API
- [ ] Image size is smaller than before

## Next Steps

1. **Deploy to staging**: Test in staging environment
2. **Monitor performance**: Watch for any runtime issues
3. **Load testing**: Verify application performance under load
4. **Security audit**: Run vulnerability scans on final image
5. **Production deployment**: Schedule production rollout

## Support

For issues with:
- **DHI images**: Check Docker Hub documentation
- **Application**: Refer to TrIAge documentation
- **Build issues**: Review Dockerfile comments and DHI_MIGRATION_SUMMARY.md
