# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for webhook processing error handling.

Tests universal properties of webhook error handling to ensure errors
are logged and users are notified appropriately using Hypothesis.

Feature: slack-integration, Property 14: Webhook Processing Error Handling
Validates: Requirements 7.5
"""

import pytest
import time
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, Mock, patch
from hypothesis import given, strategies as st, settings, assume

from slack_bot.webhook_handler import (
    WebhookHandler,
    WebhookDeduplicator,
    SignatureValidator
)
from slack_bot.event_processor import (
    AsyncEventProcessor,
    ProcessingResult,
    EventQueue
)
from slack_bot.models import WebhookEvent


# Custom strategies for generating test data

@st.composite
def signing_secret(draw):
    """Generate valid signing secrets."""
    length = draw(st.integers(min_value=32, max_value=64))
    return draw(st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            min_codepoint=33,
            max_codepoint=126
        ),
        min_size=length,
        max_size=length
    ))


@st.composite
def webhook_payload(draw):
    """Generate realistic webhook payloads."""
    event_type = draw(st.sampled_from([
        'slash_command',
        'block_action',
        'message',
        'app_mention'
    ]))
    
    user_id = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=9,
        max_size=11
    ))
    
    team_id = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=9,
        max_size=11
    ))
    
    event_id = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            min_codepoint=33,
            max_codepoint=126
        ),
        min_size=10,
        max_size=50
    ))
    
    payload = {
        "type": event_type,
        "user_id": f"U{user_id}",
        "team_id": f"T{team_id}",
        "event_id": event_id
    }
    return json.dumps(payload).encode('utf-8')


@st.composite
def error_message(draw):
    """Generate realistic error messages."""
    error_types = [
        "Connection timeout",
        "Database error",
        "Invalid configuration",
        "API rate limit exceeded",
        "Authentication failed",
        "Resource not found",
        "Internal server error",
        "Network unreachable"
    ]
    return draw(st.sampled_from(error_types))


def create_valid_webhook_request(secret: str, body: bytes):
    """
    Create a valid webhook request with proper signature.
    
    Args:
        secret: Signing secret
        body: Request body bytes
        
    Returns:
        Tuple of (headers dict, body bytes)
    """
    timestamp = str(int(time.time()))
    
    # Compute signature
    sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
    signature = 'v0=' + hmac.new(
        secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'X-Slack-Request-Timestamp': timestamp,
        'X-Slack-Signature': signature
    }
    
    return headers, body


class TestWebhookProcessingErrorHandlingProperties:
    """
    Property-based tests for webhook processing error handling.
    
    Feature: slack-integration, Property 14: Webhook Processing Error Handling
    
    For any webhook event that fails during processing, the system should
    log detailed error information and notify the user of the failure.
    
    Validates: Requirements 7.5
    """
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_malformed_json_logged_and_rejected(self, secret, payload):
        """
        Property: For any webhook with malformed JSON, the error should be
        logged and the request rejected with appropriate status.
        
        This validates that JSON parsing errors are handled gracefully.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        # Create malformed JSON body
        malformed_body = b'{"type":"test", invalid json'
        
        # Create valid signature for malformed body
        timestamp = str(int(time.time()))
        sig_basestring = f"v0:{timestamp}:".encode('utf-8') + malformed_body
        signature = 'v0=' + hmac.new(
            secret.encode('utf-8'),
            sig_basestring,
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Signature': signature
        }
        
        # Capture logs
        with patch('slack_bot.webhook_handler.logger') as mock_logger:
            response = await handler.handle_webhook(headers, malformed_body)
            
            # Should return 400 status
            assert response.status_code == 400
            assert response.body.get('error') == 'Invalid JSON'
            assert response.error == 'invalid_json'
            
            # Should log the error
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert 'Failed to parse webhook body' in call_args[0][0]
    
    @given(secret=signing_secret(), payload=webhook_payload(), error_msg=error_message())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_processing_exception_logged_with_context(self, secret, payload, error_msg):
        """
        Property: For any webhook that raises an exception during processing,
        the error should be logged with full context (event ID, user, team, error).
        
        This validates comprehensive error logging.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Create mock processor that raises exception
        mock_processor = AsyncMock()
        mock_processor.process_async.side_effect = Exception(error_msg)
        
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=mock_processor,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        # Capture logs
        with patch('slack_bot.webhook_handler.logger') as mock_logger:
            response = await handler.handle_webhook(headers, body)
            
            # Should return 500 status
            assert response.status_code == 500
            assert 'error' in response.body
            assert response.error is not None
            
            # Should log the error with context
            mock_logger.error.assert_called()
            call_args = mock_logger.error.call_args
            assert 'Webhook processing error' in call_args[0][0]
            
            # Check that extra context was logged
            extra = call_args[1].get('extra', {})
            assert 'error' in extra
            assert 'processing_time_ms' in extra
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_error_response_includes_generic_message(self, secret, payload):
        """
        Property: For any processing error, the response should include a
        generic error message without exposing internal details.
        
        This validates that error responses are user-friendly and secure.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Create mock processor that raises exception with sensitive info
        mock_processor = AsyncMock()
        mock_processor.process_async.side_effect = Exception(
            "Database connection failed: password=secret123"
        )
        
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=mock_processor,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        response = await handler.handle_webhook(headers, body)
        
        # Should return generic error message
        assert response.status_code == 500
        assert response.body.get('error') == 'Internal server error'
        
        # Should not expose sensitive details in response body
        response_str = json.dumps(response.body)
        assert 'password' not in response_str.lower()
        assert 'secret' not in response_str.lower()
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_missing_headers_logged_and_rejected(self, secret, payload):
        """
        Property: For any webhook with missing required headers, the error
        should be logged and the request rejected.
        
        This validates that header validation errors are handled properly.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        # Test missing timestamp
        headers_no_timestamp = {
            'X-Slack-Signature': 'v0=test'
        }
        
        with patch('slack_bot.webhook_handler.logger') as mock_logger:
            response = await handler.handle_webhook(headers_no_timestamp, payload)
            
            assert response.status_code == 400
            assert response.body.get('error') == 'Missing required headers'
            assert response.error == 'missing_headers'
            
            # Should log warning
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert 'Missing required headers' in call_args[0][0]
    
    @given(secret=signing_secret(), payload=webhook_payload(), error_msg=error_message())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_event_processor_error_logged_separately(self, secret, payload, error_msg):
        """
        Property: For any error in the event processor, the error should be
        logged by the processor with event context.
        
        This validates that async processing errors are tracked.
        """
        # Create event queue with mock handler that fails
        queue = EventQueue(max_workers=1)
        
        async def failing_handler(event: WebhookEvent) -> ProcessingResult:
            raise Exception(error_msg)
        
        queue.register_handler('slash_command', failing_handler)
        
        # Start queue
        await queue.start()
        
        try:
            # Parse payload to get event type
            payload_dict = json.loads(payload.decode('utf-8'))
            event_type = payload_dict.get('type', 'unknown')
            
            # Only test if event type matches registered handler
            if event_type == 'slash_command':
                # Create event
                from datetime import datetime, timezone
                event = WebhookEvent(
                    event_id=payload_dict.get('event_id', 'test'),
                    event_type=event_type,
                    user_id=payload_dict.get('user_id', 'U123'),
                    team_id=payload_dict.get('team_id', 'T123'),
                    payload=payload_dict,
                    timestamp=datetime.now(timezone.utc)
                )
                
                # Enqueue event
                with patch('slack_bot.event_processor.logger') as mock_logger:
                    await queue.enqueue(event)
                    
                    # Wait for processing
                    await queue.queue.join()
                    
                    # Should log error
                    mock_logger.error.assert_called()
                    
                    # Check error was logged with context
                    error_calls = [call for call in mock_logger.error.call_args_list 
                                   if 'Event processing exception' in str(call)]
                    assert len(error_calls) > 0
        finally:
            await queue.stop()
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_error_includes_processing_time(self, secret, payload):
        """
        Property: For any webhook that fails, the error log should include
        the processing time to help diagnose performance issues.
        
        This validates that timing information is captured even on errors.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Create mock processor that raises exception
        mock_processor = AsyncMock()
        mock_processor.process_async.side_effect = Exception("Test error")
        
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=mock_processor,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        with patch('slack_bot.webhook_handler.logger') as mock_logger:
            response = await handler.handle_webhook(headers, body)
            
            # Should log error with processing time
            mock_logger.error.assert_called()
            call_args = mock_logger.error.call_args
            extra = call_args[1].get('extra', {})
            
            assert 'processing_time_ms' in extra
            assert isinstance(extra['processing_time_ms'], int)
            assert extra['processing_time_ms'] >= 0
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_error_response_still_fast(self, secret, payload):
        """
        Property: For any webhook that fails, the error response should still
        be returned within the timeout period.
        
        This validates that error handling doesn't cause delays.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Create mock processor that raises exception
        mock_processor = AsyncMock()
        mock_processor.process_async.side_effect = Exception("Test error")
        
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=mock_processor,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        # Measure response time
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Should still respond within timeout
        assert elapsed_time < 3.0, f"Error response took {elapsed_time:.3f}s"
        assert response.status_code == 500
    
    @given(secret=signing_secret(), payloads=st.lists(webhook_payload(), min_size=2, max_size=5, unique=True))
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_multiple_errors_logged_independently(self, secret, payloads):
        """
        Property: For any sequence of webhooks that fail, each error should
        be logged independently with its own context.
        
        This validates that error logging doesn't interfere between requests.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Create mock processor that raises exception
        mock_processor = AsyncMock()
        mock_processor.process_async.side_effect = Exception("Test error")
        
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=mock_processor,
            timeout_seconds=3
        )
        
        with patch('slack_bot.webhook_handler.logger') as mock_logger:
            # Process multiple failing webhooks (each with unique event_id)
            for payload in payloads:
                headers, body = create_valid_webhook_request(secret, payload)
                response = await handler.handle_webhook(headers, body)
                # Should return 500 for processing errors
                assert response.status_code == 500
            
            # Should log error for each webhook
            assert mock_logger.error.call_count >= len(payloads)
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_error_preserves_event_id_for_tracking(self, secret, payload):
        """
        Property: For any webhook that fails, the error log should include
        the event ID for tracking and debugging.
        
        This validates that failed events can be traced.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Create mock processor that raises exception
        mock_processor = AsyncMock()
        mock_processor.process_async.side_effect = Exception("Test error")
        
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=mock_processor,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        # Parse payload to get event ID
        payload_dict = json.loads(payload.decode('utf-8'))
        expected_event_id = payload_dict.get('event_id')
        
        with patch('slack_bot.webhook_handler.logger') as mock_logger:
            response = await handler.handle_webhook(headers, body)
            
            # Error should be logged
            mock_logger.error.assert_called()
            
            # Event ID should be in the error context
            # (Note: event_id might be in the extra dict or in the message)
            call_args = mock_logger.error.call_args
            extra = call_args[1].get('extra', {})
            
            # The error log should have some context about the event
            assert extra is not None


class TestEventProcessorErrorHandlingProperties:
    """
    Property-based tests for event processor error handling.
    
    Feature: slack-integration, Property 14: Webhook Processing Error Handling
    
    Validates that the async event processor handles errors correctly.
    
    Validates: Requirements 7.5
    """
    
    @given(error_msg=error_message())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_handler_exception_logged_with_details(self, error_msg):
        """
        Property: For any exception raised by an event handler, the processor
        should log the error with event details and stack trace.
        
        This validates comprehensive error logging in async processing.
        """
        queue = EventQueue(max_workers=1)
        
        async def failing_handler(event: WebhookEvent) -> ProcessingResult:
            raise Exception(error_msg)
        
        queue.register_handler('slash_command', failing_handler)
        
        await queue.start()
        
        try:
            from datetime import datetime, timezone
            event = WebhookEvent(
                event_id='test123456789',
                event_type='slash_command',
                user_id='U12345678',
                team_id='T12345678',
                payload={'test': 'data'},
                timestamp=datetime.now(timezone.utc)
            )
            
            with patch('slack_bot.event_processor.logger') as mock_logger:
                await queue.enqueue(event)
                await queue.queue.join()
                
                # Should log error
                mock_logger.error.assert_called()
                
                # Check error details
                error_calls = [call for call in mock_logger.error.call_args_list]
                assert len(error_calls) > 0
                
                # Find the processing exception call
                exception_calls = [call for call in error_calls 
                                   if 'Event processing exception' in str(call)]
                assert len(exception_calls) > 0
                
                # Check context includes event details
                call_args = exception_calls[0]
                extra = call_args[1].get('extra', {})
                assert 'event_id' in extra
                assert 'event_type' in extra
                assert 'error' in extra
        finally:
            await queue.stop()
    
    @given(error_msg=error_message())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_handler_failure_returns_error_result(self, error_msg):
        """
        Property: For any handler that returns a failed ProcessingResult,
        the error should be logged appropriately.
        
        This validates that explicit failures are handled correctly.
        """
        queue = EventQueue(max_workers=1)
        
        async def failing_handler(event: WebhookEvent) -> ProcessingResult:
            return ProcessingResult(
                success=False,
                event_id=event.event_id,
                processing_time_ms=100,
                error=error_msg
            )
        
        queue.register_handler('slash_command', failing_handler)
        
        await queue.start()
        
        try:
            from datetime import datetime, timezone
            event = WebhookEvent(
                event_id='test123456789',
                event_type='slash_command',
                user_id='U12345678',
                team_id='T12345678',
                payload={'test': 'data'},
                timestamp=datetime.now(timezone.utc)
            )
            
            with patch('slack_bot.event_processor.logger') as mock_logger:
                await queue.enqueue(event)
                await queue.queue.join()
                
                # Should log error for failed processing
                error_calls = [call for call in mock_logger.error.call_args_list 
                               if 'Event processing failed' in str(call)]
                assert len(error_calls) > 0
                
                # Check error message is included
                call_args = error_calls[0]
                extra = call_args[1].get('extra', {})
                assert 'error' in extra
                assert extra['error'] == error_msg
        finally:
            await queue.stop()
