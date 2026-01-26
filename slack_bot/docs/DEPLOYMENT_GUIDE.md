# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# TrIAge Slack Bot - Quick Deployment Guide

This guide provides quick-start instructions for deploying the TrIAge Slack Bot in various environments.

## Prerequisites

- Docker and Docker Compose installed
- Slack workspace with admin access
- TrIAge API instance running
- PostgreSQL database
- Redis instance

## Quick Start (Local Development)

1. **Clone and navigate to slack_bot directory:**
   ```bash
   cd slack_bot
   ```

2. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

3. **Edit .env with your credentials:**
   - Get Slack credentials from https://api.slack.com/apps
   - Set TrIAge API URL and token
   - Generate a secure 32+ character encryption key

4. **Start all services:**
   ```bash
   docker-compose up -d
   ```

5. **Verify services are running:**
   ```bash
   docker-compose ps
   docker-compose logs -f slack-bot
   ```

6. **Configure Slack App webhook URL:**
   - Set to `http://your-server:3000/slack/events`
   - For local testing, use ngrok: `ngrok http 3000`

## Production Deployment Checklist

### Pre-Deployment

- [ ] Slack App created and configured
- [ ] OAuth scopes configured (chat:write, commands, users:read, channels:read, im:write)
- [ ] Slash commands registered (/triage plan, /triage status, /triage help, /triage config)
- [ ] Event subscriptions enabled
- [ ] Interactivity enabled
- [ ] PostgreSQL database created
- [ ] Redis instance available
- [ ] TrIAge API accessible via HTTPS
- [ ] SSL certificate for webhook endpoint
- [ ] Secrets stored in secure secret manager

### Deployment Steps

1. **Build Docker image:**
   ```bash
   docker build -t triage-slack-bot:latest -f Dockerfile ..
   ```

2. **Push to registry (if using container orchestration):**
   ```bash
   docker tag triage-slack-bot:latest your-registry/triage-slack-bot:latest
   docker push your-registry/triage-slack-bot:latest
   ```

3. **Deploy using your chosen method:**
   - Docker: See "Docker Deployment" section in README.md
   - Kubernetes: See "Kubernetes Deployment" section in README.md
   - AWS Lambda: See "AWS Lambda Deployment" section in README.md
   - GCP Cloud Run: See "GCP Cloud Run Deployment" section in README.md

4. **Configure environment variables:**
   - Set all required variables (see Environment Variables Reference in README.md)
   - Use secret management for sensitive values

5. **Update Slack webhook URL:**
   - Set to your deployed endpoint URL
   - Must be HTTPS in production

6. **Test the deployment:**
   - Install bot in test workspace
   - Run `/triage help` command
   - Verify webhook signature validation
   - Test plan delivery

### Post-Deployment

- [ ] Health checks configured and passing
- [ ] Monitoring and alerting set up
- [ ] Log aggregation configured
- [ ] Database backups scheduled
- [ ] SSL certificate renewal automated
- [ ] Documentation updated with production URLs
- [ ] Team trained on bot usage

## Environment Variables Quick Reference

### Critical Variables (Must Set)

```bash
# Slack Credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret

# TrIAge API
TRIAGE_API_URL=https://api.triage.example.com
TRIAGE_API_TOKEN=your-api-token

# Database
DATABASE_URL=postgresql://user:password@host:5432/triage_slack

# Security
ENCRYPTION_KEY=your-secure-32-character-key-here
```

### Optional Variables (Recommended Defaults)

```bash
# Redis
REDIS_URL=redis://redis:6379
REDIS_TTL_SECONDS=300

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Performance
WEBHOOK_TIMEOUT_SECONDS=3
MAX_RETRIES=3
RETRY_BACKOFF_BASE=2.0
```

## Common Deployment Scenarios

### Scenario 1: Single Server with Docker

Best for: Small teams, development, staging

```bash
# On your server
git clone <repository>
cd slack_bot
cp .env.example .env
# Edit .env with your values
docker-compose up -d
```

### Scenario 2: Kubernetes Cluster

Best for: Production, high availability, auto-scaling

```bash
# Create secrets
kubectl create secret generic slack-bot-secrets \
  --from-literal=bot-token=xoxb-token \
  --from-literal=signing-secret=secret \
  --from-literal=database-url=postgresql://... \
  --from-literal=encryption-key=key

# Deploy
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Scenario 3: AWS Lambda (Serverless)

Best for: Cost optimization, variable load, event-driven

```bash
# Package and deploy
pip install -r requirements.txt -t package/
cp -r slack_bot package/
cd package && zip -r ../slack-bot-lambda.zip .

# Upload to Lambda via AWS Console or CLI
aws lambda create-function \
  --function-name triage-slack-bot \
  --runtime python3.11 \
  --handler slack_bot.main.lambda_handler \
  --zip-file fileb://slack-bot-lambda.zip
```

### Scenario 4: GCP Cloud Run

Best for: Containerized serverless, auto-scaling, pay-per-use

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/triage-slack-bot
gcloud run deploy triage-slack-bot \
  --image gcr.io/PROJECT_ID/triage-slack-bot \
  --platform managed \
  --allow-unauthenticated
```

## Troubleshooting Quick Fixes

### Bot not responding
```bash
# Check logs
docker-compose logs -f slack-bot

# Verify token
echo $SLACK_BOT_TOKEN | grep xoxb

# Test webhook endpoint
curl -X POST http://localhost:3000/slack/events
```

### Database connection failed
```bash
# Test connection
docker exec triage-postgres psql -U triage -d triage_slack -c "SELECT 1"

# Check DATABASE_URL format
echo $DATABASE_URL
```

### Redis connection failed
```bash
# Test Redis
docker exec triage-redis redis-cli ping

# Check REDIS_URL
echo $REDIS_URL
```

### Webhook signature validation failed
```bash
# Verify signing secret matches Slack App
# Check system time is synchronized
date
```

## Monitoring Endpoints

- **Health Check**: `GET /health` - Returns 200 if service is running
- **Readiness Check**: `GET /ready` - Returns 200 if service is ready
- **Metrics**: Configure your monitoring tool to scrape these endpoints

## Security Reminders

1. **Never commit .env files** - Use .env.example as template
2. **Use HTTPS in production** - Required for Slack webhooks
3. **Rotate credentials regularly** - Especially encryption keys
4. **Enable audit logging** - Track all user actions
5. **Backup database regularly** - Automated daily backups recommended

## Support and Documentation

- Full documentation: See README.md in slack_bot directory
- Architecture details: See design.md in .kiro/specs/slack-integration/
- Requirements: See requirements.md in .kiro/specs/slack-integration/
- Issue tracking: Contact StrateCode support

## License

Copyright (C) 2026 StrateCode
Licensed under the GNU Affero General Public License v3 (AGPLv3)
