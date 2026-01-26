# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Notification handler for TrIAge API webhook endpoints.

This module provides HTTP endpoints that the TrIAge API can call to trigger
Slack notifications for daily plans and blocking tasks. It validates incoming
requests and routes them to the notification delivery service.

Validates: Requirements 2.1
"""

import hmac
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, date

from pydantic import BaseModel, Field, ValidationError

from slack_bot.notification_service import NotificationDeliveryService, NotificationDeliveryError
from slack_bot.triage_api_client import TriageAPIClient
from slack_bot.logging_config import get_logger
from triage.models import DailyPlan, JiraIssue, TaskClassification, TaskCategory, AdminBlock


logger = get_logger(__name__)


class PlanNotificationRequest(BaseModel):
    """Request model for plan notification webhook."""
    user_id: str = Field(..., description="TrIAge user ID")
    team_id: str = Field(..., description="Slack team/workspace ID")
    plan: Dict[str, Any] = Field(..., description="Daily plan data")
    plan_id: str = Field(..., description="Unique plan identifier")


class BlockingTaskNotificationRequest(BaseModel):
    """Request model for blocking task notification webhook."""
    user_id: str = Field(..., description="TrIAge user ID")
    team_id: str = Field(..., description="Slack team/workspace ID")
    task: Dict[str, Any] = Field(..., description="Blocking task data")
    blocker_reason: str = Field(..., description="Reason task is blocking")
    additional_tasks: Optional[list[Dict[str, Any]]] = Field(
        default=None,
        description="Additional blocking tasks for grouping"
    )


class BlockingTaskResolvedNotificationRequest(BaseModel):
    """Request model for blocking task resolution notification webhook."""
    user_id: str = Field(..., description="TrIAge user ID")
    team_id: str = Field(..., description="Slack team/workspace ID")
    task: Dict[str, Any] = Field(..., description="Resolved blocking task data")


class NotificationResponse(BaseModel):
    """Response model for notification webhooks."""
    success: bool
    message: str
    delivered: bool = False
    message_ts: Optional[str] = None
    channel: Optional[str] = None
    error: Optional[str] = None


class NotificationHandler:
    """
    Handler for TrIAge API notification webhooks.
    
    This class provides HTTP endpoint handlers that the TrIAge API can call
    to trigger Slack notifications. It validates requests, looks up user
    configuration, and routes to the notification delivery service.
    
    Validates: Requirements 2.1
    """
    
    def __init__(
        self,
        notification_service: NotificationDeliveryService,
        triage_api_client: TriageAPIClient,
        webhook_secret: Optional[str] = None
    ):
        """
        Initialize notification handler.
        
        Args:
            notification_service: NotificationDeliveryService for message delivery
            triage_api_client: TriageAPIClient for user config lookup
            webhook_secret: Optional shared secret for webhook validation
        """
        self.notification_service = notification_service
        self.triage_api_client = triage_api_client
        self.webhook_secret = webhook_secret
        
        logger.info("Notification handler initialized", extra={
            'has_webhook_secret': webhook_secret is not None
        })
    
    def validate_webhook_signature(
        self,
        body: bytes,
        signature: str,
        timestamp: str
    ) -> bool:
        """
        Validate webhook request signature.
        
        Args:
            body: Raw request body bytes
            signature: X-TrIAge-Signature header value
            timestamp: X-TrIAge-Timestamp header value
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            # No secret configured, skip validation
            logger.warning("Webhook secret not configured, skipping validation")
            return True
        
        try:
            # Compute expected signature
            sig_basestring = f"{timestamp}:".encode('utf-8') + body
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                sig_basestring,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning("Webhook signature mismatch", extra={
                    'provided_signature': signature[:20] + '...',
                    'timestamp': timestamp
                })
            
            return is_valid
            
        except Exception as e:
            logger.error("Webhook signature validation error", extra={
                'error': str(e),
                'timestamp': timestamp
            })
            return False
    
    async def handle_plan_notification(
        self,
        request_data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> NotificationResponse:
        """
        Handle daily plan notification webhook from TrIAge API.
        
        Endpoint: POST /api/v1/notifications/slack/plan
        
        Args:
            request_data: Request payload
            headers: Optional HTTP headers for signature validation
            
        Returns:
            NotificationResponse with delivery status
            
        Validates: Requirements 2.1
        """
        logger.info("Received plan notification request", extra={
            'user_id': request_data.get('user_id'),
            'team_id': request_data.get('team_id'),
            'plan_id': request_data.get('plan_id')
        })
        
        # Validate request signature if headers provided
        if headers and self.webhook_secret:
            signature = headers.get('X-TrIAge-Signature', '')
            timestamp = headers.get('X-TrIAge-Timestamp', '')
            
            if not signature or not timestamp:
                logger.warning("Missing signature headers")
                return NotificationResponse(
                    success=False,
                    message="Missing signature headers",
                    error="missing_signature"
                )
            
            import json
            body = json.dumps(request_data, sort_keys=True).encode('utf-8')
            
            if not self.validate_webhook_signature(body, signature, timestamp):
                logger.warning("Invalid webhook signature")
                return NotificationResponse(
                    success=False,
                    message="Invalid signature",
                    error="invalid_signature"
                )
        
        # Parse and validate request
        try:
            request = PlanNotificationRequest(**request_data)
        except ValidationError as e:
            logger.error("Invalid plan notification request", extra={
                'error': str(e),
                'request_data': request_data
            })
            return NotificationResponse(
                success=False,
                message=f"Invalid request: {str(e)}",
                error="validation_error"
            )
        
        # Parse plan data
        try:
            # Convert priority_tasks and admin_tasks to TaskClassification objects
            priorities = []
            for task_data in request.plan.get('priority_tasks', []):
                # Extract estimated_days before creating JiraIssue
                estimated_days = task_data.pop('estimated_days', 1.0) if isinstance(task_data, dict) else 1.0
                issue = JiraIssue(**task_data) if isinstance(task_data, dict) else task_data
                classification = TaskClassification(
                    task=issue,
                    category=TaskCategory.PRIORITY_ELIGIBLE,
                    is_priority_eligible=True,
                    has_dependencies=False,
                    estimated_days=estimated_days
                )
                priorities.append(classification)
            
            admin_tasks = []
            for task_data in request.plan.get('admin_tasks', []):
                # Extract estimated_days before creating JiraIssue
                estimated_days = task_data.pop('estimated_days', 0.125) if isinstance(task_data, dict) else 0.125
                issue = JiraIssue(**task_data) if isinstance(task_data, dict) else task_data
                classification = TaskClassification(
                    task=issue,
                    category=TaskCategory.ADMINISTRATIVE,
                    is_priority_eligible=False,
                    has_dependencies=False,
                    estimated_days=estimated_days
                )
                admin_tasks.append(classification)
            
            admin_block = AdminBlock(
                tasks=admin_tasks,
                time_allocation_minutes=sum(int(t.estimated_days * 8 * 60) for t in admin_tasks),
                scheduled_time="14:00-15:00"  # Default time
            )
            
            plan = DailyPlan(
                date=date.fromisoformat(request.plan['date']),
                priorities=priorities,
                admin_block=admin_block,
                other_tasks=[],
                previous_closure_rate=request.plan.get('previous_closure_rate')
            )
        except Exception as e:
            logger.error("Failed to parse plan data", extra={
                'error': str(e),
                'plan_id': request.plan_id
            })
            return NotificationResponse(
                success=False,
                message=f"Failed to parse plan: {str(e)}",
                error="parse_error"
            )
        
        # Get user mapping to find Slack user ID
        try:
            user_mapping = await self.triage_api_client.get_user_mapping(
                slack_user_id=request.user_id,  # This might need adjustment
                slack_team_id=request.team_id
            )
            slack_user_id = user_mapping.get('slack_user_id', request.user_id)
        except Exception as e:
            logger.warning("Failed to get user mapping, using provided user_id", extra={
                'user_id': request.user_id,
                'error': str(e)
            })
            slack_user_id = request.user_id
        
        # Get user configuration
        try:
            user_config = await self.triage_api_client.get_config(request.user_id)
        except Exception as e:
            logger.error("Failed to get user config", extra={
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Failed to get user config: {str(e)}",
                error="config_error"
            )
        
        # Deliver notification
        try:
            result = await self.notification_service.deliver_daily_plan(
                plan=plan,
                plan_id=request.plan_id,
                user_config=user_config,
                slack_user_id=slack_user_id
            )
            
            if result['delivered']:
                logger.info("Plan notification delivered successfully", extra={
                    'plan_id': request.plan_id,
                    'user_id': request.user_id,
                    'message_ts': result.get('message_ts')
                })
                
                return NotificationResponse(
                    success=True,
                    message="Plan notification delivered",
                    delivered=True,
                    message_ts=result.get('message_ts'),
                    channel=result.get('channel')
                )
            else:
                logger.info("Plan notification not delivered", extra={
                    'plan_id': request.plan_id,
                    'user_id': request.user_id,
                    'reason': result.get('reason')
                })
                
                return NotificationResponse(
                    success=True,
                    message=f"Notification not delivered: {result.get('reason')}",
                    delivered=False
                )
        
        except NotificationDeliveryError as e:
            logger.error("Failed to deliver plan notification", extra={
                'plan_id': request.plan_id,
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Delivery failed: {str(e)}",
                error="delivery_error"
            )
        
        except Exception as e:
            logger.error("Unexpected error delivering plan notification", extra={
                'plan_id': request.plan_id,
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Unexpected error: {str(e)}",
                error="unexpected_error"
            )
    
    async def handle_blocking_task_notification(
        self,
        request_data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> NotificationResponse:
        """
        Handle blocking task notification webhook from TrIAge API.
        
        Endpoint: POST /api/v1/notifications/slack/blocking-task
        
        Args:
            request_data: Request payload
            headers: Optional HTTP headers for signature validation
            
        Returns:
            NotificationResponse with delivery status
            
        Validates: Requirements 5.1
        """
        logger.info("Received blocking task notification request", extra={
            'user_id': request_data.get('user_id'),
            'team_id': request_data.get('team_id'),
            'task_key': request_data.get('task', {}).get('key')
        })
        
        # Validate request signature if headers provided
        if headers and self.webhook_secret:
            signature = headers.get('X-TrIAge-Signature', '')
            timestamp = headers.get('X-TrIAge-Timestamp', '')
            
            if not signature or not timestamp:
                logger.warning("Missing signature headers")
                return NotificationResponse(
                    success=False,
                    message="Missing signature headers",
                    error="missing_signature"
                )
            
            import json
            body = json.dumps(request_data, sort_keys=True).encode('utf-8')
            
            if not self.validate_webhook_signature(body, signature, timestamp):
                logger.warning("Invalid webhook signature")
                return NotificationResponse(
                    success=False,
                    message="Invalid signature",
                    error="invalid_signature"
                )
        
        # Parse and validate request
        try:
            request = BlockingTaskNotificationRequest(**request_data)
        except ValidationError as e:
            logger.error("Invalid blocking task notification request", extra={
                'error': str(e),
                'request_data': request_data
            })
            return NotificationResponse(
                success=False,
                message=f"Invalid request: {str(e)}",
                error="validation_error"
            )
        
        # Parse task data
        try:
            task = JiraIssue(**request.task)
            additional_tasks = None
            if request.additional_tasks:
                additional_tasks = [JiraIssue(**t) for t in request.additional_tasks]
        except Exception as e:
            logger.error("Failed to parse task data", extra={
                'error': str(e),
                'task_key': request.task.get('key')
            })
            return NotificationResponse(
                success=False,
                message=f"Failed to parse task: {str(e)}",
                error="parse_error"
            )
        
        # Get user mapping to find Slack user ID
        try:
            user_mapping = await self.triage_api_client.get_user_mapping(
                slack_user_id=request.user_id,
                slack_team_id=request.team_id
            )
            slack_user_id = user_mapping.get('slack_user_id', request.user_id)
        except Exception as e:
            logger.warning("Failed to get user mapping, using provided user_id", extra={
                'user_id': request.user_id,
                'error': str(e)
            })
            slack_user_id = request.user_id
        
        # Get user configuration
        try:
            user_config = await self.triage_api_client.get_config(request.user_id)
        except Exception as e:
            logger.error("Failed to get user config", extra={
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Failed to get user config: {str(e)}",
                error="config_error"
            )
        
        # Deliver notification
        try:
            result = await self.notification_service.deliver_blocking_task_alert(
                task=task,
                blocker_reason=request.blocker_reason,
                user_config=user_config,
                slack_user_id=slack_user_id,
                additional_tasks=additional_tasks
            )
            
            if result['delivered']:
                logger.info("Blocking task notification delivered successfully", extra={
                    'task_key': task.key,
                    'user_id': request.user_id,
                    'message_ts': result.get('message_ts')
                })
                
                return NotificationResponse(
                    success=True,
                    message="Blocking task notification delivered",
                    delivered=True,
                    message_ts=result.get('message_ts'),
                    channel=result.get('channel')
                )
            else:
                logger.info("Blocking task notification not delivered", extra={
                    'task_key': task.key,
                    'user_id': request.user_id,
                    'reason': result.get('reason')
                })
                
                return NotificationResponse(
                    success=True,
                    message=f"Notification not delivered: {result.get('reason')}",
                    delivered=False
                )
        
        except NotificationDeliveryError as e:
            logger.error("Failed to deliver blocking task notification", extra={
                'task_key': task.key,
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Delivery failed: {str(e)}",
                error="delivery_error"
            )
        
        except Exception as e:
            logger.error("Unexpected error delivering blocking task notification", extra={
                'task_key': task.key,
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Unexpected error: {str(e)}",
                error="unexpected_error"
            )

    async def handle_blocking_task_resolved_notification(
        self,
        request_data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> NotificationResponse:
        """
        Handle blocking task resolution notification webhook from TrIAge API.
        
        Endpoint: POST /api/v1/notifications/slack/blocking-task-resolved
        
        Args:
            request_data: Request payload
            headers: Optional HTTP headers for signature validation
            
        Returns:
            NotificationResponse with delivery status
            
        Validates: Requirements 5.5
        """
        logger.info("Received blocking task resolution notification request", extra={
            'user_id': request_data.get('user_id'),
            'team_id': request_data.get('team_id'),
            'task_key': request_data.get('task', {}).get('key')
        })
        
        # Validate request signature if headers provided
        if headers and self.webhook_secret:
            signature = headers.get('X-TrIAge-Signature', '')
            timestamp = headers.get('X-TrIAge-Timestamp', '')
            
            if not signature or not timestamp:
                logger.warning("Missing signature headers")
                return NotificationResponse(
                    success=False,
                    message="Missing signature headers",
                    error="missing_signature"
                )
            
            import json
            body = json.dumps(request_data, sort_keys=True).encode('utf-8')
            
            if not self.validate_webhook_signature(body, signature, timestamp):
                logger.warning("Invalid webhook signature")
                return NotificationResponse(
                    success=False,
                    message="Invalid signature",
                    error="invalid_signature"
                )
        
        # Parse and validate request
        try:
            request = BlockingTaskResolvedNotificationRequest(**request_data)
        except ValidationError as e:
            logger.error("Invalid blocking task resolution notification request", extra={
                'error': str(e),
                'request_data': request_data
            })
            return NotificationResponse(
                success=False,
                message=f"Invalid request: {str(e)}",
                error="validation_error"
            )
        
        # Parse task data
        try:
            task = JiraIssue(**request.task)
        except Exception as e:
            logger.error("Failed to parse task data", extra={
                'error': str(e),
                'task_key': request.task.get('key')
            })
            return NotificationResponse(
                success=False,
                message=f"Failed to parse task: {str(e)}",
                error="parse_error"
            )
        
        # Get user mapping to find Slack user ID
        try:
            user_mapping = await self.triage_api_client.get_user_mapping(
                slack_user_id=request.user_id,
                slack_team_id=request.team_id
            )
            slack_user_id = user_mapping.get('slack_user_id', request.user_id)
        except Exception as e:
            logger.warning("Failed to get user mapping, using provided user_id", extra={
                'user_id': request.user_id,
                'error': str(e)
            })
            slack_user_id = request.user_id
        
        # Get user configuration
        try:
            user_config = await self.triage_api_client.get_config(request.user_id)
        except Exception as e:
            logger.error("Failed to get user config", extra={
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Failed to get user config: {str(e)}",
                error="config_error"
            )
        
        # Deliver notification
        try:
            result = await self.notification_service.deliver_blocking_task_resolved_notification(
                task=task,
                user_config=user_config,
                slack_user_id=slack_user_id
            )
            
            if result['delivered']:
                logger.info("Blocking task resolution notification delivered successfully", extra={
                    'task_key': task.key,
                    'user_id': request.user_id,
                    'message_ts': result.get('message_ts')
                })
                
                return NotificationResponse(
                    success=True,
                    message="Blocking task resolution notification delivered",
                    delivered=True,
                    message_ts=result.get('message_ts'),
                    channel=result.get('channel')
                )
            else:
                logger.info("Blocking task resolution notification not delivered", extra={
                    'task_key': task.key,
                    'user_id': request.user_id,
                    'reason': result.get('reason')
                })
                
                return NotificationResponse(
                    success=True,
                    message=f"Notification not delivered: {result.get('reason')}",
                    delivered=False
                )
        
        except NotificationDeliveryError as e:
            logger.error("Failed to deliver blocking task resolution notification", extra={
                'task_key': task.key,
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Delivery failed: {str(e)}",
                error="delivery_error"
            )
        
        except Exception as e:
            logger.error("Unexpected error delivering blocking task resolution notification", extra={
                'task_key': task.key,
                'user_id': request.user_id,
                'error': str(e)
            })
            return NotificationResponse(
                success=False,
                message=f"Unexpected error: {str(e)}",
                error="unexpected_error"
            )
