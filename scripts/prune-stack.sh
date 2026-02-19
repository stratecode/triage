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
CUSTOM_DOMAIN="triage-api.stratecode.com"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
    echo "Usage: $0 [dev|staging|prod]"
    exit 1
fi

FULL_STACK_NAME="${STACK_NAME}-${ENVIRONMENT}"

echo -e "${RED}========================================${NC}"
echo -e "${RED}🧹 PRUNING STACK: $FULL_STACK_NAME${NC}"
echo -e "${RED}========================================${NC}"
echo -e "${YELLOW}⚠️  WARNING: This will forcefully delete ALL resources${NC}"
echo -e "${YELLOW}⚠️  This action is IRREVERSIBLE${NC}"
echo ""
echo "Profile: $PROFILE"
echo "Region: $REGION"
echo "Stack: $FULL_STACK_NAME"
echo ""

# Confirmation
read -p "Are you sure you want to prune this stack? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${BLUE}Starting aggressive cleanup...${NC}"
echo ""

# Function to safely run commands
safe_run() {
    "$@" 2>/dev/null || true
}

# Step 1: Delete all base path mappings from custom domain
echo -e "${BLUE}[1/8] Cleaning custom domain base path mappings...${NC}"
MAPPINGS=$(safe_run aws apigateway get-base-path-mappings \
    --domain-name $CUSTOM_DOMAIN \
    --profile $PROFILE \
    --region $REGION \
    --query 'items[].basePath' \
    --output text)

if [ -n "$MAPPINGS" ]; then
    for BASE_PATH in $MAPPINGS; do
        echo "   Deleting base path: $BASE_PATH"
        safe_run aws apigateway delete-base-path-mapping \
            --domain-name $CUSTOM_DOMAIN \
            --base-path "$BASE_PATH" \
            --profile $PROFILE \
            --region $REGION
    done
    echo -e "${GREEN}   ✓ Base path mappings deleted${NC}"
else
    echo "   No base path mappings found"
fi

# Step 2: Get API Gateway ID from stack
echo -e "${BLUE}[2/8] Getting API Gateway ID...${NC}"
API_ID=$(safe_run aws cloudformation describe-stack-resources \
    --stack-name $FULL_STACK_NAME \
    --logical-resource-id TriageApi \
    --profile $PROFILE \
    --region $REGION \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text)

if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
    echo "   Found API: $API_ID"
    
    # Delete all stages
    echo -e "${BLUE}[3/8] Deleting API Gateway stages...${NC}"
    STAGES=$(safe_run aws apigateway get-stages \
        --rest-api-id $API_ID \
        --profile $PROFILE \
        --region $REGION \
        --query 'item[].stageName' \
        --output text)
    
    if [ -n "$STAGES" ]; then
        for STAGE in $STAGES; do
            echo "   Deleting stage: $STAGE"
            safe_run aws apigateway delete-stage \
                --rest-api-id $API_ID \
                --stage-name $STAGE \
                --profile $PROFILE \
                --region $REGION
        done
        echo -e "${GREEN}   ✓ Stages deleted${NC}"
    else
        echo "   No stages found"
    fi
else
    echo "   No API Gateway found"
    echo -e "${BLUE}[3/8] Skipping API Gateway stages...${NC}"
fi

# Step 4: Delete all event source mappings for Lambda functions
echo -e "${BLUE}[4/8] Deleting Lambda event source mappings...${NC}"
FUNCTIONS=$(safe_run aws cloudformation describe-stack-resources \
    --stack-name $FULL_STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query "StackResources[?ResourceType=='AWS::Lambda::Function'].PhysicalResourceId" \
    --output text)

if [ -n "$FUNCTIONS" ]; then
    for FUNCTION_ARN in $FUNCTIONS; do
        echo "   Checking function: $FUNCTION_ARN"
        MAPPINGS=$(safe_run aws lambda list-event-source-mappings \
            --function-name "$FUNCTION_ARN" \
            --profile $PROFILE \
            --region $REGION \
            --query 'EventSourceMappings[].UUID' \
            --output text)
        
        if [ -n "$MAPPINGS" ]; then
            for UUID in $MAPPINGS; do
                echo "   Deleting mapping: $UUID"
                safe_run aws lambda delete-event-source-mapping \
                    --uuid $UUID \
                    --profile $PROFILE \
                    --region $REGION
            done
        fi
    done
    echo -e "${GREEN}   ✓ Event source mappings deleted${NC}"
else
    echo "   No Lambda functions found"
fi

