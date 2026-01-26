# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Notification delivery service for Slack bot.

This module handles delivery of daily plans and blocking task notifications
to users' configured Slack channels or DMs. It manages user lookup, channel
resolution, and message delivery with proper error handling.

Validates: Requirements 2.1
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from slack_bot.models import SlackMessage, SlackConfig
from slack_bot.message_formatter import MessageFormatter
from slack_bot.logging_config import get_logger
from triage.models import DailyPlan, JiraIssue


logger = get_logger(__name__)


class NotificationDeliveryError(Exception):
    """Exception raised when notification delivery fails."""
    def __init__(self, message: str, user_id: Optional[str] = None, error: Optional[Exception] = None):
        self.message = message
        self.user_id = user_id
        self.error = error
        super().__init__(message)


class NotificationDeliveryService:
    """
    Service for delivering notifications to Slack users.
    
    This service handles:
    - User lookup and channel resolution
    - Message delivery to configured channels or DMs
    - Retry logic for failed deliveries
    - Error handling and logging
    
    Validates: Requirements 2.1
    """
    
    def __init__(
        self,
        slack_client: AsyncWebClient,
        message_formatter: MessageFormatter,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0
    ):
        """
        Initialize notification delivery service.
        
        Args:
            slack_client: Async Slack Web API client
            message_formatter: MessageFormatter for creating Slack messages
            max_retries: Maximum number of delivery retry attempts
            retry_backoff_base: Base for exponential backoff calculation
        """
        self.slack_client = slack_client
        self.message_formatter = message_formatter
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        
        logger.info("Notification delivery service initialized", extra={
            'max_retries': max_retries,
            'retry_backoff_base': retry_backoff_base
        })
    
    async def deliver_daily_plan(
        self,
        plan: DailyPlan,
        plan_id: str,
        user_config: SlackConfig,
        slack_user_id: str
    ) -> Dict[str, Any]:
        """
        Deliver daily plan to user's configured channel or DM.
        
        Args:
            plan: DailyPlan to deliver
            plan_id: Unique identifier for the plan
            user_config: User's Slack configuration
            slack_user_id: Slack user ID for DM delivery
            
        Returns:
            Dictionary with delivery information (message_ts, channel, etc.)
            
        Raises:
            NotificationDeliveryError: If delivery fails after retries
            
        Validates: Requirements 2.1
        """
        logger.info("Delivering daily plan", extra={
            'plan_id': plan_id,
            'user_id': user_config.user_id,
            'notification_channel': user_config.notification_channel,
            'notifications_enabled': user_config.notifications_enabled
        })
        
        # Check if notifications are enabled
        if not user_config.notifications_enabled:
            logger.info("Notifications disabled for user", extra={
                'user_id': user_config.user_id,
                'plan_id': plan_id
            })
            return {
                'delivered': False,
                'reason': 'notifications_disabled',
                'user_id': user_config.user_id
            }
        
        # Format plan message
        try:
            message = self.message_formatter.format_daily_plan(plan, plan_id)
        except Exception as e:
            logger.error("Failed to format daily plan", extra={
                'plan_id': plan_id,
                'user_id': user_config.user_id,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to format daily plan: {str(e)}",
                user_id=user_config.user_id,
                error=e
            )
        
        # Resolve target channel
        target_channel = await self._resolve_channel(
            user_config.notification_channel,
            slack_user_id
        )
        
        # Deliver message
        try:
            result = await self._deliver_message(
                message=message,
                channel=target_channel,
                user_id=user_config.user_id
            )
            
            logger.info("Daily plan delivered successfully", extra={
                'plan_id': plan_id,
                'user_id': user_config.user_id,
                'channel': target_channel,
                'message_ts': result.get('ts')
            })
            
            return {
                'delivered': True,
                'message_ts': result.get('ts'),
                'channel': target_channel,
                'user_id': user_config.user_id,
                'plan_id': plan_id
            }
            
        except Exception as e:
            logger.error("Failed to deliver daily plan", extra={
                'plan_id': plan_id,
                'user_id': user_config.user_id,
                'channel': target_channel,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to deliver daily plan: {str(e)}",
                user_id=user_config.user_id,
                error=e
            )
    
    async def deliver_blocking_task_alert(
        self,
        task: JiraIssue,
        blocker_reason: str,
        user_config: SlackConfig,
        slack_user_id: str,
        additional_tasks: Optional[list[JiraIssue]] = None
    ) -> Dict[str, Any]:
        """
        Deliver blocking task alert to user's configured channel or DM.
        
        Args:
            task: Primary blocking task
            blocker_reason: Reason why task is blocking
            user_config: User's Slack configuration
            slack_user_id: Slack user ID for DM delivery
            additional_tasks: Optional list of additional blocking tasks for grouping
            
        Returns:
            Dictionary with delivery information
            
        Raises:
            NotificationDeliveryError: If delivery fails after retries
            
        Validates: Requirements 5.1, 5.2, 5.3
        """
        logger.info("Delivering blocking task alert", extra={
            'task_key': task.key,
            'user_id': user_config.user_id,
            'notification_channel': user_config.notification_channel,
            'num_additional_tasks': len(additional_tasks) if additional_tasks else 0
        })
        
        # Check if notifications are enabled
        if not user_config.notifications_enabled:
            logger.info("Notifications disabled for user", extra={
                'user_id': user_config.user_id,
                'task_key': task.key
            })
            return {
                'delivered': False,
                'reason': 'notifications_disabled',
                'user_id': user_config.user_id
            }
        
        # Format blocking task message
        try:
            message = self.message_formatter.format_blocking_task_alert(
                task=task,
                blocker_reason=blocker_reason,
                tasks=additional_tasks
            )
        except Exception as e:
            logger.error("Failed to format blocking task alert", extra={
                'task_key': task.key,
                'user_id': user_config.user_id,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to format blocking task alert: {str(e)}",
                user_id=user_config.user_id,
                error=e
            )
        
        # Resolve target channel
        target_channel = await self._resolve_channel(
            user_config.notification_channel,
            slack_user_id
        )
        
        # Deliver message
        try:
            result = await self._deliver_message(
                message=message,
                channel=target_channel,
                user_id=user_config.user_id
            )
            
            logger.info("Blocking task alert delivered successfully", extra={
                'task_key': task.key,
                'user_id': user_config.user_id,
                'channel': target_channel,
                'message_ts': result.get('ts')
            })
            
            return {
                'delivered': True,
                'message_ts': result.get('ts'),
                'channel': target_channel,
                'user_id': user_config.user_id,
                'task_key': task.key
            }
            
        except Exception as e:
            logger.error("Failed to deliver blocking task alert", extra={
                'task_key': task.key,
                'user_id': user_config.user_id,
                'channel': target_channel,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to deliver blocking task alert: {str(e)}",
                user_id=user_config.user_id,
                error=e
            )
    
    async def _resolve_channel(
        self,
        notification_channel: str,
        slack_user_id: str
    ) -> str:
        """
        Resolve notification channel to actual Slack channel ID.
        
        If notification_channel is "DM", opens a DM with the user.
        Otherwise, validates the channel ID.
        
        Args:
            notification_channel: Channel ID or "DM"
            slack_user_id: Slack user ID for DM resolution
            
        Returns:
            Resolved channel ID
            
        Raises:
            NotificationDeliveryError: If channel resolution fails
            
        Validates: Requirements 2.1
        """
        if notification_channel == "DM":
            # Open DM with user
            try:
                logger.debug("Opening DM with user", extra={
                    'slack_user_id': slack_user_id
                })
                
                response = await self.slack_client.conversations_open(
                    users=[slack_user_id]
                )
                
                if not response.get('ok'):
                    raise NotificationDeliveryError(
                        f"Failed to open DM: {response.get('error')}",
                        user_id=slack_user_id
                    )
                
                channel_id = response['channel']['id']
                logger.debug("DM opened successfully", extra={
                    'slack_user_id': slack_user_id,
                    'channel_id': channel_id
                })
                
                return channel_id
                
            except SlackApiError as e:
                logger.error("Slack API error opening DM", extra={
                    'slack_user_id': slack_user_id,
                    'error': str(e)
                })
                raise NotificationDeliveryError(
                    f"Failed to open DM: {str(e)}",
                    user_id=slack_user_id,
                    error=e
                )
        else:
            # Use provided channel ID
            logger.debug("Using configured channel", extra={
                'channel_id': notification_channel
            })
            return notification_channel
    
    async def _deliver_message(
        self,
        message: SlackMessage,
        channel: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Deliver message to Slack channel with retry logic.
        
        Args:
            message: SlackMessage to deliver
            channel: Target channel ID
            user_id: User ID for logging
            
        Returns:
            Slack API response
            
        Raises:
            NotificationDeliveryError: If delivery fails after retries
            
        Validates: Requirements 2.1, 11.2
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("Attempting message delivery", extra={
                    'channel': channel,
                    'user_id': user_id,
                    'attempt': attempt + 1,
                    'max_retries': self.max_retries + 1
                })
                
                # Send message
                response = await self.slack_client.chat_postMessage(
                    channel=channel,
                    blocks=message.blocks,
                    text=message.text,
                    thread_ts=message.thread_ts
                )
                
                if not response.get('ok'):
                    raise NotificationDeliveryError(
                        f"Slack API returned not ok: {response.get('error')}",
                        user_id=user_id
                    )
                
                logger.debug("Message delivered successfully", extra={
                    'channel': channel,
                    'user_id': user_id,
                    'message_ts': response.get('ts'),
                    'attempt': attempt + 1
                })
                
                # Return response data (handle both dict and response object)
                if hasattr(response, 'data'):
                    return response.data
                else:
                    return response
                
            except SlackApiError as e:
                last_error = e
                error_code = e.response.get('error', 'unknown')
                
                # Check if error is retryable
                retryable_errors = {'rate_limited', 'internal_error', 'service_unavailable'}
                
                if error_code in retryable_errors and attempt < self.max_retries:
                    # Calculate backoff with jitter
                    backoff = (self.retry_backoff_base ** attempt) * 0.5
                    jitter = backoff * 0.1
                    wait_time = backoff + jitter
                    
                    logger.warning("Retryable Slack API error, retrying", extra={
                        'error_code': error_code,
                        'attempt': attempt + 1,
                        'wait_time': wait_time,
                        'user_id': user_id
                    })
                    
                    await asyncio.sleep(wait_time)
                    continue
                
                # Non-retryable error or max retries exceeded
                logger.error("Slack API error", extra={
                    'error_code': error_code,
                    'error_message': str(e),
                    'user_id': user_id,
                    'attempt': attempt + 1
                })
                
                raise NotificationDeliveryError(
                    f"Slack API error: {error_code}",
                    user_id=user_id,
                    error=e
                )
            
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    backoff = (self.retry_backoff_base ** attempt) * 0.5
                    logger.warning("Unexpected error, retrying", extra={
                        'error': str(e),
                        'attempt': attempt + 1,
                        'wait_time': backoff,
                        'user_id': user_id
                    })
                    await asyncio.sleep(backoff)
                    continue
        
        # Max retries exceeded
        logger.error("Max retries exceeded for message delivery", extra={
            'user_id': user_id,
            'channel': channel,
            'max_retries': self.max_retries
        })
        
        raise NotificationDeliveryError(
            f"Failed to deliver message after {self.max_retries} retries: {str(last_error)}",
            user_id=user_id,
            error=last_error
        )
    
    async def get_user_info(self, slack_user_id: str) -> Dict[str, Any]:
        """
        Get user information from Slack.
        
        Args:
            slack_user_id: Slack user ID
            
        Returns:
            User information dictionary
            
        Raises:
            NotificationDeliveryError: If user lookup fails
        """
        try:
            logger.debug("Getting user info", extra={
                'slack_user_id': slack_user_id
            })
            
            response = await self.slack_client.users_info(user=slack_user_id)
            
            if not response.get('ok'):
                raise NotificationDeliveryError(
                    f"Failed to get user info: {response.get('error')}",
                    user_id=slack_user_id
                )
            
            user_info = response['user']
            logger.debug("User info retrieved", extra={
                'slack_user_id': slack_user_id,
                'display_name': user_info.get('profile', {}).get('display_name')
            })
            
            return user_info
            
        except SlackApiError as e:
            logger.error("Slack API error getting user info", extra={
                'slack_user_id': slack_user_id,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to get user info: {str(e)}",
                user_id=slack_user_id,
                error=e
            )

    async def deliver_blocking_task_resolved_notification(
        self,
        task: JiraIssue,
        user_config: SlackConfig,
        slack_user_id: str
    ) -> Dict[str, Any]:
        """
        Deliver blocking task resolution notification to user's configured channel or DM.
        
        Args:
            task: Resolved blocking task
            user_config: User's Slack configuration
            slack_user_id: Slack user ID for DM delivery
            
        Returns:
            Dictionary with delivery information
            
        Raises:
            NotificationDeliveryError: If delivery fails after retries
            
        Validates: Requirements 5.5
        """
        logger.info("Delivering blocking task resolution notification", extra={
            'task_key': task.key,
            'user_id': user_config.user_id,
            'notification_channel': user_config.notification_channel
        })
        
        # Check if notifications are enabled
        if not user_config.notifications_enabled:
            logger.info("Notifications disabled for user", extra={
                'user_id': user_config.user_id,
                'task_key': task.key
            })
            return {
                'delivered': False,
                'reason': 'notifications_disabled',
                'user_id': user_config.user_id
            }
        
        # Format resolution notification message
        try:
            message = self.message_formatter.format_blocking_task_resolved(task)
        except Exception as e:
            logger.error("Failed to format blocking task resolution notification", extra={
                'task_key': task.key,
                'user_id': user_config.user_id,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to format blocking task resolution notification: {str(e)}",
                user_id=user_config.user_id,
                error=e
            )
        
        # Resolve target channel
        target_channel = await self._resolve_channel(
            user_config.notification_channel,
            slack_user_id
        )
        
        # Deliver message
        try:
            result = await self._deliver_message(
                message=message,
                channel=target_channel,
                user_id=user_config.user_id
            )
            
            logger.info("Blocking task resolution notification delivered successfully", extra={
                'task_key': task.key,
                'user_id': user_config.user_id,
                'channel': target_channel,
                'message_ts': result.get('ts')
            })
            
            return {
                'delivered': True,
                'message_ts': result.get('ts'),
                'channel': target_channel,
                'user_id': user_config.user_id,
                'task_key': task.key
            }
            
        except Exception as e:
            logger.error("Failed to deliver blocking task resolution notification", extra={
                'task_key': task.key,
                'user_id': user_config.user_id,
                'channel': target_channel,
                'error': str(e)
            })
            raise NotificationDeliveryError(
                f"Failed to deliver blocking task resolution notification: {str(e)}",
                user_id=user_config.user_id,
                error=e
            )
