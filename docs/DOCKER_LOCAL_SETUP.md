# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Docker Local Setup Guide

This guide explains how to run a complete local replica of the AWS serverless stack using Docker. This is essential for debugging and testing before deploying to AWS.

## Architecture Comparison

### AWS Production Stack
```
┌─────────────────┐
│   API Gateway   │ ← JWT Authorizer (Lambda)
└────────┬────────┘
         │
    ┌────┴────────────────────┐
    │  Lambda Functions       │
    │  - generate_plan        │
    │  - get_plan            │
    │  - approve_plan        │
    │  - decompose_task      │
    └────┬────────────────────┘
         │
    ┌────┴────────────┐
    │  EventBridge    │ ← Cron: 7 AM weekdays
    └─────────────────┘
         │
    ┌────┴────────────┐
    │ Secrets Manager │
    │ - JIRA creds    │
    │ - JWT secret    │
    └─────────────────┘
```

### Docker Local Stack
```
┌─────────────────┐
│   FastAPI       │ ← JWT middleware
│   (port 8000)   │
└────────┬────────┘
         │
    ┌────┴────────────────────┐
    │  Lambda Handlers        │
    │  (imported as modules)  │
    └─────────────────────────┘
         │
    ┌────┴────────────┐
    │  Scheduler      │ ← Cron simulation
    │  (croniter)     │
    └─────────────────┘
         │
    ┌────┴────────────┐
    │  Environment    │
    │  Variables      │
    │  (.env file)    │
    └─────────────────┘
```

## Components

### 1. API Service (`api`)
- **Image**: Custom Python 3.11 with FastAPI
- **Port**: 8000
- **Purpose**: Simulates API Gateway + Lambda functions
- **Features**:
  - JWT authentication middleware
  - All Lambda handlers exposed as REST endpoints
  - Hot-reload for development
  - Structured logging to files

### 2. Scheduler Service (`scheduler`)
- **Image**: Custom Python 3.11 with croniter
- **Purpose**: Simulates EventBridge scheduled events
- **Features**:
  - Cron-based plan generation
  - Configurable schedule
  - Automatic API health checks
  - Retry logic

### 3. Logs Viewer (`logs-viewer`)
- **Image**: Dozzle
- **Port**: 8080
- **Purpose**: Real-time log viewing
- **Features**:
  - Web-based log viewer
  - Multi-container support
  - Search and filtering

## Prerequisites

1. **Docker** and **Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **JIRA Credentials**
   - JIRA base URL
   - Email address
   - API token

3. **Environment File**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## Quick Start

### 1. Configure Environment

Edit `.env` file:
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token
JWT_SECRET=your-random-secret-here
```

### 2. Start the Stack

```bash
./scripts/docker-local.sh up
```

This will:
- Build Docker images
- Start all services
- Wait for health checks
- Display access URLs

Expected output:
```
ℹ️  Starting TrIAge local stack...
ℹ️  Waiting for services to be ready...
✅ TrIAge local stack is running!

📍 API URL: http://localhost:8000
📊 Logs Viewer: http://localhost:8080
```

### 3. Generate JWT Token

```bash
./scripts/docker-local.sh token admin 30
```

Or via curl:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=30"
```

Save the token for API requests.

### 4. Test the API

```bash
./scripts/docker-local.sh test
```

Or manually:
```bash
# Health check (no auth)
curl http://localhost:8000/api/v1/health

# Generate plan (requires token)
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-17"}' \
  http://localhost:8000/api/v1/plan
```

## Available Commands

### Stack Management

```bash
# Start the stack
./scripts/docker-local.sh up

# Stop the stack
./scripts/docker-local.sh down

# Restart the stack
./scripts/docker-local.sh restart

# Rebuild images and restart
./scripts/docker-local.sh rebuild
```

### Debugging

```bash
# View logs (follow mode)
./scripts/docker-local.sh logs api
./scripts/docker-local.sh logs scheduler

# Open shell in container
./scripts/docker-local.sh shell api
./scripts/docker-local.sh shell scheduler

# View logs in browser
open http://localhost:8080
```

### Testing

```bash
# Run automated tests
./scripts/docker-local.sh test

# Generate JWT token
./scripts/docker-local.sh token admin 7
```

### Cleanup

```bash
# Remove containers and volumes
./scripts/docker-local.sh clean
```

## API Endpoints

All endpoints match the AWS production API:

### Health Check
```http
GET /api/v1/health
```
No authentication required.

### Generate Daily Plan
```http
POST /api/v1/plan
Authorization: Bearer <token>
Content-Type: application/json

{
  "date": "2026-02-17",
  "closure_rate": 0.67
}
```

### Get Plan
```http
GET /api/v1/plan/{date}
Authorization: Bearer <token>
```

### Approve Plan
```http
POST /api/v1/plan/{date}/approve
Authorization: Bearer <token>
Content-Type: application/json

{
  "approved": true,
  "feedback": "Looks good!"
}
```

### Decompose Task
```http
POST /api/v1/task/{taskId}/decompose
Authorization: Bearer <token>
Content-Type: application/json

{
  "target_days": 1
}
```

### Generate Token (Local Only)
```http
POST /api/v1/auth/token?user_id=admin&expiry_days=30
```
This endpoint only exists in local environment.

## Scheduler Configuration

The scheduler simulates EventBridge cron triggers.

### Default Schedule
```
0 7 * * 1-5  # 7 AM, Monday-Friday
```

