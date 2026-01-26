# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
API server for TrIAge notification webhooks.

This module provides HTTP endpoints that the TrIAge API can call to trigger
Slack notifications. It uses aiohttp for async HTTP handling.

Validates: Requirements 2.1, 5.1
"""

import json
from typing import Optional
from aiohttp import web

from slack_bot.notification_handler import NotificationHandler
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


class NotificationAPI:
    """
    HTTP API server for TrIAge notification webhooks.
    
    Provides endpoints:
    - POST /api/v1/notifications/slack/plan - Daily plan delivery
    - POST /api/v1/notifications/slack/blocking-task - Blocking task alerts
    - POST /api/v1/notifications/slack/blocking-task-resolved - Resolution notifications
    
    Validates: Requirements 2.1, 5.1, 5.5
    """
    
    def __init__(self, notification_handler: NotificationHandler):
        """
        Initialize notification API.
        
        Args:
            notification_handler: NotificationHandler instance for processing requests
        """
        self.notification_handler = notification_handler
        self.app = web.Application()
        self._setup_routes()
        
        logger.info("Notification API initialized")
    
    def _setup_routes(self) -> None:
        """Configure API routes."""
        self.app.router.add_post(
            '/api/v1/notifications/slack/plan',
            self.handle_plan_notification
        )
        self.app.router.add_post(
            '/api/v1/notifications/slack/blocking-task',
            self.handle_blocking_task_notification
        )
        self.app.router.add_post(
            '/api/v1/notifications/slack/blocking-task-resolved',
            self.handle_blocking_task_resolved_notification
        )
        
        # Health check endpoint
        self.app.router.add_get('/health', self.health_check)
        
        logger.info("API routes configured")
    
    async def handle_plan_notification(self, request: web.Request) -> web.Response:
        """
        Handle daily plan notification webhook.
        
        Endpoint: POST /api/v1/notifications/slack/plan
        
        Args:
            request: aiohttp Request object
            
        Returns:
            JSON response with delivery status
            
        Validates: Requirements 2.1
        """
        try:
            # Parse request body
            request_data = await request.json()
            
            # Extract headers for signature validation
            headers = dict(request.headers)
            
            # Process notification
            response = await self.notification_handler.handle_plan_notification(
                request_data=request_data,
                headers=headers
            )
            
            # Return response
            status_code = 200 if response.success else 400
            return web.json_response(
                data=response.model_dump(),
                status=status_code
            )
            
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in plan notification request", extra={
                'error': str(e)
            })
            return web.json_response(
                data={'success': False, 'message': 'Invalid JSON', 'error': 'invalid_json'},
                status=400
            )
        
        except Exception as e:
            logger.error("Unexpected error in plan notification handler", extra={
                'error': str(e)
            })
            return web.json_response(
                data={'success': False, 'message': str(e), 'error': 'unexpected_error'},
                status=500
            )
    
    async def handle_blocking_task_notification(self, request: web.Request) -> web.Response:
        """
        Handle blocking task notification webhook.
        
        Endpoint: POST /api/v1/notifications/slack/blocking-task
        
        Args:
            request: aiohttp Request object
            
        Returns:
            JSON response with delivery status
            
        Validates: Requirements 5.1
        """
        try:
            # Parse request body
            request_data = await request.json()
            
            # Extract headers for signature validation
            headers = dict(request.headers)
            
            # Process notification
            response = await self.notification_handler.handle_blocking_task_notification(
                request_data=request_data,
                headers=headers
            )
            
            # Return response
            status_code = 200 if response.success else 400
            return web.json_response(
                data=response.model_dump(),
                status=status_code
            )
            
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in blocking task notification request", extra={
                'error': str(e)
            })
            return web.json_response(
                data={'success': False, 'message': 'Invalid JSON', 'error': 'invalid_json'},
                status=400
            )
        
        except Exception as e:
            logger.error("Unexpected error in blocking task notification handler", extra={
                'error': str(e)
            })
            return web.json_response(
                data={'success': False, 'message': str(e), 'error': 'unexpected_error'},
                status=500
            )
    
    async def handle_blocking_task_resolved_notification(
        self,
        request: web.Request
    ) -> web.Response:
        """
        Handle blocking task resolution notification webhook.
        
        Endpoint: POST /api/v1/notifications/slack/blocking-task-resolved
        
        Args:
            request: aiohttp Request object
            
        Returns:
            JSON response with delivery status
            
        Validates: Requirements 5.5
        """
        try:
            # Parse request body
            request_data = await request.json()
            
            # Extract headers for signature validation
            headers = dict(request.headers)
            
            # Process notification
            response = await self.notification_handler.handle_blocking_task_resolved_notification(
                request_data=request_data,
                headers=headers
            )
            
            # Return response
            status_code = 200 if response.success else 400
            return web.json_response(
                data=response.model_dump(),
                status=status_code
            )
            
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in resolution notification request", extra={
                'error': str(e)
            })
            return web.json_response(
                data={'success': False, 'message': 'Invalid JSON', 'error': 'invalid_json'},
                status=400
            )
        
        except Exception as e:
            logger.error("Unexpected error in resolution notification handler", extra={
                'error': str(e)
            })
            return web.json_response(
                data={'success': False, 'message': str(e), 'error': 'unexpected_error'},
                status=500
            )
    
    async def health_check(self, request: web.Request) -> web.Response:
        """
        Health check endpoint.
        
        Returns:
            JSON response with service status
        """
        return web.json_response(
            data={'status': 'healthy', 'service': 'slack-bot-api'},
            status=200
        )
    
    def run(self, host: str = '0.0.0.0', port: int = 8080) -> None:
        """
        Run the API server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        logger.info("Starting notification API server", extra={
            'host': host,
            'port': port
        })
        web.run_app(self.app, host=host, port=port)
