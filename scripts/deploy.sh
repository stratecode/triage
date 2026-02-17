#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

# Configuration
PROFILE="stratecode"
REGION="eu-south-2"
STACK_NAME="triage-api"
ENVIRONMENT="${1:-dev}"

echo "🚀 Deploying TrIAge to AWS"
echo "Profile: $PROFILE"
echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo "❌ AWS SAM CLI not found. Installing..."
    uv pip install aws-sam-cli
fi

# Verify AWS credentials
echo "🔐 Verifying AWS credentials..."
aws sts get-caller-identity --profile $PROFILE --region $REGION > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ AWS credentials verification failed"
    exit 1
fi
echo "✅ AWS credentials verified"

# Package dependencies
echo "📦 Packaging Lambda dependencies..."
cd lambda
if [ -f "requirements.txt" ]; then
    uv pip install -r requirements.txt -t . --upgrade
fi
cd ..

# Copy triage package to lambda directory
echo "📋 Copying triage package..."
cp -r triage lambda/

# Build SAM application
echo "🔨 Building SAM application..."
sam build --profile $PROFILE --region $REGION

# Deploy
echo "🚀 Deploying to AWS..."

# Crear bucket S3 si no existe
BUCKET_NAME="triage-sam-artifacts-${ENVIRONMENT}-$(aws sts get-caller-identity --profile $PROFILE --query 'Account' --output text)"
echo "📦 Verificando bucket S3: $BUCKET_NAME"

if ! aws s3 ls "s3://${BUCKET_NAME}" --profile $PROFILE --region $REGION 2>/dev/null; then
    echo "   Creando bucket..."
    aws s3 mb "s3://${BUCKET_NAME}" --profile $PROFILE --region $REGION
    echo "✅ Bucket creado"
else
    echo "✅ Bucket ya existe"
fi

sam deploy \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --parameter-overrides Environment=$ENVIRONMENT \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset \
    --s3-bucket $BUCKET_NAME \
    --s3-prefix triage-api

# Get API URL
echo ""
echo "✅ Deployment complete!"
echo ""
API_URL=$(aws cloudformation describe-stacks \
    --profile $PROFILE \
    --region $REGION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

echo "🌐 API URL: $API_URL"
echo ""
echo "Next steps:"
echo "1. Configure secrets: ./scripts/setup-secrets.sh $ENVIRONMENT"
echo "2. Generate JWT token: ./scripts/generate-token.sh"
echo "3. Test API: ./scripts/test-api.sh $API_URL"
