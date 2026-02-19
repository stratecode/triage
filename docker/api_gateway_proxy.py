# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
API Gateway Proxy for LocalStack
Forwards requests to LocalStack API Gateway with proper URL formatting
"""

import os
import sys
import logging
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/api-gateway-proxy.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TrIAge API Gateway Proxy",
    description="Proxy to LocalStack API Gateway",
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

# Read API Gateway ID from file (created by deploy script)
def get_api_gateway_url():
    """Get the LocalStack API Gateway URL."""
    import time
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            with open('/tmp/api_gateway_id.txt', 'r') as f:
                api_id = f.read().strip()
                if api_id:
                    logger.info(f"Found API Gateway ID: {api_id}")
                    return f"http://localstack:4566/restapis/{api_id}/local/_user_request_"
        except FileNotFoundError:
            if retry_count == 0:
                logger.info("Waiting for API Gateway ID file to be created by localstack-init...")
            retry_count += 1
            time.sleep(1)
    
    logger.error("API Gateway ID file not found after 30 seconds. LocalStack may not be initialized.")
    return None

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    """Proxy all requests to LocalStack API Gateway."""
    
    base_url = get_api_gateway_url()
    if not base_url:
        return Response(
            content='{"error": "API Gateway not initialized. Please wait for LocalStack to start."}',
            status_code=503,
            media_type="application/json"
        )
    
    # Build target URL
    target_url = f"{base_url}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"
    
    logger.info(f"Proxying {request.method} {path} -> {target_url}")
    
    # Forward request to LocalStack
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            # Get request body
            body = await request.body()
            
            # Forward headers (exclude host)
            headers = dict(request.headers)
            headers.pop('host', None)
            
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body
            )
            
            # Return response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get('content-type', 'application/json')
            )
            
        except httpx.RequestError as e:
            logger.error(f"Error proxying request: {e}")
            return Response(
                content=f'{{"error": "Failed to connect to API Gateway: {str(e)}"}}',
                status_code=502,
                media_type="application/json"
            )

@app.get("/health")
async def health():
    """Health check endpoint."""
    base_url = get_api_gateway_url()
    
    # During startup, it's OK if API Gateway isn't ready yet
    if not base_url:
        return {
            "status": "starting",
            "message": "Waiting for LocalStack initialization",
            "api_gateway_url": None
        }
    
    return {
        "status": "healthy",
        "api_gateway_url": base_url
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
