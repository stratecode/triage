#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROFILE="${AWS_PROFILE:-stratecode}"
REGION="${AWS_REGION:-eu-south-2}"
STACK_NAME="triage-api"
ENVIRONMENT="${1:-dev}"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
    echo "Usage: $0 [dev|staging|prod]"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Deploying TrIAge to AWS${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Profile: $PROFILE"
echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo "Stack: ${STACK_NAME}-${ENVIRONMENT}"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    echo "Install: brew install awscli"
    exit 1
fi

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo -e "${YELLOW}⚠️  AWS SAM CLI not found. Installing...${NC}"
    uv pip install aws-sam-cli
fi

# Verify AWS credentials
echo -e "${BLUE}🔐 Verifying AWS credentials...${NC}"
if ! aws sts get-caller-identity --profile $PROFILE --region $REGION > /dev/null 2>&1; then
    echo -e "${RED}❌ AWS credentials verification failed${NC}"
    echo "Please configure AWS credentials:"
    echo "  aws configure --profile $PROFILE"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --profile $PROFILE --query 'Account' --output text)
echo -e "${GREEN}✅ AWS credentials verified (Account: $ACCOUNT_ID)${NC}"

# Check if stack already exists and its status
echo -e "${BLUE}🔍 Checking existing stack...${NC}"
STACK_STATUS=$(aws cloudformation describe-stacks \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" = "DOES_NOT_EXIST" ]; then
    echo -e "${GREEN}✅ New stack will be created${NC}"
    STACK_EXISTS=false
elif [ "$STACK_STATUS" = "DELETE_FAILED" ] || [ "$STACK_STATUS" = "ROLLBACK_FAILED" ] || [ "$STACK_STATUS" = "CREATE_FAILED" ]; then
    echo -e "${RED}❌ Stack is in a failed state: $STACK_STATUS${NC}"
    echo ""
    echo "The stack must be cleaned up before deploying."
    echo "Run: make prune-${ENVIRONMENT}"
    echo ""
    exit 1
else
    echo -e "${YELLOW}⚠️  Stack already exists (Status: $STACK_STATUS). This will update the existing stack.${NC}"
    STACK_EXISTS=true
fi

# Build SAM application
echo ""
echo -e "${BLUE}🔨 Building SAM application...${NC}"
if ! sam build --profile $PROFILE --region $REGION; then
    echo -e "${RED}❌ SAM build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Build complete${NC}"

# Create/verify S3 bucket for artifacts
BUCKET_NAME="triage-sam-artifacts-${ENVIRONMENT}-${ACCOUNT_ID}"
echo ""
echo -e "${BLUE}📦 Verifying S3 bucket: $BUCKET_NAME${NC}"

if ! aws s3 ls "s3://${BUCKET_NAME}" --profile $PROFILE --region $REGION 2>/dev/null; then
    echo "   Creating bucket..."
    if aws s3 mb "s3://${BUCKET_NAME}" --profile $PROFILE --region $REGION; then
        echo -e "${GREEN}✅ Bucket created${NC}"
    else
        echo -e "${RED}❌ Failed to create bucket${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Bucket already exists${NC}"
fi

# Deploy
echo ""
echo -e "${BLUE}🚀 Deploying to AWS...${NC}"
echo "This may take several minutes..."
echo ""

if sam deploy \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset \
    --s3-bucket $BUCKET_NAME \
    --s3-prefix triage-api \
    --no-confirm-changeset; then
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}❌ Deployment failed${NC}"
    echo "Check CloudFormation console for details:"
    echo "https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks"
    exit 1
fi

# Get stack outputs
echo ""
echo -e "${BLUE}📋 Stack Outputs:${NC}"
echo ""

API_URL=$(aws cloudformation describe-stacks \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text 2>/dev/null || echo "N/A")

SLACK_WEBHOOK=$(aws cloudformation describe-stacks \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].Outputs[?OutputKey==`SlackWebhookUrl`].OutputValue' \
    --output text 2>/dev/null || echo "N/A")

SLACK_OAUTH=$(aws cloudformation describe-stacks \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].Outputs[?OutputKey==`SlackOAuthCallbackUrl`].OutputValue' \
    --output text 2>/dev/null || echo "N/A")

echo "🌐 API URL: $API_URL"
echo "🔗 Slack Webhook: $SLACK_WEBHOOK"
echo "🔗 Slack OAuth Callback: $SLACK_OAUTH"

# Check if secrets are configured
echo ""
echo -e "${BLUE}🔐 Checking secrets configuration...${NC}"

JIRA_SECRET_EXISTS=false
JWT_SECRET_EXISTS=false

if aws secretsmanager describe-secret \
    --profile $PROFILE \
    --region $REGION \
    --secret-id "/${ENVIRONMENT}/triage/jira-credentials" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ JIRA credentials configured${NC}"
    JIRA_SECRET_EXISTS=true
else
    echo -e "${YELLOW}⚠️  JIRA credentials not configured${NC}"
fi

if aws secretsmanager describe-secret \
    --profile $PROFILE \
    --region $REGION \
    --secret-id "/${ENVIRONMENT}/triage/jwt-secret" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ JWT secret configured${NC}"
    JWT_SECRET_EXISTS=true
else
    echo -e "${YELLOW}⚠️  JWT secret not configured${NC}"
fi

# Next steps
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}📝 Next Steps:${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ "$JIRA_SECRET_EXISTS" = false ] || [ "$JWT_SECRET_EXISTS" = false ]; then
    echo "1. Configure secrets:"
    echo -e "   ${YELLOW}./scripts/setup-secrets.sh $ENVIRONMENT${NC}"
    echo ""
fi

echo "2. Generate JWT token:"
echo -e "   ${YELLOW}python scripts/generate-jwt-token.py${NC}"
echo ""

echo "3. Test API:"
echo -e "   ${YELLOW}curl $API_URL/api/v1/health${NC}"
echo ""

if [ "$SLACK_WEBHOOK" != "N/A" ]; then
    echo "4. Configure Slack App:"
    echo "   - Event Subscriptions URL: $SLACK_WEBHOOK"
    echo "   - OAuth Redirect URL: $SLACK_OAUTH"
    echo "   - Slash Command URL: $SLACK_WEBHOOK"
    echo ""
fi

echo "5. View logs:"
echo -e "   ${YELLOW}make aws-logs${NC}"
echo ""

echo "6. Monitor stack:"
echo "   https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks"
echo ""

echo -e "${GREEN}🎉 Deployment successful!${NC}"
