#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

PROFILE="stratecode"
REGION="eu-south-2"
ENVIRONMENT="${1:-dev}"
USER_ID="${2:-admin}"
EXPIRY_DAYS="${3:-30}"

echo "🔑 Generating JWT token"
echo "Environment: $ENVIRONMENT"
echo "User: $USER_ID"
echo "Expiry: $EXPIRY_DAYS days"
echo ""

# Get JWT secret from AWS Secrets Manager
JWT_SECRET_NAME="/${ENVIRONMENT}/triage/jwt-secret"
JWT_SECRET=$(aws secretsmanager get-secret-value \
    --profile $PROFILE \
    --region $REGION \
    --secret-id "$JWT_SECRET_NAME" \
    --query 'SecretString' \
    --output text | jq -r '.jwt_secret')

if [ -z "$JWT_SECRET" ]; then
    echo "❌ Failed to retrieve JWT secret"
    exit 1
fi

# Generate token using Python
python3 - <<EOF
import jwt
from datetime import datetime, timezone, timedelta

secret = "$JWT_SECRET"
user_id = "$USER_ID"
expiry_days = int("$EXPIRY_DAYS")

payload = {
    'sub': user_id,
    'iat': datetime.now(timezone.utc),
    'exp': datetime.now(timezone.utc) + timedelta(days=expiry_days)
}

token = jwt.encode(payload, secret, algorithm='HS256')
print(f"\n✅ JWT Token generated successfully!\n")
print(f"Token: {token}\n")
print(f"Valid until: {payload['exp'].isoformat()}\n")
print(f"Usage: Authorization: Bearer {token}\n")
EOF
