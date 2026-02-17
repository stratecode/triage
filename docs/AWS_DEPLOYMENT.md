# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# AWS Serverless Deployment Guide

This guide covers deploying TrIAge as a serverless application on AWS using AWS SAM (Serverless Application Model).

## Architecture

```
┌─────────────────┐
│   API Gateway   │ ← JWT Authentication
└────────┬────────┘
         │
    ┌────┴────┐
    │ Lambda  │
    │Functions│
    └────┬────┘
         │
    ┌────┴────────────┐
    │  Secrets        │
    │  Manager        │
    │  - JIRA creds   │
    │  - JWT secret   │
    └─────────────────┘
```

### Components

- **API Gateway**: REST API with JWT authorization
- **Lambda Functions**:
  - `AuthorizerFunction`: JWT token validation
  - `GeneratePlanFunction`: Daily plan generation
  - `GetPlanFunction`: Retrieve existing plans
  - `ApprovePlanFunction`: Approve/reject plans
  - `DecomposeTaskFunction`: Task decomposition
  - `HealthCheckFunction`: Health check endpoint
- **EventBridge**: Scheduled plan generation (7 AM weekdays)
- **Secrets Manager**: Secure credential storage
- **CloudWatch Logs**: Application logging

## Prerequisites

1. **AWS CLI** configured with profile `stratecode`
   ```bash
   aws configure --profile stratecode
   ```

2. **AWS SAM CLI**
   ```bash
   pip install aws-sam-cli
   ```

3. **Python 3.11+**
   ```bash
   python --version
   ```

4. **JIRA credentials** in `.env` file
   ```bash
   cp .env.example .env
   # Edit .env with your JIRA credentials
   ```

## Configuration

### AWS Profile and Region

- **Profile**: `stratecode`
- **Region**: `eu-south-2` (Europe - Spain)

These are configured in:
- `samconfig.toml`
- `scripts/deploy.sh`
- All deployment scripts

### Environment Variables

The application uses AWS Secrets Manager for sensitive data:

- `/${ENVIRONMENT}/triage/jira-credentials`: JIRA connection details
- `/${ENVIRONMENT}/triage/jwt-secret`: JWT signing secret

## Deployment Steps

### 1. Initial Setup

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

### 2. Configure Secrets

Store JIRA credentials and generate JWT secret:
```bash
./scripts/setup-secrets.sh dev
```

This will:
- Read credentials from `.env`
- Store them in AWS Secrets Manager
- Generate a random JWT secret
- Display the JWT secret (save it securely!)

### 3. Deploy to AWS

Deploy the complete stack:
```bash
./scripts/deploy.sh dev
```

This will:
- Package Lambda dependencies
- Copy the `triage` package to Lambda
- Build the SAM application
- Deploy to AWS CloudFormation
- Output the API URL

Expected output:
```
🚀 Deploying TrIAge to AWS
Profile: stratecode
Region: eu-south-2
Environment: dev

✅ Deployment complete!

🌐 API URL: https://xxxxx.execute-api.eu-south-2.amazonaws.com/dev
```

### 4. Generate JWT Token

Create a token for API authentication:
```bash
./scripts/generate-token.sh dev admin 30
```

Parameters:
- Environment: `dev`
- User ID: `admin`
- Expiry: `30` days

Save the generated token securely.

### 5. Test the API

Test all endpoints:
```bash
./scripts/test-api.sh <API_URL> <JWT_TOKEN>
```

Example:
```bash
./scripts/test-api.sh \
  https://xxxxx.execute-api.eu-south-2.amazonaws.com/dev \
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Local Testing

Test Lambda functions locally before deploying:

### 1. Start Local API

```bash
./scripts/local-test.sh
```

This starts a local API Gateway emulator on `http://127.0.0.1:3000`

### 2. Test Locally

```bash
# Health check (no auth)
curl http://127.0.0.1:3000/api/v1/health

# Generate plan (requires token)
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-17"}' \
  http://127.0.0.1:3000/api/v1/plan
```

## API Endpoints

### Authentication

All endpoints (except `/health`) require JWT authentication:

```
Authorization: Bearer <jwt_token>
```

### Available Endpoints

