# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Webhook handler for Slack events.

This module handles incoming webhook events from Slack, including signature
validation, timestamp validation, deduplication, and async event processing.

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 12.4
"""

import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass

from slack_bot.models import WebhookEvent
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class WebhookResponse:
    """Response from webhook processing."""
    status_code: int
    body: Dict[str, Any]
    processed: bool = False
    duplicate: bool = False
    error: Optional[str] = None


class SignatureValidator:
    """
    Validates Slack webhook signatures using signing secret.
    
    Implements Slack's signature verification algorithm to ensure
    webhooks are authentic and haven't been tampered with.
    
    Validates: Requirements 7.3, 12.4
    """
    
    # Maximum age of webhook request (5 minutes)
    MAX_REQUEST_AGE_SECONDS = 300
    
    def __init__(self, signing_secret: str):
        """
        Initialize signature validator.
        
        Args:
            signing_secret: Slack app signing secret
        """
        self.signing_secret = signing_secret.encode('utf-8')
        logger.info("Signature validator initialized")
    
    def validate_signature(
        self,
        timestamp: str,
        body: bytes,
        signature: str
    ) -> bool:
        """
        Validate webhook signature using Slack's signing secret.
        
        Args:
            timestamp: X-Slack-Request-Timestamp header value
            body: Raw request body bytes
            signature: X-Slack-Signature header value
            
        Returns:
            True if signature is valid, False otherwise
            
        Validates: Requirements 7.3, 12.4
        """
        try:
            # Validate timestamp to prevent replay attacks
            if not self._validate_timestamp(timestamp):
                logger.warning("Webhook timestamp validation failed", extra={
                    'timestamp': timestamp,
                    'current_time': int(time.time())
                })
                return False
            
            # Compute expected signature
            sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
            expected_signature = 'v0=' + hmac.new(
                self.signing_secret,
                sig_basestring,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures using constant-time comparison
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning("Webhook signature mismatch", extra={
                    'provided_signature': signature[:20] + '...',
                    'timestamp': timestamp
                })
            
            return is_valid
            
        except Exception as e:
            logger.error("Signature validation error", extra={
                'error': str(e),
                'timestamp': timestamp
            })
            return False
    
    def _validate_timestamp(self, timestamp: str) -> bool:
        """
        Validate webhook timestamp is within acceptable window.
        
        Prevents replay attacks by rejecting requests older than 5 minutes.
        
        Args:
            timestamp: Unix timestamp as string
            
        Returns:
            True if timestamp is valid, False otherwise
            
        Validates: Requirements 7.3
        """
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            age = abs(current_time - request_time)
            
            if age > self.MAX_REQUEST_AGE_SECONDS:
                logger.warning("Webhook timestamp too old", extra={
                    'age_seconds': age,
                    'max_age': self.MAX_REQUEST_AGE_SECONDS
                })
                return False
            
            return True
            
        except (ValueError, TypeError) as e:
            logger.error("Invalid timestamp format", extra={
                'timestamp': timestamp,
                'error': str(e)
            })
            return False


class WebhookDeduplicator:
    """
    Prevents duplicate processing of webhook events.
    
    Uses Redis or in-memory cache with TTL to track processed event IDs
    and reject duplicates.
    
    Validates: Requirements 7.4
    """
    
    def __init__(self, redis_client: Optional[Any] = None, ttl_seconds: int = 300):
        """
        Initialize webhook deduplicator.
        
        Args:
            redis_client: Optional Redis client for distributed deduplication
            ttl_seconds: Time-to-live for event IDs (default 5 minutes)
        """
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        
        # In-memory cache for development/testing
        self._memory_cache: Dict[str, datetime] = {}
        
        logger.info("Webhook deduplicator initialized", extra={
            'ttl_seconds': ttl_seconds,
            'using_redis': redis_client is not None
        })
    
    async def is_duplicate(self, event_id: str) -> bool:
        """
        Check if event has already been processed.
        
        Args:
            event_id: Unique event identifier
            
        Returns:
            True if event is a duplicate, False otherwise
            
        Validates: Requirements 7.4
        """
        if self.redis_client:
            return await self._check_redis(event_id)
        else:
            return self._check_memory(event_id)
    
    async def mark_processed(self, event_id: str) -> None:
        """
        Mark event as processed to prevent future duplicates.
        
        Args:
            event_id: Unique event identifier
            
        Validates: Requirements 7.4
        """
        if self.redis_client:
            await self._mark_redis(event_id)
        else:
            self._mark_memory(event_id)
        
        logger.debug("Event marked as processed", extra={'event_id': event_id})
    
    async def _check_redis(self, event_id: str) -> bool:
        """Check if event exists in Redis."""
        try:
            exists = await self.redis_client.exists(f"webhook:{event_id}")
            return bool(exists)
        except Exception as e:
            logger.error("Redis check failed", extra={
                'event_id': event_id,
                'error': str(e)
            })
            # Fail open - allow processing if Redis is unavailable
            return False
    
    async def _mark_redis(self, event_id: str) -> None:
        """Mark event as processed in Redis with TTL."""
        try:
            await self.redis_client.setex(
                f"webhook:{event_id}",
                self.ttl_seconds,
                "1"
            )
        except Exception as e:
            logger.error("Redis mark failed", extra={
                'event_id': event_id,
                'error': str(e)
            })
    
    def _check_memory(self, event_id: str) -> bool:
        """Check if event exists in memory cache."""
        # Clean expired entries
        self._clean_expired()
        
        return event_id in self._memory_cache
    
    def _mark_memory(self, event_id: str) -> None:
        """Mark event as processed in memory cache."""
        self._memory_cache[event_id] = datetime.now(timezone.utc)
    
    def _clean_expired(self) -> None:
        """Remove expired entries from memory cache."""
        now = datetime.now(timezone.utc)
        expired = [
            event_id
            for event_id, timestamp in self._memory_cache.items()
            if (now - timestamp).total_seconds() > self.ttl_seconds
        ]
        for event_id in expired:
            del self._memory_cache[event_id]


class WebhookHandler:
    """
    Main webhook handler for Slack events.
    
    Receives incoming webhooks, validates signatures, checks for duplicates,
    and processes events asynchronously with immediate acknowledgment.
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
    """
    
    def __init__(
        self,
        signing_secret: str,
        deduplicator: WebhookDeduplicator,
        event_processor: Optional[Any] = None,
        timeout_seconds: int = 3
    ):
        """
        Initialize webhook handler.
        
        Args:
            signing_secret: Slack app signing secret for signature validation
            deduplicator: WebhookDeduplicator instance
            event_processor: Optional AsyncEventProcessor for background processing
            timeout_seconds: Maximum time to respond to webhook (default 3s)
        """
        self.validator = SignatureValidator(signing_secret)
        self.deduplicator = deduplicator
        self.event_processor = event_processor
        self.timeout_seconds = timeout_seconds
        
        logger.info("Webhook handler initialized", extra={
            'timeout_seconds': timeout_seconds,
            'has_event_processor': event_processor is not None
        })
    
    async def handle_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> WebhookResponse:
        """
        Handle incoming webhook from Slack.
        
        This method:
        1. Validates the webhook signature
        2. Checks for duplicate events
        3. Acknowledges immediately (< 3s)
        4. Queues event for async processing
        
        Args:
            headers: HTTP request headers
            body: Raw request body bytes
            
        Returns:
            WebhookResponse with status and processing info
            
        Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
        """
        start_time = time.time()
        
        try:
            # Extract required headers
            timestamp = headers.get('X-Slack-Request-Timestamp', '')
            signature = headers.get('X-Slack-Signature', '')
            
            if not timestamp or not signature:
                logger.warning("Missing required headers", extra={
                    'has_timestamp': bool(timestamp),
                    'has_signature': bool(signature)
                })
                return WebhookResponse(
                    status_code=400,
                    body={'error': 'Missing required headers'},
                    error='missing_headers'
                )
            
            # Validate signature
            if not self.validator.validate_signature(timestamp, body, signature):
                logger.warning("Invalid webhook signature")
                return WebhookResponse(
                    status_code=401,
                    body={'error': 'Invalid signature'},
                    error='invalid_signature'
                )
            
            # Parse event
            import json
            try:
                payload = json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error("Failed to parse webhook body", extra={'error': str(e)})
                return WebhookResponse(
                    status_code=400,
                    body={'error': 'Invalid JSON'},
                    error='invalid_json'
                )
            
            # Handle URL verification challenge
            if payload.get('type') == 'url_verification':
                logger.info("Handling URL verification challenge")
                return WebhookResponse(
                    status_code=200,
                    body={'challenge': payload.get('challenge', '')},
                    processed=True
                )
            
            # Extract event ID for deduplication
            event_id = payload.get('event_id') or payload.get('callback_id') or str(time.time())
            
            # Check for duplicate
            if await self.deduplicator.is_duplicate(event_id):
                logger.info("Duplicate webhook event detected", extra={
                    'event_id': event_id
                })
                return WebhookResponse(
                    status_code=200,
                    body={'ok': True},
                    duplicate=True
                )
            
            # Mark as processed
            await self.deduplicator.mark_processed(event_id)
            
            # Create webhook event
            event = self._parse_event(payload, event_id)
            
            # Queue for async processing if processor is available
            if self.event_processor:
                await self.event_processor.process_async(event)
            
            # Acknowledge immediately (< 3s requirement)
            logger.info("Webhook event received", extra={
                'event_id': event_id,
                'event_type': event.event_type,
                'user_id': event.user_id,
                'team_id': event.team_id,
                'processing_time_ms': int((time.time() - start_time) * 1000)
            })
            
            return WebhookResponse(
                status_code=200,
                body={'ok': True},
                processed=True
            )
            
        except Exception as e:
            logger.error("Webhook processing error", extra={
                'error': str(e),
                'processing_time_ms': int((time.time() - start_time) * 1000)
            })
            return WebhookResponse(
                status_code=500,
                body={'error': 'Internal server error'},
                error=str(e)
            )
    
    def _parse_event(self, payload: Dict[str, Any], event_id: str) -> WebhookEvent:
        """
        Parse webhook payload into WebhookEvent model.
        
        Args:
            payload: Parsed JSON payload
            event_id: Unique event identifier
            
        Returns:
            WebhookEvent instance
        """
        # Determine event type
        event_type = payload.get('type', 'unknown')
        
        # Extract user and team IDs
        user_id = (
            payload.get('user_id') or
            payload.get('user', {}).get('id') or
            payload.get('event', {}).get('user') or
            'UNKNOWN'
        )
        
        team_id = (
            payload.get('team_id') or
            payload.get('team', {}).get('id') or
            'UNKNOWN'
        )
        
        return WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            team_id=team_id,
            payload=payload,
            timestamp=datetime.now(timezone.utc)
        )
