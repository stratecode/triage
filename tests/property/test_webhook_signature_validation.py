# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for webhook signature validation.

Tests universal properties of Slack webhook signature validation using
Hypothesis for comprehensive validation across many inputs.

Feature: slack-integration, Property 12: Webhook Signature Validation
Validates: Requirements 7.3
"""

import pytest
import time
import hashlib
import hmac
from hypothesis import given, strategies as st, assume, settings

from slack_bot.webhook_handler import SignatureValidator


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
def webhook_body(draw):
    """Generate realistic webhook request bodies."""
    # Generate JSON-like webhook payload
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
    
    body = f'{{"type":"{event_type}","user_id":"U{user_id}","team_id":"T{team_id}"}}'
    return body.encode('utf-8')


@st.composite
def valid_timestamp(draw):
    """Generate valid timestamps (within 5 minutes of current time)."""
    current_time = int(time.time())
    # Generate timestamp within ±4 minutes to ensure it's valid
    offset = draw(st.integers(min_value=-240, max_value=240))
    return str(current_time + offset)


@st.composite
def expired_timestamp(draw):
    """Generate expired timestamps (older than 5 minutes)."""
    current_time = int(time.time())
    # Generate timestamp older than 5 minutes (300 seconds)
    offset = draw(st.integers(min_value=301, max_value=3600))
    return str(current_time - offset)


def compute_signature(signing_secret: str, timestamp: str, body: bytes) -> str:
    """
    Compute valid Slack signature for testing.
    
    Args:
        signing_secret: Signing secret
        timestamp: Request timestamp
        body: Request body bytes
        
    Returns:
        Valid signature string
    """
    sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
    signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    return signature


class TestWebhookSignatureValidationProperties:
    """
    Property-based tests for webhook signature validation.
    
    Feature: slack-integration, Property 12: Webhook Signature Validation
    
    For any incoming webhook request, if the signature is invalid, the system
    should reject it with HTTP 401 without processing the payload.
    
    Validates: Requirements 7.3
    """
    
    @given(secret=signing_secret(), timestamp=valid_timestamp(), body=webhook_body())
    @settings(max_examples=100)
    def test_valid_signature_accepted(self, secret, timestamp, body):
        """
        Property: For any valid signature computed with the correct secret,
        timestamp, and body, validation should succeed.
        
        This validates that correctly signed webhooks are accepted.
        """
        validator = SignatureValidator(secret)
        signature = compute_signature(secret, timestamp, body)
        
        result = validator.validate_signature(timestamp, body, signature)
        
        assert result is True
    
    @given(
        secret=signing_secret(),
        wrong_secret=signing_secret(),
        timestamp=valid_timestamp(),
        body=webhook_body()
    )
    @settings(max_examples=100)
    def test_wrong_secret_rejected(self, secret, wrong_secret, timestamp, body):
        """
        Property: For any signature computed with a different secret,
        validation should fail.
        
        This validates that signatures from unauthorized sources are rejected.
        """
        # Ensure secrets are actually different
        assume(secret != wrong_secret)
        
        validator = SignatureValidator(secret)
        # Compute signature with wrong secret
        wrong_signature = compute_signature(wrong_secret, timestamp, body)
        
        result = validator.validate_signature(timestamp, body, wrong_signature)
        
        assert result is False
    
    @given(secret=signing_secret(), timestamp=valid_timestamp(), body=webhook_body())
    @settings(max_examples=100)
    def test_tampered_body_rejected(self, secret, timestamp, body):
        """
        Property: For any webhook with a valid signature but tampered body,
        validation should fail.
        
        This validates that body tampering is detected.
        """
        validator = SignatureValidator(secret)
        signature = compute_signature(secret, timestamp, body)
        
        # Tamper with body
        tampered_body = body + b"TAMPERED"
        
        result = validator.validate_signature(timestamp, body=tampered_body, signature=signature)
        
        assert result is False
    
    @given(secret=signing_secret(), timestamp=expired_timestamp(), body=webhook_body())
    @settings(max_examples=100)
    def test_expired_timestamp_rejected(self, secret, timestamp, body):
        """
        Property: For any webhook with an expired timestamp (> 5 minutes old),
        validation should fail even with correct signature.
        
        This validates replay attack prevention.
        """
        validator = SignatureValidator(secret)
        signature = compute_signature(secret, timestamp, body)
        
        result = validator.validate_signature(timestamp, body, signature)
        
        assert result is False
    
    @given(secret=signing_secret(), body=webhook_body())
    @settings(max_examples=100)
    def test_future_timestamp_rejected(self, secret, body):
        """
        Property: For any webhook with a future timestamp (> 5 minutes ahead),
        validation should fail.
        
        This validates that future-dated requests are rejected.
        """
        # Generate timestamp more than 5 minutes in the future
        future_timestamp = str(int(time.time()) + 400)
        
        validator = SignatureValidator(secret)
        signature = compute_signature(secret, future_timestamp, body)
        
        result = validator.validate_signature(future_timestamp, body, signature)
        
        assert result is False
    
    @given(secret=signing_secret(), timestamp=valid_timestamp(), body=webhook_body())
    @settings(max_examples=100)
    def test_malformed_signature_rejected(self, secret, timestamp, body):
        """
        Property: For any webhook with a malformed signature format,
        validation should fail.
        
        This validates that signature format is enforced.
        """
        validator = SignatureValidator(secret)
        
        # Test various malformed signatures
        malformed_signatures = [
            "invalid",
            "v0=",
            "v1=abcdef123456",  # Wrong version
            "abcdef123456",  # Missing version prefix
            "",  # Empty signature
        ]
        
        for malformed_sig in malformed_signatures:
            result = validator.validate_signature(timestamp, body, malformed_sig)
            assert result is False
    
    @given(secret=signing_secret(), timestamp=valid_timestamp(), body=webhook_body())
    @settings(max_examples=100)
    def test_signature_case_sensitive(self, secret, timestamp, body):
        """
        Property: For any valid signature, changing the case should cause
        validation to fail.
        
        This validates that signature comparison is case-sensitive.
        """
        validator = SignatureValidator(secret)
        signature = compute_signature(secret, timestamp, body)
        
        # Change case of signature (after v0= prefix)
        if len(signature) > 3:
            case_changed = signature[:3] + signature[3:].upper()
            
            # Only test if case actually changed
            if case_changed != signature:
                result = validator.validate_signature(timestamp, body, case_changed)
                assert result is False
    
    @given(secret=signing_secret(), body=webhook_body())
    @settings(max_examples=100)
    def test_invalid_timestamp_format_rejected(self, secret, body):
        """
        Property: For any webhook with an invalid timestamp format,
        validation should fail.
        
        This validates that timestamp format is enforced.
        """
        validator = SignatureValidator(secret)
        
        # Test various invalid timestamp formats
        invalid_timestamps = [
            "not_a_number",
            "12.34",  # Float instead of int
            "",  # Empty
            "abc123",  # Mixed alphanumeric
        ]
        
        for invalid_ts in invalid_timestamps:
            # Compute signature with invalid timestamp
            signature = compute_signature(secret, invalid_ts, body)
            result = validator.validate_signature(invalid_ts, body, signature)
            assert result is False
    
    @given(
        secret=signing_secret(),
        timestamp1=valid_timestamp(),
        timestamp2=valid_timestamp(),
        body=webhook_body()
    )
    @settings(max_examples=100)
    def test_signature_timestamp_binding(self, secret, timestamp1, timestamp2, body):
        """
        Property: For any signature computed with one timestamp, using it
        with a different timestamp should fail validation.
        
        This validates that signatures are bound to specific timestamps.
        """
        assume(timestamp1 != timestamp2)
        
        validator = SignatureValidator(secret)
        
        # Compute signature with timestamp1
        signature = compute_signature(secret, timestamp1, body)
        
        # Try to validate with timestamp2
        result = validator.validate_signature(timestamp2, body, signature)
        
        assert result is False
    
    @given(secret=signing_secret(), timestamp=valid_timestamp(), body=webhook_body())
    @settings(max_examples=100)
    def test_signature_validation_idempotent(self, secret, timestamp, body):
        """
        Property: For any webhook, validating the same signature multiple times
        should produce the same result.
        
        This validates that validation is deterministic and idempotent.
        """
        validator = SignatureValidator(secret)
        signature = compute_signature(secret, timestamp, body)
        
        # Validate multiple times
        result1 = validator.validate_signature(timestamp, body, signature)
        result2 = validator.validate_signature(timestamp, body, signature)
        result3 = validator.validate_signature(timestamp, body, signature)
        
        assert result1 == result2 == result3 == True


class TestTimestampValidationProperties:
    """
    Property-based tests for timestamp validation.
    
    Feature: slack-integration, Property 12: Webhook Signature Validation
    
    Validates the 5-minute window for webhook timestamps.
    
    Validates: Requirements 7.3
    """
    
    @given(secret=signing_secret())
    @settings(max_examples=50)
    def test_current_timestamp_valid(self, secret):
        """
        Property: For any webhook with the current timestamp,
        validation should succeed.
        
        This validates that current requests are accepted.
        """
        validator = SignatureValidator(secret)
        current_timestamp = str(int(time.time()))
        
        # Just test timestamp validation, not full signature
        result = validator._validate_timestamp(current_timestamp)
        
        assert result is True
    
    @given(secret=signing_secret())
    @settings(max_examples=50)
    def test_timestamp_within_window_valid(self, secret):
        """
        Property: For any timestamp within 5 minutes of current time,
        validation should succeed.
        
        This validates the 5-minute acceptance window.
        """
        validator = SignatureValidator(secret)
        
        # Test timestamps at various points within the window
        current_time = int(time.time())
        
        for offset in [-299, -150, 0, 150, 299]:
            timestamp = str(current_time + offset)
            result = validator._validate_timestamp(timestamp)
            assert result is True
    
    @given(secret=signing_secret())
    @settings(max_examples=50)
    def test_timestamp_outside_window_invalid(self, secret):
        """
        Property: For any timestamp outside the 5-minute window,
        validation should fail.
        
        This validates that old and future requests are rejected.
        """
        validator = SignatureValidator(secret)
        current_time = int(time.time())
        
        # Test timestamps outside the window
        for offset in [-301, -600, 301, 600]:
            timestamp = str(current_time + offset)
            result = validator._validate_timestamp(timestamp)
            assert result is False
