# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Slack API client with retry logic and error handling.

This module provides a wrapper around the Slack SDK with exponential backoff
retry logic for handling transient failures and rate limits.

Validates: Requirements 11.2
"""

import asyncio
import logging
import random
from typing import Any, Dict, Optional, Callable
from functools import wraps

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from slack_bot.config import SlackBotConfig


logger = logging.getLogger(__name__)


class SlackAPIRetryError(Exception):
    """Exception raised when Slack API call fails after all retries."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, attempts: int = 0):
        self.message = message
        self.original_error = original_error
        self.attempts = attempts
        super().__init__(message)


class SlackAPIClient:
    """
    Slack API client with retry logic and error handling.
    
    This client wraps the Slack SDK and adds:
    - Exponential backoff with jitter for retryable errors
    - Automatic retry for rate limits (429)
    - Retry for server errors (500, 502, 503, 504)
    - Comprehensive error logging
    
    Validates: Requirements 11.2
    """
    
    def __init__(self, config: SlackBotConfig):
        """
        Initialize Slack API client.
        
        Args:
            config: Slack bot configuration
        """
        self.config = config
        self.client = AsyncWebClient(token=config.slack_bot_token)
        self.max_retries = config.max_retries
        self.retry_backoff_base = config.retry_backoff_base
        
        logger.info(
            "Initialized Slack API client",
            extra={
                "max_retries": self.max_retries,
                "backoff_base": self.retry_backoff_base
            }
        )
    
    def _is_retryable_error(self, error: SlackApiError) -> bool:
        """
        Determine if a Slack API error is retryable.
        
        Args:
            error: Slack API error
            
        Returns:
            True if error should be retried
        """
        # Rate limiting
        if error.response.status_code == 429:
            return True
        
        # Server errors
        if error.response.status_code in {500, 502, 503, 504}:
            return True
        
        # Specific error codes that are retryable
        retryable_errors = {
            'internal_error',
            'service_unavailable',
            'fatal_error'
        }
        
        if error.response.get('error') in retryable_errors:
            return True
        
        return False
    
    def _calculate_backoff(self, attempt: int, retry_after: Optional[int] = None) -> float:
        """
        Calculate backoff time with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (0-indexed)
            retry_after: Optional retry-after value from rate limit response
            
        Returns:
            Backoff time in seconds
            
        Validates: Requirements 11.2
        """
        if retry_after is not None:
            # Use Slack's retry-after header if provided
            base_wait = float(retry_after)
        else:
            # Exponential backoff: base^attempt
            base_wait = self.retry_backoff_base ** attempt
        
        # Add jitter (10% of base wait time)
        jitter = base_wait * 0.1 * random.random()
        
        return base_wait + jitter
    
    async def _retry_api_call(
        self,
        api_method: Callable,
        method_name: str,
        **kwargs
    ) -> Any:
        """
        Execute Slack API call with retry logic.
        
        Args:
            api_method: Slack API method to call
            method_name: Name of the method (for logging)
            **kwargs: Arguments to pass to the API method
            
        Returns:
            API response
            
        Raises:
            SlackAPIRetryError: If call fails after all retries
            
        Validates: Requirements 11.2
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"Calling Slack API: {method_name}",
                    extra={
                        "method": method_name,
                        "attempt": attempt + 1,
                        "max_attempts": self.max_retries + 1
                    }
                )
                
                response = await api_method(**kwargs)
                
                logger.debug(
                    f"Slack API call successful: {method_name}",
                    extra={"method": method_name, "attempt": attempt + 1}
                )
                
                return response
                
            except SlackApiError as e:
                last_error = e
                
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(
                        f"Non-retryable Slack API error: {method_name}",
                        extra={
                            "method": method_name,
                            "error": e.response.get('error'),
                            "status_code": e.response.status_code
                        }
                    )
                    raise SlackAPIRetryError(
                        f"Slack API error: {e.response.get('error')}",
                        original_error=e,
                        attempts=attempt + 1
                    )
                
                # Don't retry if we've exhausted attempts
                if attempt >= self.max_retries:
                    logger.error(
                        f"Max retries exceeded for Slack API: {method_name}",
                        extra={
                            "method": method_name,
                            "attempts": attempt + 1,
                            "error": e.response.get('error')
                        }
                    )
                    break
                
                # Calculate backoff time
                retry_after = e.response.headers.get('Retry-After')
                if retry_after:
                    try:
                        retry_after = int(retry_after)
                    except (ValueError, TypeError):
                        retry_after = None
                
                backoff = self._calculate_backoff(attempt, retry_after)
                
                logger.warning(
                    f"Retryable Slack API error, retrying in {backoff:.2f}s",
                    extra={
                        "method": method_name,
                        "attempt": attempt + 1,
                        "backoff": backoff,
                        "error": e.response.get('error'),
                        "status_code": e.response.status_code
                    }
                )
                
                await asyncio.sleep(backoff)
                
            except Exception as e:
                last_error = e
                logger.error(
                    f"Unexpected error calling Slack API: {method_name}",
                    extra={
                        "method": method_name,
                        "attempt": attempt + 1,
                        "error": str(e)
                    },
                    exc_info=True
                )
                raise SlackAPIRetryError(
                    f"Unexpected error: {str(e)}",
                    original_error=e,
                    attempts=attempt + 1
                )
        
        # Max retries exceeded
        raise SlackAPIRetryError(
            f"Slack API call failed after {self.max_retries + 1} attempts",
            original_error=last_error,
            attempts=self.max_retries + 1
        )
    
    async def post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list] = None,
        thread_ts: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post a message to a Slack channel with retry logic.
        
        Args:
            channel: Channel ID or user ID
            text: Fallback text for the message
            blocks: Optional Block Kit blocks
            thread_ts: Optional thread timestamp for replies
            **kwargs: Additional arguments for chat.postMessage
            
        Returns:
            API response
            
        Raises:
            SlackAPIRetryError: If message posting fails after retries
        """
        return await self._retry_api_call(
            self.client.chat_postMessage,
            "chat.postMessage",
            channel=channel,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts,
            **kwargs
        )
    
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Update an existing Slack message with retry logic.
        
        Args:
            channel: Channel ID where message was posted
            ts: Timestamp of message to update
            text: New fallback text
            blocks: New Block Kit blocks
            **kwargs: Additional arguments for chat.update
            
        Returns:
            API response
            
        Raises:
            SlackAPIRetryError: If message update fails after retries
        """
        return await self._retry_api_call(
            self.client.chat_update,
            "chat.update",
            channel=channel,
            ts=ts,
            text=text,
            blocks=blocks,
            **kwargs
        )
    
    async def post_ephemeral(
        self,
        channel: str,
        user: str,
        text: str,
        blocks: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post an ephemeral message (visible only to specific user) with retry logic.
        
        Args:
            channel: Channel ID where message should appear
            user: User ID who should see the message
            text: Fallback text
            blocks: Optional Block Kit blocks
            **kwargs: Additional arguments for chat.postEphemeral
            
        Returns:
            API response
            
        Raises:
            SlackAPIRetryError: If ephemeral message posting fails after retries
        """
        return await self._retry_api_call(
            self.client.chat_postEphemeral,
            "chat.postEphemeral",
            channel=channel,
            user=user,
            text=text,
            blocks=blocks,
            **kwargs
        )
    
    async def get_user_info(
        self,
        user: str
    ) -> Dict[str, Any]:
        """
        Get information about a Slack user with retry logic.
        
        Args:
            user: User ID
            
        Returns:
            User information
            
        Raises:
            SlackAPIRetryError: If user info retrieval fails after retries
        """
        return await self._retry_api_call(
            self.client.users_info,
            "users.info",
            user=user
        )
    
    async def list_conversations(
        self,
        types: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """
        List conversations (channels) with retry logic.
        
        Args:
            types: Comma-separated list of conversation types
            limit: Maximum number of results
            **kwargs: Additional arguments for conversations.list
            
        Returns:
            List of conversations
            
        Raises:
            SlackAPIRetryError: If conversation listing fails after retries
        """
        return await self._retry_api_call(
            self.client.conversations_list,
            "conversations.list",
            types=types,
            limit=limit,
            **kwargs
        )
    
    async def open_conversation(
        self,
        users: str
    ) -> Dict[str, Any]:
        """
        Open a direct message conversation with retry logic.
        
        Args:
            users: Comma-separated list of user IDs
            
        Returns:
            Conversation information
            
        Raises:
            SlackAPIRetryError: If conversation opening fails after retries
        """
        return await self._retry_api_call(
            self.client.conversations_open,
            "conversations.open",
            users=users
        )