### Custom Schedule

Edit `.env`:
```bash
SCHEDULE_CRON=0 8 * * *  # 8 AM every day
```

Or in `docker-compose.yml`:
```yaml
scheduler:
  environment:
    - SCHEDULE_CRON=0 8 * * *
```

### Cron Format
```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, 0 and 7 are Sunday)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

Examples:
- `0 7 * * 1-5` - 7 AM weekdays
- `0 8 * * *` - 8 AM every day
- `*/30 * * * *` - Every 30 minutes
- `0 9,17 * * 1-5` - 9 AM and 5 PM weekdays

## Development Workflow

### 1. Code Changes

The stack uses volume mounts for hot-reload:

```yaml
volumes:
  - ./triage:/app/triage:ro
  - ./lambda:/app/lambda:ro
```

After changing code:
```bash
# Restart to pick up changes
./scripts/docker-local.sh restart

# Or rebuild if dependencies changed
./scripts/docker-local.sh rebuild
```

### 2. View Logs

Real-time logs:
```bash
./scripts/docker-local.sh logs api
```

Or use the web viewer:
```bash
open http://localhost:8080
```

### 3. Debug in Container

```bash
# Open shell
./scripts/docker-local.sh shell api

# Inside container
python
>>> from triage.jira_client import JiraClient
>>> # Test your code
```

### 4. Test Changes

```bash
# Run automated tests
./scripts/docker-local.sh test

# Or manual curl tests
curl -X POST \
  -H "Authorization: Bearer $(./scripts/docker-local.sh token admin 1 | jq -r .token)" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-17"}' \
  http://localhost:8000/api/v1/plan | jq .
```

## Troubleshooting

### Services Won't Start

Check Docker resources:
```bash
docker system df
docker system prune -f
```

Check logs:
```bash
docker-compose logs
```

### API Returns 500 Errors

Check JIRA credentials:
```bash
# View environment
docker-compose exec api env | grep JIRA

# Test JIRA connection
docker-compose exec api python examples/diagnose-jira-connection.py
```

### Scheduler Not Triggering

Check scheduler logs:
```bash
./scripts/docker-local.sh logs scheduler
```

Verify cron schedule:
```bash
docker-compose exec scheduler env | grep SCHEDULE_CRON
```

### JWT Token Issues

Regenerate token:
```bash
./scripts/docker-local.sh token admin 1
```

Check JWT secret:
```bash
docker-compose exec api env | grep JWT_SECRET
```

### Port Already in Use

Change ports in `docker-compose.yml`:
```yaml
api:
  ports:
    - "8001:8000"  # Use 8001 instead of 8000
```

## Differences from AWS

### What's the Same
- All API endpoints and responses
- Lambda handler logic
- JWT authentication
- Scheduled plan generation
- Error handling and logging

### What's Different
- **Secrets Manager**: Uses environment variables instead
- **CloudWatch Logs**: Uses local files + Dozzle
- **API Gateway**: Uses FastAPI instead
- **EventBridge**: Uses croniter instead
- **IAM**: No IAM, uses simple JWT
- **Cold starts**: No cold starts in local

### Local-Only Features
- `/api/v1/auth/token` endpoint for token generation
- Hot-reload for code changes
- Direct shell access to containers
- Real-time log viewer

## Performance Comparison

| Metric | AWS Lambda | Docker Local |
|--------|-----------|--------------|
| Cold start | 1-3s | 0s |
| Warm response | 50-200ms | 10-50ms |
| Memory | 512MB | Configurable |
| Timeout | 30s | Configurable |
| Concurrency | 1000+ | Limited by host |

## Security Notes

### Local Environment
- JWT secret is in `.env` file
- No encryption at rest
- No network isolation
- Suitable for development only

### Production (AWS)
- JWT secret in Secrets Manager
- Encryption at rest and in transit
- VPC isolation
- IAM-based access control

## Next Steps

1. **Test locally** before deploying to AWS
2. **Debug issues** using logs and shell access
3. **Validate changes** with automated tests
4. **Deploy to AWS** using `./scripts/deploy.sh`

## Integration with AWS Deployment

### Local Testing Flow
```bash
# 1. Develop locally
./scripts/docker-local.sh up

# 2. Test changes
./scripts/docker-local.sh test

# 3. Verify logs
./scripts/docker-local.sh logs api

# 4. Deploy to AWS
./scripts/deploy.sh dev

# 5. Test AWS deployment
./scripts/test-api.sh <AWS_API_URL> <AWS_TOKEN>
```

### Environment Parity

Keep `.env` and AWS Secrets Manager in sync:

```bash
# Local
JIRA_BASE_URL=https://your-domain.atlassian.net

# AWS
aws secretsmanager get-secret-value \
  --secret-id /dev/triage/jira-credentials \
  --query SecretString
```

## Support

For issues:
1. Check logs: `./scripts/docker-local.sh logs api`
2. Verify environment: `docker-compose exec api env`
3. Test JIRA connection: `python examples/diagnose-jira-connection.py`
4. Review this guide
5. Check AWS deployment docs: `docs/AWS_DEPLOYMENT.md`

## Additional Resources

- [AWS Deployment Guide](./AWS_DEPLOYMENT.md)
- [JIRA API Migration](./JIRA_API_MIGRATION.md)
- [Logging Guide](./LOGGING_GUIDE.md)
- [Repository Files Guide](./REPOSITORY_FILES_GUIDE.md)
