# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

import json
import os
import jwt
import boto3
from typing import Dict, Any

secrets_client = boto3.client('secretsmanager')

def get_jwt_secret() -> str:
    """Retrieve JWT secret from Secrets Manager."""
    secret_name = os.environ['JWT_SECRET_NAME']
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret['jwt_secret']
    except Exception as e:
        print(f"Error retrieving JWT secret: {e}")
        raise

def generate_policy(principal_id: str, effect: str, resource: str) -> Dict[str, Any]:
    """Generate IAM policy for API Gateway."""
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda authorizer for JWT token validation.
    
    Expected header: Authorization: Bearer <token>
    """
    try:
        # Extract token from Authorization header
        token = event['headers'].get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            print("No token provided")
            raise Exception('Unauthorized')
        
        # Get JWT secret
        secret = get_jwt_secret()
        
        # Verify and decode token
        try:
            decoded = jwt.decode(token, secret, algorithms=['HS256'])
            print(f"Token validated for user: {decoded.get('sub', 'unknown')}")
            
            # Generate allow policy
            return generate_policy(
                principal_id=decoded.get('sub', 'user'),
                effect='Allow',
                resource=event['methodArn']
            )
            
        except jwt.ExpiredSignatureError:
            print("Token expired")
            raise Exception('Unauthorized: Token expired')
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {e}")
            raise Exception('Unauthorized: Invalid token')
            
    except Exception as e:
        print(f"Authorization failed: {e}")
        raise Exception('Unauthorized')
