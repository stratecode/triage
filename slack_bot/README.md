# TrIAge Slack Bot

Slack integration for the TrIAge AI Secretary system.

## Overview

The Slack Bot provides a conversational, notification-driven interface for TrIAge through Slack. It acts as a thin client over the TrIAge HTTP API, enabling users to:

- Receive daily plans as interactive Slack messages
- Approve or reject plans using buttons
- Trigger plan generation via slash commands
- Get notified about blocking tasks
- Configure notification preferences

## Architecture

The Slack Bot follows an event-driven architecture:

- **Webhook Handler**: Receives and validates events from Slack
- **Message Formatter**: Converts TrIAge data to Slack Block Kit format
- **Command Handler**: Processes slash commands
- **OAuth Manager**: Handles workspace installation
- **Interaction Handler**: Processes button clicks and interactive elements

All business logic remains in the TrIAge API; the Slack Bot only handles Slack-specific formatting and communication.

## Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for local development)
- Slack workspace with admin access
- TrIAge API instance

### Local Development

1. **Copy environment configuration:**
   ```bash
   cp .env.example .env
   ```

2. **Configure environment variables:**
   Edit `.env` and set:
   - Slack API credentials (from Slack App configuration)
   - TrIAge API URL and token
   - Database and Redis URLs
   - Encryption key (32+ characters)

3. **Start services with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Run without Docker:**
   ```bash
   # Install dependencies
   uv pip install -e .
   
   # Run the bot
   python -m slack_bot.main
   ```

### Slack App Configuration

1. Create a new Slack App at https://api.slack.com/apps
2. Configure OAuth scopes:
   - `chat:write` - Send messages
   - `commands` - Handle slash commands
   - `users:read` - Get user information
   - `channels:read` - List channels
   - `im:write` - Send direct messages
3. Enable Event Subscriptions and set webhook URL
4. Create slash commands:
   - `/triage plan` - Generate daily plan
   - `/triage status` - Show plan status
   - `/triage help` - Show help
   - `/triage config` - Configure settings
5. Enable Interactivity for button handling
6. Copy credentials to `.env` file

## Configuration

Configuration is managed through environment variables. See `.env.example` for all available options.

### Required Variables

- `SLACK_BOT_TOKEN`: Bot user OAuth token (starts with `xoxb-`)
- `SLACK_SIGNING_SECRET`: Signing secret for webhook validation
- `SLACK_CLIENT_ID`: OAuth client ID
- `SLACK_CLIENT_SECRET`: OAuth client secret
- `TRIAGE_API_URL`: TrIAge API base URL (must use HTTPS)
- `TRIAGE_API_TOKEN`: API authentication token
- `DATABASE_URL`: PostgreSQL connection string
- `ENCRYPTION_KEY`: Encryption key for token storage (32+ chars)

### Optional Variables

- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `LOG_FORMAT`: Log format - `json` or `text` (default: `json`)
- `WEBHOOK_TIMEOUT_SECONDS`: Webhook response timeout (default: `3`)
- `MAX_RETRIES`: Maximum retry attempts for API calls (default: `3`)

## Logging

The bot uses structured JSON logging with automatic redaction of sensitive data:

- OAuth tokens
- API keys
- Passwords
- Bearer tokens

Logs include contextual information:
- User ID
- Team ID
- Event ID
- Request ID

## Security

- All OAuth tokens are encrypted at rest using AES-256
- Webhook signatures are validated using Slack's signing secret
- All TrIAge API calls use HTTPS
- Sensitive data is automatically redacted from logs
- User data is isolated per workspace

## Development

### Project Structure

```
slack_bot/
├── __init__.py           # Package initialization
├── main.py              # Application entry point
├── config.py            # Configuration management
├── logging_config.py    # Structured logging setup
├── .env.example         # Environment template
├── Dockerfile           # Container image
├── docker-compose.yml   # Local development stack
└── README.md           # This file
```

### Testing

Tests are located in the `tests/` directory at the project root:

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run property tests
pytest tests/property/

# Run integration tests
pytest tests/integration/
```

## Production Deployment

### Deployment Options

The Slack Bot can be deployed in several ways:

1. **Docker Container** (Recommended)
2. **Kubernetes**
3. **Cloud Serverless** (AWS Lambda, GCP Cloud Run, Azure Functions)
4. **Traditional VM/Server**

### Docker Deployment

#### Building the Image

```bash
# Build from slack_bot directory
cd slack_bot
docker build -t triage-slack-bot:latest -f Dockerfile ..

# Or build from project root
docker build -t triage-slack-bot:latest -f slack_bot/Dockerfile .
```

#### Running the Container

```bash
# Run with environment file
docker run -d \
  --name triage-slack-bot \
  --env-file .env \
  -p 3000:3000 \
  --restart unless-stopped \
  triage-slack-bot:latest

