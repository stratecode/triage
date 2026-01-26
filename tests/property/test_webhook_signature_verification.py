# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for webhook signature verification (security requirement).

Feature: slack-integration, Property 30: Webhook Signature Verification

For any incoming webhook request, the system should validate the signature
using Slack's signing secret before processing.

Validates: Requirements 12.4

Note: This property is also validated by Property 12 (test_webhook_signature_validation.py).
This test file exists to explicitly link to the security requirement 12.4.
"""

import time
import hmac
import hashlib
from hypothesis import given, strategies as st, settings
from slack_bot.webhook_handler import SignatureValidator


# Feature: slack-integration, Property 30: Webhook Signature Verification
@settings(max_examples=100)
@given(
    signing_secret=st.text(min_size=32, max_size=64),
    body=st.binary(min_size=10, max_size=1000),
    timestamp_offset=st.integers(min_value=0, max_value=299)  # Within 5-minute window
)
def test_valid_signatures_are_accepted(signing_secret, body, timestamp_offset):
    """
    Property: For any valid webhook with correct signature and recent timestamp,
    the signature validator should accept it.
    
    Validates: Requirements 12.4
    """
    validator = SignatureValidator(signing_secret)
    
    # Generate valid timestamp (current time minus offset)
    timestamp = str(int(time.time()) - timestamp_offset)
    
    # Generate valid signature
    sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
    expected_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    
    # Validate signature
    is_valid = validator.validate_signature(timestamp, body, expected_signature)
    
    # Should accept valid signature
    assert is_valid, "Valid signature was rejected"


# Feature: slack-integration, Property 30: Webhook Signature Verification
@settings(max_examples=100)
@given(
    signing_secret=st.text(min_size=32, max_size=64),
    body=st.binary(min_size=10, max_size=1000),
    wrong_secret=st.text(min_size=32, max_size=64),
    timestamp_offset=st.integers(min_value=0, max_value=299)
)
def test_invalid_signatures_are_rejected(signing_secret, body, wrong_secret, timestamp_offset):
    """
    Property: For any webhook with incorrect signature, the signature
    validator should reject it.
    
    Validates: Requirements 12.4
    """
    # Ensure secrets are different
    if signing_secret == wrong_secret:
        wrong_secret = wrong_secret + "different"
    
    validator = SignatureValidator(signing_secret)
    
    # Generate timestamp
    timestamp = str(int(time.time()) - timestamp_offset)
    
    # Generate signature with WRONG secret
    sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
    invalid_signature = 'v0=' + hmac.new(
        wrong_secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    
    # Validate signature
    is_valid = validator.validate_signature(timestamp, body, invalid_signature)
    
    # Should reject invalid signature
    assert not is_valid, "Invalid signature was accepted"


# Feature: slack-integration, Property 30: Webhook Signature Verification
@settings(max_examples=100)
@given(
    signing_secret=st.text(min_size=32, max_size=64),
    body=st.binary(min_size=10, max_size=1000),
    timestamp_age=st.integers(min_value=301, max_value=3600)  # Older than 5 minutes
)
def test_old_timestamps_are_rejected(signing_secret, body, timestamp_age):
    """
    Property: For any webhook with timestamp older than 5 minutes,
    the signature validator should reject it (replay attack prevention).
    
    Validates: Requirements 12.4
    """
    validator = SignatureValidator(signing_secret)
    
    # Generate old timestamp
    timestamp = str(int(time.time()) - timestamp_age)
    
    # Generate valid signature for old timestamp
    sig_basestring = f"v0:{timestamp}:".encode('utf-8') + body
    signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    
    # Validate signature
    is_valid = validator.validate_signature(timestamp, body, signature)
    
    # Should reject due to old timestamp
    assert not is_valid, "Old timestamp was accepted (replay attack vulnerability)"


# Feature: slack-integration, Property 30: Webhook Signature Verification
@settings(max_examples=50)
@given(
    signing_secret=st.text(min_size=32, max_size=64),
    body=st.binary(min_size=10, max_size=1000),
    malformed_signature=st.text(min_size=10, max_size=100)
)
def test_malformed_signatures_are_rejected(signing_secret, body, malformed_signature):
    """
    Property: For any webhook with malformed signature (not in v0=hash format),
    the signature validator should reject it.
    
    Validates: Requirements 12.4
    """
    # Ensure malformed signature doesn't accidentally match valid format
    if malformed_signature.startswith('v0=') and len(malformed_signature) == 67:
        malformed_signature = "invalid_" + malformed_signature
    
    validator = SignatureValidator(signing_secret)
    
    # Generate valid timestamp
    timestamp = str(int(time.time()))
    
    # Validate malformed signature
    is_valid = validator.validate_signature(timestamp, body, malformed_signature)
    
    # Should reject malformed signature
    assert not is_valid, "Malformed signature was accepted"