# Step 5: Delete all Lambda functions directly (bypass CloudFormation)
echo -e "${BLUE}[5/8] Force deleting Lambda functions...${NC}"
if [ -n "$FUNCTIONS" ]; then
    for FUNCTION_ARN in $FUNCTIONS; do
        FUNCTION_NAME=$(echo $FUNCTION_ARN | awk -F: '{print $NF}')
        echo "   Deleting function: $FUNCTION_NAME"
        safe_run aws lambda delete-function \
            --function-name "$FUNCTION_NAME" \
            --profile $PROFILE \
            --region $REGION
    done
    echo -e "${GREEN}   ✓ Lambda functions deleted${NC}"
else
    echo "   No Lambda functions to delete"
fi

# Step 6: Delete CloudWatch Log Groups
echo -e "${BLUE}[6/8] Deleting CloudWatch Log Groups...${NC}"
LOG_GROUPS=$(safe_run aws logs describe-log-groups \
    --profile $PROFILE \
    --region $REGION \
    --log-group-name-prefix "/aws/lambda/${FULL_STACK_NAME}" \
    --query 'logGroups[].logGroupName' \
    --output text)

if [ -n "$LOG_GROUPS" ]; then
    for LOG_GROUP in $LOG_GROUPS; do
        echo "   Deleting log group: $LOG_GROUP"
        safe_run aws logs delete-log-group \
            --log-group-name "$LOG_GROUP" \
            --profile $PROFILE \
            --region $REGION
    done
    echo -e "${GREEN}   ✓ Log groups deleted${NC}"
else
    echo "   No log groups found"
fi

# Step 7: Delete the CloudFormation stack (with retries)
echo -e "${BLUE}[7/8] Deleting CloudFormation stack...${NC}"

STACK_EXISTS=$(safe_run aws cloudformation describe-stacks \
    --stack-name $FULL_STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].StackName' \
    --output text)

if [ -n "$STACK_EXISTS" ] && [ "$STACK_EXISTS" != "None" ]; then
    echo "   Initiating stack deletion..."
    safe_run aws cloudformation delete-stack \
        --stack-name $FULL_STACK_NAME \
        --profile $PROFILE \
        --region $REGION
    
    echo "   Waiting for stack deletion (max 5 minutes)..."
    WAIT_COUNT=0
    MAX_WAIT=60
    
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        STACK_STATUS=$(safe_run aws cloudformation describe-stacks \
            --stack-name $FULL_STACK_NAME \
            --profile $PROFILE \
            --region $REGION \
            --query 'Stacks[0].StackStatus' \
            --output text)
        
        if [ -z "$STACK_STATUS" ] || [ "$STACK_STATUS" = "None" ]; then
            echo ""
            echo -e "${GREEN}   ✓ Stack deleted successfully${NC}"
            break
        elif [ "$STACK_STATUS" = "DELETE_COMPLETE" ]; then
            echo ""
            echo -e "${GREEN}   ✓ Stack deleted successfully${NC}"
            break
        elif [ "$STACK_STATUS" = "DELETE_FAILED" ]; then
            echo ""
            echo -e "${YELLOW}   ⚠️  Stack deletion failed, but continuing...${NC}"
            
            # Try to delete with retain option via AWS CLI trick
            echo "   Attempting force delete via console method..."
            echo ""
            echo -e "${YELLOW}   Manual action required:${NC}"
            echo "   1. Go to: https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks"
            echo "   2. Select: $FULL_STACK_NAME"
            echo "   3. Click 'Delete' and check: ☑ Retain resources that cannot be deleted"
            echo "   4. Confirm deletion"
            echo ""
            echo "   Press Enter when done (or Ctrl+C to abort)..."
            read
            break
        fi
        
        echo -n "."
        sleep 5
        WAIT_COUNT=$((WAIT_COUNT + 1))
    done
    
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo ""
        echo -e "${YELLOW}   ⚠️  Stack deletion timeout, but may still be in progress${NC}"
    fi
else
    echo "   Stack does not exist"
fi

# Step 8: Final verification
echo -e "${BLUE}[8/8] Verifying cleanup...${NC}"

FINAL_CHECK=$(safe_run aws cloudformation describe-stacks \
    --stack-name $FULL_STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].StackStatus' \
    --output text)

if [ -z "$FINAL_CHECK" ] || [ "$FINAL_CHECK" = "None" ]; then
    echo -e "${GREEN}   ✓ Stack completely removed${NC}"
else
    echo -e "${YELLOW}   ⚠️  Stack still exists with status: $FINAL_CHECK${NC}"
    echo "   You may need to manually delete it from the console"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Prune complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Run: make deploy-dev"
echo "  2. Test: curl https://${CUSTOM_DOMAIN}/api/v1/health"
echo ""
