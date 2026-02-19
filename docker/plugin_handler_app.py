# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Handler ASGI Application

Wraps the Lambda handler for local development with uvicorn.
Provides HTTP endpoints for plugin webhooks and OAuth callbacks.
"""

import json
import os
import sys
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse

# Import Lambda handler using importlib to avoid 'lambda' keyword issue
import importlib
plugin_handler_module = importlib.import_module('lambda.plugin_handler')
lambda_handler = plugin_handler_module.handler


async def convert_request_to_lambda_event(request: Request) -> Dict[str, Any]:
    """
    Convert Starlette request to Lambda API Gateway event format.
    
    Args:
        request: Starlette request
        
    Returns:
        Lambda event dict
    """
    # Get body
    body = await request.body()
    body_str = body.decode('utf-8') if body else ''
    
    # Build event
    event = {
        'path': request.url.path,
        'httpMethod': request.method,
        'headers': dict(request.headers),
        'queryStringParameters': dict(request.query_params) if request.query_params else None,
        'body': body_str,
        'isBase64Encoded': False,
        'requestContext': {
            'requestId': request.headers.get('x-request-id', 'local-dev'),
            'identity': {
                'sourceIp': request.client.host if request.client else 'unknown'
            }
        }
    }
    
    return event


class MockLambdaContext:
    """Mock Lambda context for local development."""
    
    def __init__(self, request_id: str = 'local-dev'):
        self.request_id = request_id
        self.function_name = 'plugin-handler-local'
        self.function_version = '$LATEST'
        self.invoked_function_arn = 'arn:aws:lambda:local:000000000000:function:plugin-handler-local'
        self.memory_limit_in_mb = 512
        self.aws_request_id = request_id


async def handle_request(request: Request) -> JSONResponse | HTMLResponse:
    """
    Handle incoming HTTP request by converting to Lambda event.
    
    Args:
        request: Starlette request
        
    Returns:
        Starlette response
    """
    # Convert to Lambda event
    event = await convert_request_to_lambda_event(request)
    context = MockLambdaContext(
        request_id=request.headers.get('x-request-id', 'local-dev')
    )
    
    # Invoke Lambda handler
    lambda_response = lambda_handler(event, context)
    
    # Convert Lambda response to Starlette response
    status_code = lambda_response.get('statusCode', 200)
    headers = lambda_response.get('headers', {})
    body = lambda_response.get('body', '')
    
    # Determine response type
    content_type = headers.get('Content-Type', 'application/json')
    
    if 'text/html' in content_type:
        return HTMLResponse(
            content=body,
            status_code=status_code,
            headers=headers
        )
    else:
        # Parse JSON body if it's a string
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass
        
        return JSONResponse(
            content=body,
            status_code=status_code,
            headers=headers
        )


# Define routes
routes = [
    Route('/plugins/slack/webhook', handle_request, methods=['POST']),
    Route('/plugins/slack/oauth/callback', handle_request, methods=['GET']),
    Route('/plugins/health', handle_request, methods=['GET']),
]

# Create ASGI app
app = Starlette(debug=True, routes=routes)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8001, log_level='debug')
