# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Retry queue for failed Slack message deliveries.

This module implements a persistent retry queue to ensure that failed
Slack notifications don't block TrIAge core functionality and can be
retried later.

Validates: Requirements 11.1
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis

from slack_bot.config import SlackBotConfig


logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages that can be queued."""
    DAILY_PLAN = "daily_plan"
    BLOCKING_TASK = "blocking_task"
    BLOCKING_RESOLVED = "blocking_resolved"
    APPROVAL_CONFIRMATION = "approval_confirmation"
    ERROR_MESSAGE = "error_message"


@dataclass
class QueuedMessage:
    """
    Represents a message in the retry queue.
    
    Attributes:
        message_id: Unique identifier for the message
        message_type: Type of message
        user_id: Slack user ID
        team_id: Slack team ID
        channel: Channel or DM to send to
        payload: Message payload (blocks, text, etc.)
        created_at: When message was first queued
        retry_count: Number of retry attempts
        next_retry_at: When to retry next
        max_retries: Maximum number of retries
        last_error: Last error message
    """
    message_id: str
    message_type: MessageType
    user_id: str
    team_id: str
    channel: str
    payload: Dict[str, Any]
    created_at: datetime
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    max_retries: int = 5
    last_error: Optional[str] = None


class RetryQueue:
    """
    Persistent retry queue for failed Slack message deliveries.
    
    Uses Redis for persistence and implements exponential backoff
    for retries. Messages are automatically removed after max retries
    or 24 hours, whichever comes first.
    
    Validates: Requirements 11.1
    """
    
    def __init__(self, config: SlackBotConfig):
        """
        Initialize retry queue.
        
        Args:
            config: Slack bot configuration
        """
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.queue_key = "slack_bot:retry_queue"
        self.processing_key = "slack_bot:processing"
        self.max_age_hours = 24
        
        logger.info("Initialized retry queue")
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis for retry queue")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Disconnected from Redis")
    
    async def enqueue(
        self,
        message_type: MessageType,
        user_id: str,
        team_id: str,
        channel: str,
        payload: Dict[str, Any],
        message_id: Optional[str] = None
    ) -> str:
        """
        Add a message to the retry queue.
        
        Args:
            message_type: Type of message
            user_id: Slack user ID
            team_id: Slack team ID
            channel: Channel or DM to send to
            payload: Message payload
            message_id: Optional message ID (generated if not provided)
            
        Returns:
            Message ID
            
        Validates: Requirements 11.1
        """
        if not self.redis_client:
            await self.connect()
        
        # Generate message ID if not provided
        if not message_id:
            message_id = f"{message_type}:{user_id}:{datetime.utcnow().timestamp()}"
        
        # Create queued message
        now = datetime.utcnow()
        message = QueuedMessage(
            message_id=message_id,
            message_type=message_type,
            user_id=user_id,
            team_id=team_id,
            channel=channel,
            payload=payload,
            created_at=now,
            next_retry_at=now  # Retry immediately on first attempt
        )
        
        # Serialize and store
        message_data = self._serialize_message(message)
        await self.redis_client.hset(
            self.queue_key,
            message_id,
            message_data
        )
        
        logger.info(
            "Message enqueued for retry",
            extra={
                "message_id": message_id,
                "message_type": message_type,
                "user_id": user_id,
                "channel": channel
            }
        )
        
        return message_id
    
    async def get_pending_messages(self, limit: int = 10) -> List[QueuedMessage]:
        """
        Get messages that are ready for retry.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of messages ready for retry
            
        Validates: Requirements 11.1
        """
        if not self.redis_client:
            await self.connect()
        
        now = datetime.utcnow()
        messages = []
        
        # Get all messages from queue
        all_messages = await self.redis_client.hgetall(self.queue_key)
        
        for message_id, message_data in all_messages.items():
            message = self._deserialize_message(message_data)
            
            # Skip if already being processed
            is_processing = await self.redis_client.exists(
                f"{self.processing_key}:{message_id}"
            )
            if is_processing:
                continue
            
            # Skip if not ready for retry
            if message.next_retry_at and message.next_retry_at > now:
                continue
            
            # Skip if too old
            age = now - message.created_at
            if age.total_seconds() > self.max_age_hours * 3600:
                logger.warning(
                    "Message expired, removing from queue",
                    extra={
                        "message_id": message_id,
                        "age_hours": age.total_seconds() / 3600
                    }
                )
                await self.remove(message_id)
                continue
            
            # Skip if max retries exceeded
            if message.retry_count >= message.max_retries:
                logger.warning(
                    "Message exceeded max retries, removing from queue",
                    extra={
                        "message_id": message_id,
                        "retry_count": message.retry_count,
                        "max_retries": message.max_retries
                    }
                )
                await self.remove(message_id)
                continue
            
            messages.append(message)
            
            if len(messages) >= limit:
                break
        
        return messages
    
    async def mark_processing(self, message_id: str, ttl_seconds: int = 300) -> None:
        """
        Mark a message as being processed.
        
        Args:
            message_id: Message ID
            ttl_seconds: Time-to-live for processing lock
        """
        if not self.redis_client:
            await self.connect()
        
        await self.redis_client.setex(
            f"{self.processing_key}:{message_id}",
            ttl_seconds,
            "1"
        )
    
    async def mark_success(self, message_id: str) -> None:
        """
        Mark a message as successfully delivered and remove from queue.
        
        Args:
            message_id: Message ID
            
        Validates: Requirements 11.1
        """
        if not self.redis_client:
            await self.connect()
        
        # Remove from queue
        await self.redis_client.hdel(self.queue_key, message_id)
        
        # Remove processing lock
        await self.redis_client.delete(f"{self.processing_key}:{message_id}")
        
        logger.info(
            "Message delivered successfully, removed from queue",
            extra={"message_id": message_id}
        )
    
    async def mark_failure(
        self,
        message_id: str,
        error: str,
        backoff_seconds: Optional[int] = None
    ) -> None:
        """
        Mark a message delivery as failed and schedule retry.
        
        Args:
            message_id: Message ID
            error: Error message
            backoff_seconds: Optional custom backoff time
            
        Validates: Requirements 11.1
        """
        if not self.redis_client:
            await self.connect()
        
        # Get current message
        message_data = await self.redis_client.hget(self.queue_key, message_id)
        if not message_data:
            logger.warning(
                "Message not found in queue",
                extra={"message_id": message_id}
            )
            return
        
        message = self._deserialize_message(message_data)
        
        # Update retry count and error
        message.retry_count += 1
        message.last_error = error
        
        # Calculate next retry time with exponential backoff
        if backoff_seconds is None:
            backoff_seconds = min(300, 30 * (2 ** message.retry_count))  # Max 5 minutes
        
        message.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
        
        # Update in queue
        message_data = self._serialize_message(message)
        await self.redis_client.hset(self.queue_key, message_id, message_data)
        
        # Remove processing lock
        await self.redis_client.delete(f"{self.processing_key}:{message_id}")
        
        logger.warning(
            "Message delivery failed, scheduled for retry",
            extra={
                "message_id": message_id,
                "retry_count": message.retry_count,
                "next_retry_at": message.next_retry_at.isoformat(),
                "error": error
            }
        )
    
    async def remove(self, message_id: str) -> None:
        """
        Remove a message from the queue.
        
        Args:
            message_id: Message ID
        """
        if not self.redis_client:
            await self.connect()
        
        await self.redis_client.hdel(self.queue_key, message_id)
        await self.redis_client.delete(f"{self.processing_key}:{message_id}")
        
        logger.info(
            "Message removed from queue",
            extra={"message_id": message_id}
        )
    
    async def get_queue_size(self) -> int:
        """
        Get the current size of the retry queue.
        
        Returns:
            Number of messages in queue
        """
        if not self.redis_client:
            await self.connect()
        
        return await self.redis_client.hlen(self.queue_key)
    
    def _serialize_message(self, message: QueuedMessage) -> str:
        """Serialize message to JSON."""
        data = asdict(message)
        # Convert datetime objects to ISO format
        data['created_at'] = message.created_at.isoformat()
        if message.next_retry_at:
            data['next_retry_at'] = message.next_retry_at.isoformat()
        return json.dumps(data)
    
    def _deserialize_message(self, data: str) -> QueuedMessage:
        """Deserialize message from JSON."""
        obj = json.loads(data)
        # Convert ISO format back to datetime
        obj['created_at'] = datetime.fromisoformat(obj['created_at'])
        if obj.get('next_retry_at'):
            obj['next_retry_at'] = datetime.fromisoformat(obj['next_retry_at'])
        obj['message_type'] = MessageType(obj['message_type'])
        return QueuedMessage(**obj)


async def process_retry_queue(
    queue: RetryQueue,
    slack_client,
    max_concurrent: int = 5
) -> None:
    """
    Process messages in the retry queue.
    
    This function should be run as a background task to continuously
    process failed messages.
    
    Args:
        queue: RetryQueue instance
        slack_client: SlackAPIClient instance for sending messages
        max_concurrent: Maximum concurrent message deliveries
        
    Validates: Requirements 11.1
    """
    logger.info("Starting retry queue processor")
    
    while True:
        try:
            # Get pending messages
            messages = await queue.get_pending_messages(limit=max_concurrent)
            
            if not messages:
                # No messages to process, wait before checking again
                await asyncio.sleep(10)
                continue
            
            logger.info(
                f"Processing {len(messages)} messages from retry queue",
                extra={"message_count": len(messages)}
            )
            
            # Process messages concurrently
            tasks = [
                _process_single_message(queue, slack_client, message)
                for message in messages
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(
                "Error in retry queue processor",
                extra={"error": str(e)},
                exc_info=True
            )
            await asyncio.sleep(30)  # Wait before retrying


async def _process_single_message(
    queue: RetryQueue,
    slack_client,
    message: QueuedMessage
) -> None:
    """Process a single message from the retry queue."""
    try:
        # Mark as processing
        await queue.mark_processing(message.message_id)
        
        logger.info(
            "Retrying message delivery",
            extra={
                "message_id": message.message_id,
                "message_type": message.message_type,
                "retry_count": message.retry_count
            }
        )
        
        # Attempt delivery
        await slack_client.post_message(
            channel=message.channel,
            text=message.payload.get('text', ''),
            blocks=message.payload.get('blocks')
        )
        
        # Mark as successful
        await queue.mark_success(message.message_id)
        
    except Exception as e:
        # Mark as failed and schedule retry
        await queue.mark_failure(
            message.message_id,
            str(e)
        )