# Run with explicit environment variables
docker run -d \
  --name triage-slack-bot \
  -e SLACK_BOT_TOKEN=xoxb-your-token \
  -e SLACK_SIGNING_SECRET=your-secret \
  -e TRIAGE_API_URL=https://api.triage.example.com \
  -e TRIAGE_API_TOKEN=your-api-token \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e REDIS_URL=redis://redis:6379 \
  -e ENCRYPTION_KEY=your-32-char-key \
  -p 3000:3000 \
  --restart unless-stopped \
  triage-slack-bot:latest
```

#### Docker Compose Production

For production with Docker Compose:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f slack-bot

# Stop services
docker-compose down

# Restart specific service
docker-compose restart slack-bot

# Update and restart
docker-compose pull
docker-compose up -d
```

### Kubernetes Deployment

#### Deployment Manifest

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: triage-slack-bot
  labels:
    app: triage-slack-bot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: triage-slack-bot
  template:
    metadata:
      labels:
        app: triage-slack-bot
    spec:
      containers:
      - name: slack-bot
        image: triage-slack-bot:latest
        ports:
        - containerPort: 3000
        env:
        - name: SLACK_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: slack-bot-secrets
              key: bot-token
        - name: SLACK_SIGNING_SECRET
          valueFrom:
            secretKeyRef:
              name: slack-bot-secrets
              key: signing-secret
        - name: TRIAGE_API_URL
          valueFrom:
            configMapKeyRef:
              name: slack-bot-config
              key: api-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: slack-bot-secrets
              key: database-url
        - name: REDIS_URL
          value: redis://redis-service:6379
        - name: ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: slack-bot-secrets
              key: encryption-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: slack-bot-service
spec:
  selector:
    app: triage-slack-bot
  ports:
  - protocol: TCP
    port: 80
    targetPort: 3000
  type: LoadBalancer
```

#### Create Secrets

```bash
# Create secrets from literals
kubectl create secret generic slack-bot-secrets \
  --from-literal=bot-token=xoxb-your-token \
  --from-literal=signing-secret=your-secret \
  --from-literal=database-url=postgresql://user:pass@host:5432/db \
  --from-literal=encryption-key=your-32-char-key

# Create config map
kubectl create configmap slack-bot-config \
  --from-literal=api-url=https://api.triage.example.com
```

#### Deploy

```bash
# Apply manifests
kubectl apply -f k8s/

# Check status
kubectl get pods -l app=triage-slack-bot
kubectl logs -f deployment/triage-slack-bot

# Scale deployment
kubectl scale deployment triage-slack-bot --replicas=3
```

### AWS Lambda Deployment

For serverless deployment on AWS Lambda:

1. **Package the application:**
   ```bash
   # Install dependencies to a directory
   pip install -r requirements.txt -t package/
   
   # Copy application code
   cp -r slack_bot package/
   
   # Create deployment package
   cd package
   zip -r ../slack-bot-lambda.zip .
   ```

2. **Create Lambda function:**
   - Runtime: Python 3.11
   - Handler: `slack_bot.main.lambda_handler`
   - Memory: 512 MB
   - Timeout: 30 seconds
   - Environment variables: Set all required variables

3. **Configure API Gateway:**
   - Create REST API
   - Create POST method for `/slack/events`
   - Enable CORS if needed
   - Deploy to stage

4. **Update Slack webhook URL:**
   - Set to API Gateway endpoint URL

### GCP Cloud Run Deployment

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/triage-slack-bot

# Deploy to Cloud Run
gcloud run deploy triage-slack-bot \
  --image gcr.io/PROJECT_ID/triage-slack-bot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SLACK_BOT_TOKEN=xoxb-token,TRIAGE_API_URL=https://api.example.com \
  --set-secrets DATABASE_URL=database-url:latest,ENCRYPTION_KEY=encryption-key:latest \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 10
```

### Azure Container Instances

```bash
# Create resource group
az group create --name triage-rg --location eastus

# Create container
az container create \
  --resource-group triage-rg \
  --name triage-slack-bot \
  --image triage-slack-bot:latest \
  --dns-name-label triage-slack-bot \
  --ports 3000 \
  --environment-variables \
    SLACK_BOT_TOKEN=xoxb-token \
    TRIAGE_API_URL=https://api.example.com \
  --secure-environment-variables \
    DATABASE_URL=postgresql://... \
    ENCRYPTION_KEY=your-key \
  --cpu 1 \
  --memory 1
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SLACK_BOT_TOKEN` | Bot user OAuth token from Slack | `xoxb-123-456-abc` |
| `SLACK_SIGNING_SECRET` | Signing secret for webhook validation | `abc123def456` |
| `SLACK_CLIENT_ID` | OAuth client ID | `123456789.123456789` |
| `SLACK_CLIENT_SECRET` | OAuth client secret | `abc123def456ghi789` |
| `TRIAGE_API_URL` | TrIAge API base URL (HTTPS only) | `https://api.triage.example.com` |
| `TRIAGE_API_TOKEN` | API authentication token | `Bearer abc123...` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `ENCRYPTION_KEY` | Encryption key for tokens (32+ chars) | `your-secure-32-character-key-here` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `REDIS_TTL_SECONDS` | Event deduplication TTL | `300` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `LOG_FORMAT` | Log format (json or text) | `json` |
| `WEBHOOK_TIMEOUT_SECONDS` | Webhook response timeout | `3` |
| `MAX_RETRIES` | Maximum API retry attempts | `3` |
| `RETRY_BACKOFF_BASE` | Exponential backoff base | `2.0` |

