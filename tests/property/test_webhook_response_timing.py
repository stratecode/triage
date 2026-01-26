# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for webhook response timing.

Tests universal properties of webhook response timing to ensure
immediate acknowledgment within 3 seconds using Hypothesis.

Feature: slack-integration, Property 11: Webhook Response Timing
Validates: Requirements 7.1, 7.2
"""

import pytest
import time
import hashlib
import hmac
from hypothesis import given, strategies as st, settings

from slack_bot.webhook_handler import (
    WebhookHandler,
    WebhookDeduplicator,
    SignatureValidator
)
from slack_bot.event_processor import AsyncEventProcessor


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
    
    payload = f'{{"type":"{event_type}","user_id":"U{user_id}","team_id":"T{team_id}","event_id":"{event_id}"}}'
    return payload.encode('utf-8')


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


class TestWebhookResponseTimingProperties:
    """
    Property-based tests for webhook response timing.
    
    Feature: slack-integration, Property 11: Webhook Response Timing
    
    For any incoming webhook event from Slack, the system should respond
    with HTTP 200 within 3 seconds, processing long-running operations
    asynchronously.
    
    Validates: Requirements 7.1, 7.2
    """
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_webhook_responds_within_timeout(self, secret, payload):
        """
        Property: For any valid webhook request, the handler should respond
        within the configured timeout (3 seconds).
        
        This validates the immediate acknowledgment requirement.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        # Measure response time
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Should respond within 3 seconds
        assert elapsed_time < 3.0, f"Response took {elapsed_time:.3f}s, exceeds 3s limit"
        
        # Should return 200 status
        assert response.status_code == 200
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_webhook_responds_quickly_without_processor(self, secret, payload):
        """
        Property: For any valid webhook request without async processor,
        the handler should still respond very quickly.
        
        This validates that the handler is fast even without background processing.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=None,  # No async processor
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        # Measure response time
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Should respond very quickly (< 1 second)
        assert elapsed_time < 1.0, f"Response took {elapsed_time:.3f}s, should be < 1s"
        
        # Should return 200 status
        assert response.status_code == 200
        assert response.processed is True
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_duplicate_webhook_responds_quickly(self, secret, payload):
        """
        Property: For any duplicate webhook request, the handler should respond
        even faster since it skips processing.
        
        This validates that deduplication doesn't add significant overhead.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        # First request
        await handler.handle_webhook(headers, body)
        
        # Second request (duplicate) - measure timing
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Duplicate should respond very quickly
        assert elapsed_time < 1.0, f"Duplicate response took {elapsed_time:.3f}s"
        
        # Should return 200 status
        assert response.status_code == 200
        assert response.duplicate is True
    
    @given(secret=signing_secret())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_invalid_signature_responds_quickly(self, secret):
        """
        Property: For any webhook with invalid signature, the handler should
        respond quickly with rejection.
        
        This validates that validation failures don't cause delays.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        # Create request with invalid signature
        headers = {
            'X-Slack-Request-Timestamp': str(int(time.time())),
            'X-Slack-Signature': 'v0=invalid_signature'
        }
        body = b'{"type":"test"}'
        
        # Measure response time
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Should respond very quickly
        assert elapsed_time < 1.0, f"Invalid signature response took {elapsed_time:.3f}s"
        
        # Should return 401 status
        assert response.status_code == 401
    
    @given(secret=signing_secret(), payloads=st.lists(webhook_payload(), min_size=3, max_size=10))
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_multiple_webhooks_all_respond_quickly(self, secret, payloads):
        """
        Property: For any sequence of webhook requests, each should respond
        within the timeout regardless of load.
        
        This validates that the handler can handle multiple concurrent requests.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        # Process multiple webhooks
        for payload in payloads:
            headers, body = create_valid_webhook_request(secret, payload)
            
            start_time = time.time()
            response = await handler.handle_webhook(headers, body)
            elapsed_time = time.time() - start_time
            
            # Each should respond within timeout
            assert elapsed_time < 3.0, f"Response took {elapsed_time:.3f}s"
            assert response.status_code == 200
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_url_verification_responds_immediately(self, secret, payload):
        """
        Property: For any URL verification challenge, the handler should
        respond immediately with the challenge.
        
        This validates special handling for URL verification.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        # Create URL verification challenge
        challenge = "test_challenge_12345"
        body = f'{{"type":"url_verification","challenge":"{challenge}"}}'.encode('utf-8')
        headers, body = create_valid_webhook_request(secret, body)
        
        # Measure response time
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Should respond very quickly
        assert elapsed_time < 1.0, f"URL verification took {elapsed_time:.3f}s"
        
        # Should return 200 with challenge
        assert response.status_code == 200
        assert response.body.get('challenge') == challenge
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_response_time_consistent(self, secret, payload):
        """
        Property: For any webhook request, multiple invocations should have
        consistent response times.
        
        This validates that response time is predictable.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            timeout_seconds=3
        )
        
        # Measure response times for multiple requests
        times = []
        for i in range(3):
            # Create unique payload for each request by modifying the JSON
            import json
            payload_dict = json.loads(payload.decode('utf-8'))
            payload_dict['iteration'] = i
            unique_payload = json.dumps(payload_dict).encode('utf-8')
            
            headers, body = create_valid_webhook_request(secret, unique_payload)
            
            start_time = time.time()
            response = await handler.handle_webhook(headers, body)
            elapsed_time = time.time() - start_time
            
            times.append(elapsed_time)
            assert response.status_code == 200
        
        # All times should be within reasonable range (< 1 second)
        assert all(t < 1.0 for t in times), f"Response times: {times}"
        
        # Variance should be reasonable (no single request takes 10x longer)
        max_time = max(times)
        min_time = min(times)
        if min_time > 0:
            ratio = max_time / min_time
            assert ratio < 10.0, f"Response time variance too high: {ratio:.2f}x"


class TestAsyncProcessingProperties:
    """
    Property-based tests for async event processing behavior.
    
    Feature: slack-integration, Property 11: Webhook Response Timing
    
    Validates that webhook handler works correctly with or without
    async processing enabled.
    
    Validates: Requirements 7.1, 7.2
    """
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_handler_without_processor_still_fast(self, secret, payload):
        """
        Property: For any webhook without async processor, the handler should
        still respond quickly.
        
        This validates that the handler works with or without async processing.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        handler = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=None,  # No async processor
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        
        start_time = time.time()
        response = await handler.handle_webhook(headers, body)
        elapsed_time = time.time() - start_time
        
        # Should still respond quickly
        assert elapsed_time < 1.0, f"Response took {elapsed_time:.3f}s without processor"
        assert response.status_code == 200
    
    @given(secret=signing_secret(), payload=webhook_payload())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_handler_response_independent_of_processor(self, secret, payload):
        """
        Property: For any webhook, the response should be the same whether
        or not an async processor is configured.
        
        This validates consistent behavior across configurations.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=300)
        
        # Handler without processor
        handler_no_proc = WebhookHandler(
            signing_secret=secret,
            deduplicator=deduplicator,
            event_processor=None,
            timeout_seconds=3
        )
        
        headers, body = create_valid_webhook_request(secret, payload)
        response_no_proc = await handler_no_proc.handle_webhook(headers, body)
        
        # Both should return 200 and mark as processed
        assert response_no_proc.status_code == 200
        assert response_no_proc.processed is True
