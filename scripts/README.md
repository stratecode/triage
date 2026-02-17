# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Deployment Scripts

Essential scripts for deploying and managing TrIAge on AWS.

## Prerequisites

- AWS CLI configured with profile `stratecode`
- AWS SAM CLI installed
- Python 3.11+ with PyJWT
- Valid AWS credentials with appropriate permissions

## Scripts

### 1. setup-iam-permissions.sh

Configure IAM permissions for deployment.

```bash
./scripts/setup-iam-permissions.sh <IAM_USERNAME>
```

**What it does:**
- Creates IAM policy with required permissions
- Attaches policy to specified user
- Grants access to CloudFormation, Lambda, API Gateway, etc.

**Example:**
```bash
./scripts/setup-iam-permissions.sh juan.perez
```

### 2. deploy.sh

Deploy TrIAge API to AWS.

```bash
./scripts/deploy.sh [environment]
```

**Parameters:**
- `environment` (optional): dev, staging, or prod (default: dev)

**What it does:**
- Packages Lambda dependencies
- Builds SAM application
- Creates S3 bucket for artifacts
- Deploys CloudFormation stack
- Outputs API URL

**Example:**
```bash
./scripts/deploy.sh dev
./scripts/deploy.sh prod
```

### 3. setup-secrets.sh

Configure AWS Secrets Manager with JIRA credentials and JWT secret.

```bash
./scripts/setup-secrets.sh [environment]
```

**Prerequisites:**
- `.env` file with JIRA credentials (see `.env.example`)

**What it does:**
- Reads JIRA credentials from `.env`
- Creates/updates JIRA credentials secret
- Generates and stores JWT secret
- Outputs JWT secret for token generation

**Example:**
```bash
./scripts/setup-secrets.sh dev
```

### 4. generate-token.sh

Generate JWT authentication token.

```bash
./scripts/generate-token.sh [environment] [user_id] [expiry_days]
```

**Parameters:**
- `environment` (optional): dev, staging, or prod (default: dev)
- `user_id` (optional): User identifier (default: admin)
- `expiry_days` (optional): Token validity in days (default: 30)

**What it does:**
- Retrieves JWT secret from Secrets Manager
- Generates JWT token with specified expiry
- Outputs token for API authentication

**Example:**
```bash
./scripts/generate-token.sh dev admin 30
```

### 5. test-api.sh

Test deployed API endpoints.

```bash
./scripts/test-api.sh <API_URL> [TOKEN]
```

**Parameters:**
- `API_URL` (required): API Gateway endpoint URL
- `TOKEN` (optional): JWT token for authenticated endpoints

**What it does:**
- Tests health check endpoint
- Tests plan generation (if token provided)
- Tests plan retrieval (if token provided)
- Tests plan approval (if token provided)

**Example:**
```bash
# Test health check only
./scripts/test-api.sh https://xxx.execute-api.eu-south-2.amazonaws.com/dev

# Test all endpoints
TOKEN=$(./scripts/generate-token.sh dev | grep "Token:" | cut -d' ' -f2)
./scripts/test-api.sh https://xxx.execute-api.eu-south-2.amazonaws.com/dev $TOKEN
```

## Deployment Workflow

Complete deployment from scratch:

```bash
# 1. Configure IAM permissions
./scripts/setup-iam-permissions.sh your-username

# 2. Create .env file with JIRA credentials
cp .env.example .env
# Edit .env with your JIRA credentials

# 3. Deploy the API
./scripts/deploy.sh dev

# 4. Setup secrets
./scripts/setup-secrets.sh dev

# 5. Generate authentication token
./scripts/generate-token.sh dev

# 6. Test the API
API_URL="<URL from deploy output>"
TOKEN="<token from generate-token output>"
./scripts/test-api.sh $API_URL $TOKEN
```

## Configuration

All scripts use these default values:

- **AWS Profile**: `stratecode`
- **AWS Region**: `eu-south-2`
- **Stack Name**: `triage-api`

To modify these, edit the variables at the top of each script.

## Troubleshooting

### Permission Denied

```bash
chmod +x scripts/*.sh
```

### AWS CLI Not Found

```bash
# macOS
brew install awscli

# Linux
pip install awscli
```

### SAM CLI Not Found

```bash
uv pip install aws-sam-cli
```

### Invalid Credentials

```bash
aws configure --profile stratecode
```

### Secret Not Found

Ensure you've run `setup-secrets.sh` before generating tokens or deploying.

## Security Notes

- Never commit `.env` files
- Store JWT secrets securely
- Rotate tokens regularly
- Use least-privilege IAM policies
- Enable CloudTrail for audit logging

## Support

For detailed deployment documentation, see:
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/AWS_DEPLOYMENT.md`
- `docs/IAM_PERMISSIONS_GUIDE.md`
