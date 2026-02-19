# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

AI-powered execution support system that generates focused daily plans from JIRA tasks.

## What is TrIAge?

```
┌─────────────┐
│    JIRA     │  Single source of truth
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         TrIAge Engine               │
│  • Task Classification              │
│  • Dependency Detection             │
│  • Effort Estimation                │
│  • Priority Selection (max 3)       │
│  • Admin Task Grouping              │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│       Daily Plan (Markdown)         │
│  ✓ 3 Priority Tasks                 │
│  ✓ 90-min Admin Block               │
│  ✓ Closure Rate Tracking            │
└─────────────────────────────────────┘
```

**Core Principles:**
- Maximum 3 priorities per day (cognitive load minimization)
- All tasks must be closable within one working day
- Human approval required for all actions
- JIRA as single source of truth (no local state)

---

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- JIRA account with API token
- Docker (for local deployment)
- AWS CLI (for production deployment)

### Installation

```bash
# Clone and setup
git clone https://github.com/your-org/triage.git
cd triage
uv venv && source .venv/bin/activate
make install

# Configure JIRA credentials
cp .env.example .env
# Edit .env with your JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
```

---

## Deployment Options

### 1. Docker Local (Recommended for Development)

Full AWS stack replica with LocalStack.

```bash
# Start stack (includes Lambda deployment)
make docker-up

# Test API
make docker-test

# View logs
make docker-logs
```

**Architecture:**
```
Developer → API Gateway Proxy (port 8000) → LocalStack → Lambda Functions
                                                ↓
                                          EventBridge (scheduled plans)
                                                ↓
                                          PostgreSQL (future features)
```

**Endpoints:**
- API: `http://localhost:8000`
- Health: `http://localhost:8000/api/v1/health`
- Generate Plan: `POST http://localhost:8000/api/v1/plan/generate`

**Useful Commands:**
```bash
make docker-restart          # Clean restart
make docker-logs-localstack  # View Lambda deployment logs
make docker-lambda-list      # List deployed functions
make docker-test-health      # Test health endpoints
make docker-clean            # Clean up resources
```

### 2. AWS Production (dev/staging/prod)

Deploy to AWS Lambda + API Gateway.

```bash
# Deploy to dev
make deploy-dev

# Deploy to staging
make deploy-staging

# Deploy to prod
make deploy-prod

# Test deployment
API_URL=https://xxx.execute-api.eu-south-2.amazonaws.com/dev \
TOKEN=your-token \
make aws-test

# View logs
make aws-logs

# Prune stack (DESTRUCTIVE!)
make prune-dev
```

**Stack Resources:**
- Lambda Functions (GeneratePlan, HealthCheck, EventProcessor, PluginHandler, Authorizer)
- API Gateway (REST API with custom authorizer)
- EventBridge (scheduled plan generation)
- Secrets Manager (JIRA credentials)
- CloudWatch Logs

### 3. SAM Local (Quick Testing)

Run Lambda functions locally without full stack.

```bash
# One command deployment
make sam-deploy-all

# Or manual steps
make sam-build
make sam-start
make sam-test
```

---

## API Reference

### Postman Collection

Download the complete API collection:
- Collection: [`events/postman_collection.json`](events/postman_collection.json) *(to be created)*
- Environment: [`events/postman_environment.json`](events/postman_environment.json) *(to be created)*

### Core Endpoints

#### Health Check
```bash
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-19T17:00:00Z"
}
```

#### Generate Daily Plan
```bash
POST /api/v1/plan/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "date": "2026-02-19",
  "closure_rate": 0.67
}
```

**Response:**
```json
{
  "plan": "# Daily Plan - 2026-02-19\n\n## Today's Priorities\n...",
  "priorities": 3,
  "admin_tasks": 2,
  "other_tasks": 8
}
```

#### Test Endpoints (Docker Local)
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Generate plan
curl -X POST http://localhost:8000/api/v1/plan/generate \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-02-19"}'
```

---

## Configuration

### Environment Variables

```bash
# Required
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-token-here

