# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for webhook handler security features.

Tests signature validation with invalid signatures, timestamp validation,
and webhook processing edge cases.

Validates: Requirements 12.4
"""

import pytest
import time
import hashlib
import hmac
from datetime import datetime, timezone

from slack_bot.webhook_handler import (
    SignatureValidator,
    WebhookDeduplicator,
    WebhookHandler,
    WebhookResponse
)


class TestSignatureValidator:
    """Test webhook signature validation."""
    
    @pytest.fixture
    def validator(self):
        """Create signature validator for testing."""
        return SignatureValidator(signing_secret="test_signing_secret_12345")
    
    def _compute_valid_signature(self, timestamp: str, body: bytes, secret: str) -> str:
        """Helper to compute valid signature for testing."""
        sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
        signature = 'v0=' + hmac.new(
            secret.encode('utf-8'),
            sig_basestring,
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def test_valid_signature_accepted(self, validator):
        """Test that valid signature is accepted."""
        timestamp = str(int(time.time()))
        body = b'{"type":"event_callback","event":{"type":"message"}}'
        signature = self._compute_valid_signature(
            timestamp,
            body,
            "test_signing_secret_12345"
        )
        
        result = validator.validate_signature(timestamp, body, signature)
        assert result is True
    
    def test_invalid_signature_rejected(self, validator):
        """Test that invalid signature is rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"event_callback"}'
        signature = "v0=invalid_signature_hash"
        
        result = validator.validate_signature(timestamp, body, signature)
        assert result is False
    
    def test_wrong_secret_rejected(self, validator):
        """Test that signature with wrong secret is rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"event_callback"}'
        
        # Compute signature with different secret
        signature = self._compute_valid_signature(
            timestamp,
            body,
            "wrong_secret"
        )
        
        result = validator.validate_signature(timestamp, body, signature)
        assert result is False
    
    def test_tampered_body_rejected(self, validator):
        """Test that tampered body is rejected."""
        timestamp = str(int(time.time()))
        original_body = b'{"type":"event_callback","amount":100}'
        
        # Compute signature for original body
        signature = self._compute_valid_signature(
            timestamp,
            original_body,
            "test_signing_secret_12345"
        )
        
        # Tamper with body
        tampered_body = b'{"type":"event_callback","amount":999}'
        
        result = validator.validate_signature(timestamp, tampered_body, signature)
        assert result is False
    
    def test_old_timestamp_rejected(self, validator):
        """Test that old timestamp is rejected (replay attack prevention)."""
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        body = b'{"type":"event_callback"}'
        signature = self._compute_valid_signature(
            old_timestamp,
            body,
            "test_signing_secret_12345"
        )
        
        result = validator.validate_signature(old_timestamp, body, signature)
        assert result is False
    
    def test_future_timestamp_rejected(self, validator):
        """Test that future timestamp is rejected."""
        # Timestamp from 10 minutes in the future
        future_timestamp = str(int(time.time()) + 600)
        body = b'{"type":"event_callback"}'
        signature = self._compute_valid_signature(
            future_timestamp,
            body,
            "test_signing_secret_12345"
        )
        
        result = validator.validate_signature(future_timestamp, body, signature)
        assert result is False
    
    def test_malformed_timestamp_rejected(self, validator):
        """Test that malformed timestamp is rejected."""
        body = b'{"type":"event_callback"}'
        signature = "v0=somehash"
        
        # Test various malformed timestamps
        assert validator.validate_signature("not_a_number", body, signature) is False
        assert validator.validate_signature("", body, signature) is False
        assert validator.validate_signature("12.34", body, signature) is False
    
    def test_missing_signature_prefix_rejected(self, validator):
        """Test that signature without v0= prefix is rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"event_callback"}'
        
        # Compute valid hash but without v0= prefix
        sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
        signature_hash = hmac.new(
            "test_signing_secret_12345".encode('utf-8'),
            sig_basestring,
            hashlib.sha256
        ).hexdigest()
        
        result = validator.validate_signature(timestamp, body, signature_hash)
        assert result is False
    
    def test_empty_signature_rejected(self, validator):
        """Test that empty signature is rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"event_callback"}'
        
        result = validator.validate_signature(timestamp, body, "")
        assert result is False
    
    def test_signature_validation_exception_handling(self, validator):
        """Test that exceptions during validation return False."""
        # Pass None as body to trigger exception
        result = validator.validate_signature(str(int(time.time())), None, "v0=hash")
        assert result is False


class TestWebhookDeduplicator:
    """Test webhook deduplication."""
    
    @pytest.mark.asyncio
    async def test_first_event_not_duplicate(self):
        """Test that first occurrence of event is not a duplicate."""
        deduplicator = WebhookDeduplicator()
        
        is_dup = await deduplicator.is_duplicate("event_123")
        assert is_dup is False
    
    @pytest.mark.asyncio
    async def test_second_event_is_duplicate(self):
        """Test that second occurrence of event is a duplicate."""
        deduplicator = WebhookDeduplicator()
        
        await deduplicator.mark_processed("event_123")
        is_dup = await deduplicator.is_duplicate("event_123")
        
        assert is_dup is True
    
    @pytest.mark.asyncio
    async def test_different_events_not_duplicates(self):
        """Test that different events are not duplicates."""
        deduplicator = WebhookDeduplicator()
        
        await deduplicator.mark_processed("event_123")
        is_dup = await deduplicator.is_duplicate("event_456")
        
        assert is_dup is False
    
    @pytest.mark.asyncio
    async def test_expired_event_not_duplicate(self):
        """Test that expired events are cleaned up."""
        # Use very short TTL for testing
        deduplicator = WebhookDeduplicator(ttl_seconds=1)
        
        await deduplicator.mark_processed("event_123")
        
        # Wait for TTL to expire
        import asyncio
        await asyncio.sleep(1.1)
        
        # Should not be duplicate after expiry
        is_dup = await deduplicator.is_duplicate("event_123")
        assert is_dup is False


class TestWebhookHandler:
    """Test webhook handler security features."""
    
    @pytest.fixture
    def handler(self):
        """Create webhook handler for testing."""
        deduplicator = WebhookDeduplicator()
        return WebhookHandler(
            signing_secret="test_signing_secret_12345",
            deduplicator=deduplicator
        )
    
    def _compute_valid_signature(self, timestamp: str, body: bytes) -> str:
        """Helper to compute valid signature."""
        sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
        signature = 'v0=' + hmac.new(
            "test_signing_secret_12345".encode('utf-8'),
            sig_basestring,
            hashlib.sha256
        ).hexdigest()
        return signature
    
    @pytest.mark.asyncio
    async def test_missing_timestamp_header_rejected(self, handler):
        """Test that request without timestamp header is rejected."""
        body = b'{"type":"event_callback"}'
        headers = {
            'X-Slack-Signature': 'v0=somehash'
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 400
        assert response.error == 'missing_headers'
    
    @pytest.mark.asyncio
    async def test_missing_signature_header_rejected(self, handler):
        """Test that request without signature header is rejected."""
        body = b'{"type":"event_callback"}'
        headers = {
            'X-Slack-Request-Timestamp': str(int(time.time()))
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 400
        assert response.error == 'missing_headers'
    
    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self, handler):
        """Test that request with invalid signature is rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"event_callback"}'
        headers = {
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Signature': 'v0=invalid_signature'
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 401
        assert response.error == 'invalid_signature'
    
    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self, handler):
        """Test that request with valid signature is accepted."""
        timestamp = str(int(time.time()))
        body = b'{"type":"slash_command","event_id":"evt_123","user_id":"U12345ABCD","team_id":"T12345ABCD"}'
        signature = self._compute_valid_signature(timestamp, body)
        
        headers = {
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Signature': signature
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 200
        assert response.processed is True
    
    @pytest.mark.asyncio
    async def test_url_verification_challenge(self, handler):
        """Test URL verification challenge response."""
        timestamp = str(int(time.time()))
        body = b'{"type":"url_verification","challenge":"test_challenge_123"}'
        signature = self._compute_valid_signature(timestamp, body)
        
        headers = {
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Signature': signature
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 200
        assert response.body['challenge'] == 'test_challenge_123'
        assert response.processed is True
    
    @pytest.mark.asyncio
    async def test_duplicate_event_rejected(self, handler):
        """Test that duplicate events are rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"slash_command","event_id":"evt_123","user_id":"U12345ABCD","team_id":"T12345ABCD"}'
        signature = self._compute_valid_signature(timestamp, body)
        
        headers = {
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Signature': signature
        }
        
        # First request should succeed
        response1 = await handler.handle_webhook(headers, body)
        assert response1.status_code == 200
        assert response1.processed is True
        assert response1.duplicate is False
        
        # Second request should be marked as duplicate
        response2 = await handler.handle_webhook(headers, body)
        assert response2.status_code == 200
        assert response2.duplicate is True
    
    @pytest.mark.asyncio
    async def test_invalid_json_rejected(self, handler):
        """Test that invalid JSON body is rejected."""
        timestamp = str(int(time.time()))
        body = b'invalid json {'
        signature = self._compute_valid_signature(timestamp, body)
        
        headers = {
            'X-Slack-Request-Timestamp': timestamp,
            'X-Slack-Signature': signature
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 400
        assert response.error == 'invalid_json'
    
    @pytest.mark.asyncio
    async def test_old_timestamp_rejected(self, handler):
        """Test that old timestamp is rejected."""
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        body = b'{"type":"event_callback"}'
        signature = self._compute_valid_signature(old_timestamp, body)
        
        headers = {
            'X-Slack-Request-Timestamp': old_timestamp,
            'X-Slack-Signature': signature
        }
        
        response = await handler.handle_webhook(headers, body)
        
        assert response.status_code == 401
        assert response.error == 'invalid_signature'
