#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

PROFILE="stratecode"
REGION="eu-south-2"
ENVIRONMENT="${1:-dev}"

echo "🔐 Setting up AWS Secrets Manager"
echo "Environment: $ENVIRONMENT"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create it from .env.example"
    exit 1
fi

# Load .env
source .env

# Validate required variables
if [ -z "$JIRA_BASE_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo "❌ Missing required JIRA credentials in .env"
    exit 1
fi

# Create JIRA credentials secret
echo "📝 Creating JIRA credentials secret..."
JIRA_SECRET_NAME="/${ENVIRONMENT}/triage/jira-credentials"

aws secretsmanager create-secret \
    --profile $PROFILE \
    --region $REGION \
    --name "$JIRA_SECRET_NAME" \
    --description "JIRA credentials for TrIAge" \
    --secret-string "{\"jira_base_url\":\"$JIRA_BASE_URL\",\"jira_email\":\"$JIRA_EMAIL\",\"jira_api_token\":\"$JIRA_API_TOKEN\"}" \
    2>/dev/null || \
aws secretsmanager update-secret \
    --profile $PROFILE \
    --region $REGION \
    --secret-id "$JIRA_SECRET_NAME" \
    --secret-string "{\"jira_base_url\":\"$JIRA_BASE_URL\",\"jira_email\":\"$JIRA_EMAIL\",\"jira_api_token\":\"$JIRA_API_TOKEN\"}"

echo "✅ JIRA credentials stored"

# Create JWT secret
echo "📝 Creating JWT secret..."
JWT_SECRET=$(openssl rand -base64 32)
JWT_SECRET_NAME="/${ENVIRONMENT}/triage/jwt-secret"

aws secretsmanager create-secret \
    --profile $PROFILE \
    --region $REGION \
    --name "$JWT_SECRET_NAME" \
    --description "JWT secret for TrIAge API authentication" \
    --secret-string "{\"jwt_secret\":\"$JWT_SECRET\"}" \
    2>/dev/null || \
aws secretsmanager update-secret \
    --profile $PROFILE \
    --region $REGION \
    --secret-id "$JWT_SECRET_NAME" \
    --secret-string "{\"jwt_secret\":\"$JWT_SECRET\"}"

echo "✅ JWT secret stored"
echo ""
echo "🔑 JWT Secret (save this securely): $JWT_SECRET"
echo ""
echo "✅ All secrets configured successfully!"