# Optional
JIRA_PROJECT=PROJ              # Filter by project
ADMIN_TIME_START=14:00         # Admin block start
ADMIN_TIME_END=15:30           # Admin block end
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
```

**Generate JIRA API Token:**
https://id.atlassian.com/manage-profile/security/api-tokens

---

## Development

### Project Structure

```
triage/                    # Core package
├── core/                  # Core business logic
│   ├── actions.py        # Core actions (generate plan, etc.)
│   └── events.py         # Event handling
├── plugins/              # Plugin system
│   ├── base.py          # Base plugin interface
│   └── slack/           # Slack integration
├── models.py            # Data models
├── jira_client.py       # JIRA integration
├── task_classifier.py   # Task classification
├── plan_generator.py    # Plan generation
└── cli.py               # CLI interface

lambda/                   # AWS Lambda handlers
├── handlers.py          # API handlers
├── event_processor.py   # Event processing
├── plugin_handler.py    # Plugin endpoints
└── authorizer.py        # Custom authorizer

docker/                   # Docker services
├── Dockerfile.api       # API service
├── Dockerfile.scheduler # Scheduler service
└── init-localstack.sh   # LocalStack initialization

scripts/                  # Deployment scripts
├── deploy.sh            # AWS deployment
├── prune-stack.sh       # Stack cleanup
├── docker-local.sh      # Docker management
└── test-*.sh            # Testing scripts

tests/                    # Test suite
├── unit/                # Unit tests
├── property/            # Property-based tests (Hypothesis)
└── integration/         # Integration tests

examples/                 # Demo scripts
├── demo_mvp.py          # Complete MVP demo
├── validate_mvp.py      # MVP validation
└── diagnose-jira-connection.py
```

### Running Tests

```bash
make test              # All tests
make test-unit         # Unit tests only
make test-property     # Property-based tests
make test-integration  # Integration tests
make lint              # Linting
make format            # Code formatting
```

### Makefile Commands

```bash
# Development
make install           # Install dependencies
make clean             # Clean generated files

# Docker Local
make docker-up         # Start stack
make docker-down       # Stop stack
make docker-restart    # Clean restart
make docker-test       # Test API
make docker-logs       # View logs
make docker-clean      # Clean resources

# AWS Deployment
make deploy-dev        # Deploy to dev
make deploy-staging    # Deploy to staging
make deploy-prod       # Deploy to prod
make prune-dev         # Delete dev stack
make aws-logs          # View Lambda logs
make aws-test          # Test deployment

# SAM Local
make sam-deploy-all    # Complete deployment
make sam-build         # Build functions
make sam-start         # Start API
make sam-test          # Test functions

# Examples
make demo-mvp          # Run MVP demo
make validate-mvp      # Validate implementation
make diagnose-jira     # Diagnose JIRA connection
```

---

## Troubleshooting

### JIRA Connection Issues

```bash
# Diagnose connection
python examples/diagnose-jira-connection.py

# Enable debug logging
triage generate-plan --debug
```

**Common Issues:**
- **401/403**: Invalid credentials → regenerate API token
- **410**: Old API endpoint → update to latest version
- **429**: Rate limiting → automatic retry with backoff
- **No tasks**: Check `JIRA_PROJECT` filter in `.env`

### Docker Issues

```bash
# View LocalStack logs
make docker-logs-localstack

# List Lambda functions
make docker-lambda-list

# Check API Gateway
make docker-api-gateway

# Test health endpoints
make docker-test-health

# Clean restart
make docker-restart
```

### AWS Deployment Issues

```bash
# View CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name triage-api-dev \
  --profile stratecode

# View Lambda logs
make aws-logs

# Validate template
sam validate --lint

# Prune and redeploy
make prune-dev
make deploy-dev
```

---

## License

GNU Affero General Public License v3 (AGPLv3)

Copyright (C) 2026 StrateCode

---

**TrIAge** - Reduce cognitive load, increase productivity. 🎯