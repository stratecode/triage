# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Docker Local Stack - Status Report

## Overview

The Docker local stack is now **fully operational** and replicates the AWS serverless architecture (API Gateway + Lambda + EventBridge) for local development and debugging.

## Stack Components

### 1. API Service (Port 8000)
- **Technology**: FastAPI + Uvicorn
- **Purpose**: Simulates AWS API Gateway + Lambda functions
- **Features**:
  - JWT authentication (simulates Lambda Authorizer)
  - All API endpoints functional
  - Mock Secrets Manager for JIRA credentials
  - Health checks and monitoring

### 2. Scheduler Service
- **Technology**: Python + croniter
- **Purpose**: Simulates AWS EventBridge scheduled events
- **Features**:
  - Cron-based scheduling (default: 7 AM weekdays)
  - Automatic daily plan generation
  - Configurable schedule via environment variables

### 3. Logs Viewer (Port 8080)
- **Technology**: Dozzle
- **Purpose**: Real-time log viewing for all containers
- **Access**: http://localhost:8080

## API Endpoints

All endpoints are fully functional and tested:

### Authentication
- `POST /api/v1/auth/token` - Generate JWT token for testing

### Health Check
- `GET /api/v1/health` - Service health status (no auth required)

### Plan Management
- `POST /api/v1/plan` - Generate daily plan
- `GET /api/v1/plan/{date}` - Retrieve plan for specific date
- `POST /api/v1/plan/{date}/approve` - Approve or reject a plan

### Task Management
- `POST /api/v1/task/{taskId}/decompose` - Decompose long-running task into subtasks

## Test Results

All automated tests pass successfully:

```
✓ Health Check............................ PASS
✓ Unauthorized Access..................... PASS
✓ Generate Token.......................... PASS
✓ Generate Plan........................... PASS
✓ Get Plan................................ PASS
✓ Approve Plan............................ PASS

Total: 6/6 tests passed
```

## Configuration

### Environment Variables (.env)
```bash
# JIRA Configuration
JIRA_BASE_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token

# JWT Configuration
JWT_SECRET=dev-secret-change-in-production

# Scheduler Configuration
SCHEDULE_CRON=0 7 * * 1-5  # 7 AM weekdays
SCHEDULE_TIMEZONE=Europe/Madrid

# AWS Configuration (for local development)
AWS_DEFAULT_REGION=eu-west-1
```

## Quick Start

### Start the Stack
```bash
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f scheduler

# Or use web UI
open http://localhost:8080
```

### Run Tests
```bash
python3 examples/test_local_stack.py
```

### Generate a Token
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=30"
```

### Generate a Plan
```bash
TOKEN="your-jwt-token"
curl -X POST http://localhost:8000/api/v1/plan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-02-17"}'
```

### Stop the Stack
```bash
docker-compose down
```

## Issues Resolved

During setup, the following issues were identified and fixed:

1. ✅ **Method Name Mismatches**: 
   - `fetch_active_issues()` → `fetch_active_tasks()`
   - `classify()` → `classify_task()`
   - `fetch_issue()` → `get_task_by_key()`
   - `generate_plan()` → `generate_daily_plan()`

2. ✅ **Attribute Name Mismatches**:
   - `TaskClassification.issue` → `TaskClassification.task`
   - `AdminBlock.time_start/time_end` → `AdminBlock.scheduled_time`
   - `p.effort_hours` → `p.estimated_days`

3. ✅ **Decomposition Method Signature**:
   - Fixed to accept only `JiraIssue` parameter
   - Returns `List[SubtaskSpec]` directly

4. ✅ **Dependencies**:
   - Resolved boto3/botocore version conflicts
   - Added missing PyJWT dependency

## Architecture Alignment

The local stack accurately mirrors the AWS production architecture:

| AWS Service | Local Equivalent | Purpose |
|-------------|------------------|---------|
| API Gateway | FastAPI | HTTP API endpoints |
| Lambda Functions | Python handlers | Business logic |
| Lambda Authorizer | JWT middleware | Authentication |
| Secrets Manager | Environment variables | Credentials |
| EventBridge | Cron scheduler | Scheduled events |
| CloudWatch Logs | Dozzle + file logs | Log aggregation |

## Next Steps

The local stack is production-ready for:
- ✅ Local development and debugging
- ✅ Integration testing
- ✅ API endpoint validation
- ✅ JIRA integration testing
- ✅ Scheduler behavior verification

## Documentation

- [Docker Quick Start](../DOCKER_QUICKSTART.md) - Getting started guide
- [Docker Local Setup](DOCKER_LOCAL_SETUP.md) - Detailed setup instructions
- [Docker Setup Summary](DOCKER_SETUP_SUMMARY.md) - Architecture overview
- [Test Script](../examples/test_local_stack.py) - Automated test suite

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify environment variables in `.env`
3. Run test suite: `python3 examples/test_local_stack.py`
4. Review documentation in `docs/` folder

---

**Status**: ✅ Fully Operational  
**Last Updated**: 2026-02-17  
**Version**: 0.1.0