## Monitoring and Observability

### Health Checks

The bot exposes health check endpoints:

- `GET /health` - Liveness probe (returns 200 if running)
- `GET /ready` - Readiness probe (returns 200 if ready to serve)

### Metrics

Key metrics to monitor:

- **Request Rate**: Webhook events per second
- **Response Time**: P50, P95, P99 latencies
- **Error Rate**: Failed webhook processing percentage
- **API Call Success**: TrIAge API call success rate
- **Queue Depth**: Pending async tasks

### Logging

Structured JSON logs include:

```json
{
  "timestamp": "2026-01-26T10:30:00Z",
  "level": "INFO",
  "message": "Plan delivered successfully",
  "user_id": "U12345",
  "team_id": "T12345",
  "event_id": "abc123",
  "request_id": "req-456"
}
```

### Alerting

Recommended alerts:

- Error rate > 5% for 5 minutes
- Response time P95 > 2 seconds
- API call failure rate > 10%
- Queue depth > 1000 items
- Memory usage > 80%

## Troubleshooting

### Common Issues

**Bot not responding to commands:**
- Verify `SLACK_BOT_TOKEN` is correct
- Check bot has required OAuth scopes
- Ensure webhook URL is accessible from Slack
- Check logs for signature validation errors

**Database connection errors:**
- Verify `DATABASE_URL` is correct
- Ensure PostgreSQL is running and accessible
- Check network connectivity
- Verify database user has required permissions

**Redis connection errors:**
- Verify `REDIS_URL` is correct
- Ensure Redis is running and accessible
- Check network connectivity

**TrIAge API errors:**
- Verify `TRIAGE_API_URL` uses HTTPS
- Check `TRIAGE_API_TOKEN` is valid
- Ensure API is accessible from bot
- Check API logs for errors

**Webhook signature validation failures:**
- Verify `SLACK_SIGNING_SECRET` is correct
- Check system clock is synchronized
- Ensure webhook payload is not modified

### Debug Mode

Enable debug logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in .env file
LOG_LEVEL=DEBUG
```

### Viewing Logs

```bash
# Docker
docker logs -f triage-slack-bot

# Docker Compose
docker-compose logs -f slack-bot

# Kubernetes
kubectl logs -f deployment/triage-slack-bot

# Follow logs with grep
docker logs -f triage-slack-bot | grep ERROR
```

## Security Best Practices

1. **Use secrets management:**
   - Store sensitive variables in secret managers (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)
   - Never commit `.env` files to version control
   - Rotate credentials regularly

2. **Network security:**
   - Use HTTPS for all external communication
   - Restrict ingress to webhook endpoints
   - Use private networks for database/Redis connections

3. **Container security:**
   - Run as non-root user (already configured)
   - Scan images for vulnerabilities
   - Keep base images updated
   - Use minimal base images (Alpine)

4. **Access control:**
   - Use least-privilege IAM roles
   - Restrict database user permissions
   - Enable audit logging

5. **Data protection:**
   - Encrypt tokens at rest (already implemented)
   - Use TLS for all connections
   - Implement data retention policies
   - Regular backups of PostgreSQL

## Backup and Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker exec triage-postgres pg_dump -U triage triage_slack > backup.sql

# Restore PostgreSQL
docker exec -i triage-postgres psql -U triage triage_slack < backup.sql
```

### Redis Backup

```bash
# Backup Redis (if persistence enabled)
docker exec triage-redis redis-cli SAVE
docker cp triage-redis:/data/dump.rdb ./redis-backup.rdb

# Restore Redis
docker cp ./redis-backup.rdb triage-redis:/data/dump.rdb
docker restart triage-redis
```

## Performance Tuning

### Scaling Recommendations

- **Horizontal scaling**: Run multiple bot instances behind load balancer
- **Database connection pooling**: Configure appropriate pool size
- **Redis clustering**: Use Redis Cluster for high availability
- **Async processing**: Ensure background tasks don't block webhooks

### Resource Requirements

**Minimum (Development):**
- CPU: 0.5 cores
- Memory: 256 MB
- Storage: 1 GB

**Recommended (Production):**
- CPU: 1-2 cores
- Memory: 512 MB - 1 GB
- Storage: 10 GB
- Database: 2 cores, 4 GB RAM
- Redis: 1 core, 512 MB RAM

## License

Copyright (C) 2026 StrateCode

Licensed under the GNU Affero General Public License v3 (AGPLv3).
See LICENSE file for details.
