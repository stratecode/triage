# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Local FastAPI server that simulates AWS API Gateway + Lambda.
Replicates the AWS stack for local debugging.
"""

import os
import sys
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import jwt

# Add lambda directory to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/lambda')

# Import Lambda handlers (avoid using 'lambda' directly as it's a reserved keyword)
import handlers as lambda_handlers

# Configure logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/api.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TrIAge API (Local)",
    description="Local replica of AWS serverless stack",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class GeneratePlanRequest(BaseModel):
    date: Optional[str] = None
    closure_rate: Optional[float] = None

class ApprovePlanRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None

class DecomposeTaskRequest(BaseModel):
    target_days: int = 1

# JWT Authentication (simulates Lambda Authorizer)
def get_jwt_secret() -> str:
    """Get JWT secret from environment (simulates Secrets Manager)."""
    return os.environ.get('JWT_SECRET', 'dev-secret-change-in-production')

def verify_token(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Verify JWT token (simulates Lambda Authorizer)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    try:
        token = authorization.replace("Bearer ", "")
        secret = get_jwt_secret()
        decoded = jwt.decode(token, secret, algorithms=['HS256'])
        logger.info(f"Token validated for user: {decoded.get('sub', 'unknown')}")
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

# Simulate Lambda context
class MockLambdaContext:
    def __init__(self):
        self.function_name = "local-function"
        self.memory_limit_in_mb = 512
        self.invoked_function_arn = "arn:aws:lambda:local:000000000000:function:local"
        self.aws_request_id = "local-request-id"

def create_lambda_event(request: Request, path_params: Dict = None, body: Any = None) -> Dict:
    """Create Lambda event from FastAPI request."""
    return {
        'httpMethod': request.method,
        'path': request.url.path,
        'pathParameters': path_params or {},
        'headers': dict(request.headers),
        'body': body,
        'requestContext': {
            'requestId': 'local-request-id',
            'identity': {
                'sourceIp': request.client.host if request.client else 'unknown'
            }
        }
    }

def handle_lambda_response(lambda_response: Dict) -> JSONResponse:
    """Convert Lambda response to FastAPI response."""
    body = lambda_response.get('body', '{}')
    
    # Parse body if it's a string
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {}
    
    return JSONResponse(
        status_code=lambda_response.get('statusCode', 200),
        content=body,
        headers=lambda_response.get('headers', {})
    )

# Mock Secrets Manager for local development
class MockSecretsManager:
    @staticmethod
    def get_jira_credentials() -> Dict[str, str]:
        """Get JIRA credentials from environment."""
        return {
            'jira_base_url': os.environ.get('JIRA_BASE_URL', ''),
            'jira_email': os.environ.get('JIRA_EMAIL', ''),
            'jira_api_token': os.environ.get('JIRA_API_TOKEN', '')
        }

# Patch handlers to use mock secrets manager
lambda_handlers.get_jira_credentials = MockSecretsManager.get_jira_credentials

# API Endpoints

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    event = create_lambda_event(Request(scope={'type': 'http', 'method': 'GET', 'path': '/api/v1/health', 'headers': []}))
    context = MockLambdaContext()
    response = lambda_handlers.health_check(event, context)
    return handle_lambda_response(response)

@app.post("/api/v1/plan")
async def generate_plan(
    request: Request,
    body: GeneratePlanRequest,
    user: Dict = Depends(verify_token)
):
    """Generate daily plan."""
    logger.info(f"Generate plan request from user: {user.get('sub')}")
    
    event = create_lambda_event(
        request,
        body=body.model_dump_json()
    )
    context = MockLambdaContext()
    
    try:
        response = lambda_handlers.generate_plan(event, context)
        return handle_lambda_response(response)
    except Exception as e:
        logger.error(f"Error generating plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/plan/{date}")
async def get_plan(
    request: Request,
    date: str,
    user: Dict = Depends(verify_token)
):
    """Get plan for specific date."""
    logger.info(f"Get plan request for {date} from user: {user.get('sub')}")
    
    event = create_lambda_event(
        request,
        path_params={'date': date}
    )
    context = MockLambdaContext()
    
    try:
        response = lambda_handlers.get_plan(event, context)
        return handle_lambda_response(response)
    except Exception as e:
        logger.error(f"Error getting plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/plan/{date}/approve")
async def approve_plan(
    request: Request,
    date: str,
    body: ApprovePlanRequest,
    user: Dict = Depends(verify_token)
):
    """Approve or reject a plan."""
    logger.info(f"Approve plan request for {date} from user: {user.get('sub')}")
    
    event = create_lambda_event(
        request,
        path_params={'date': date},
        body=body.model_dump_json()
    )
    context = MockLambdaContext()
    
    try:
        response = lambda_handlers.approve_plan(event, context)
        return handle_lambda_response(response)
    except Exception as e:
        logger.error(f"Error approving plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/task/{taskId}/decompose")
async def decompose_task(
    request: Request,
    taskId: str,
    body: DecomposeTaskRequest,
    user: Dict = Depends(verify_token)
):
    """Decompose a long-running task."""
    logger.info(f"Decompose task request for {taskId} from user: {user.get('sub')}")
    
    event = create_lambda_event(
        request,
        path_params={'taskId': taskId},
        body=body.model_dump_json()
    )
    context = MockLambdaContext()
    
    try:
        response = lambda_handlers.decompose_task(event, context)
        return handle_lambda_response(response)
    except Exception as e:
        logger.error(f"Error decomposing task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Utility endpoint for generating tokens locally
@app.post("/api/v1/auth/token")
async def generate_token(user_id: str = "admin", expiry_days: int = 30):
    """Generate JWT token for local testing."""
    secret = get_jwt_secret()
    payload = {
        'sub': user_id,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=expiry_days)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    
    return {
        'token': token,
        'user_id': user_id,
        'expires_in_days': expiry_days
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