#### Health Check
```http
GET /api/v1/health
```

No authentication required. Returns service status.

#### Generate Daily Plan
```http
POST /api/v1/plan
Content-Type: application/json

{
  "date": "2026-02-17",
  "closure_rate": 0.67
}
```

Generates a daily plan with up to 3 priorities.

#### Get Plan
```http
GET /api/v1/plan/{date}
```

Retrieves the plan for a specific date.

#### Approve Plan
```http
POST /api/v1/plan/{date}/approve
Content-Type: application/json

{
  "approved": true,
  "feedback": "Looks good!"
}
```

Approve or reject a generated plan.

#### Decompose Task
```http
POST /api/v1/task/{taskId}/decompose
Content-Type: application/json

{
  "target_days": 1
}
```

Decompose a long-running task into subtasks.

## Scheduled Execution

The `GeneratePlanFunction` is automatically triggered:
- **Schedule**: Monday-Friday at 7:00 AM UTC
- **EventBridge Rule**: `cron(0 7 ? * MON-FRI *)`

To modify the schedule, edit `template.yaml`:
```yaml
ScheduledEvent:
  Type: Schedule
  Properties:
    Schedule: cron(0 7 ? * MON-FRI *)
```

## Monitoring

### CloudWatch Logs

View logs for each function:
```bash
aws logs tail /aws/lambda/triage-api-dev-GeneratePlanFunction \
  --profile stratecode \
  --region eu-south-2 \
  --follow
```

### Metrics

Monitor in CloudWatch:
- Lambda invocations
- Error rates
- Duration
- Throttles

## Updating the Deployment

To update after code changes:
```bash
./scripts/deploy.sh dev
```

SAM will create a changeset and deploy only what changed.

## Environments

### Development
```bash
./scripts/deploy.sh dev
```

### Production
```bash
./scripts/setup-secrets.sh prod
./scripts/deploy.sh prod
```

## Costs

Estimated monthly costs (with AWS Free Tier):

- **API Gateway**: ~$3.50/million requests
- **Lambda**: Free tier covers ~1M requests/month
- **Secrets Manager**: $0.40/secret/month
- **CloudWatch Logs**: ~$0.50/GB

**Total**: ~$5-10/month for moderate usage

## Troubleshooting

### Deployment Fails

Check AWS credentials:
```bash
aws sts get-caller-identity --profile stratecode --region eu-south-2
```

### Lambda Errors

View logs:
```bash
sam logs -n GeneratePlanFunction --stack-name triage-api-dev --tail
```

### Authentication Issues

Verify JWT secret:
```bash
aws secretsmanager get-secret-value \
  --profile stratecode \
  --region eu-south-2 \
  --secret-id /dev/triage/jwt-secret
```

### JIRA Connection Errors

Test JIRA credentials:
```bash
python examples/diagnose-jira-connection.py
```

## Cleanup

Remove all AWS resources:
```bash
aws cloudformation delete-stack \
  --profile stratecode \
  --region eu-south-2 \
  --stack-name triage-api-dev
```

Delete secrets:
```bash
aws secretsmanager delete-secret \
  --profile stratecode \
  --region eu-south-2 \
  --secret-id /dev/triage/jira-credentials \
  --force-delete-without-recovery

aws secretsmanager delete-secret \
  --profile stratecode \
  --region eu-south-2 \
  --secret-id /dev/triage/jwt-secret \
  --force-delete-without-recovery
```

## Security Best Practices

1. **Rotate JWT secrets** regularly
2. **Use short-lived tokens** (30 days max)
3. **Enable CloudTrail** for audit logging
4. **Restrict IAM permissions** to minimum required
5. **Use VPC** for production deployments
6. **Enable API Gateway throttling**

## Next Steps

1. **Add DynamoDB** for plan persistence
2. **Implement webhooks** for JIRA events
3. **Add SNS notifications** for plan approvals
4. **Create CloudFormation StackSets** for multi-region
5. **Implement API versioning** strategy
6. **Add WAF rules** for API protection

## Support

For issues or questions:
- Check CloudWatch Logs
- Review SAM build output
- Test locally with `./scripts/local-test.sh`
- Verify secrets in Secrets Manager
