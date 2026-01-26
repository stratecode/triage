# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for error scenarios.

Tests API unavailable handling, rate limit handling, and invalid token handling.

**Validates: Requirements 11.1, 11.4**
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from slack_sdk.errors import SlackApiError

from slack_bot.triage_api_client import TriageAPIClient, TriageAPIError
from slack_bot.slack_api_client import SlackAPIClient, SlackAPIRetryError
from slack_bot.retry_queue import RetryQueue, MessageType
from slack_bot.config import SlackBotConfig


@pytest.fixture
def test_config():
    """Create test configuration."""
    return SlackBotConfig(
        slack_bot_token="xoxb-test-token",
        slack_signing_secret="test-secret",
        slack_client_id="test-client-id",
        slack_client_secret="test-client-secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test-token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="a" * 32,
        max_retries=3
    )


# Test API unavailable handling
@pytest.mark.asyncio
async def test_triage_api_unavailable_returns_503_error(test_config):
    """
    Test that TrIAge API unavailable (503) is handled correctly.
    
    Validates: Requirements 11.1
    """
    client = TriageAPIClient(test_config)
    
    # Mock HTTP client to return 503
    with patch.object(client, '_client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        
        mock_client.request = AsyncMock(return_value=mock_response)
        
        # Attempt API call
        with pytest.raises(TriageAPIError) as exc_info:
            await client._make_request("GET", "/test")
        
        # Verify error details
        assert exc_info.value.status_code == 503
        assert "Service Unavailable" in exc_info.value.response_body


@pytest.mark.asyncio
async def test_triage_api_unavailable_retries_before_failing(test_config):
    """
    Test that TrIAge API unavailable triggers retries.
    
    Validates: Requirements 11.1, 11.4
    """
    client = TriageAPIClient(test_config)
    
    # Track number of attempts
    attempt_count = 0
    
    async def mock_request(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        return mock_response
    
    with patch.object(client, '_client') as mock_client:
        mock_client.request = mock_request
        
        # Attempt API call
        with pytest.raises(TriageAPIError):
            await client._make_request("GET", "/test")
        
        # Verify retries occurred
        expected_attempts = test_config.max_retries + 1
        assert attempt_count == expected_attempts, \
            f"Expected {expected_attempts} attempts for 503 error"


@pytest.mark.asyncio
async def test_slack_api_unavailable_retries_before_failing(test_config):
    """
    Test that Slack API unavailable triggers retries.
    
    Validates: Requirements 11.1, 11.4
    """
    client = SlackAPIClient(test_config)
    
    # Create 503 error
    response = Mock()
    response.status_code = 503
    response.get = Mock(return_value="service_unavailable")
    response.headers = {}
    
    error = SlackApiError("Service unavailable", response)
    
    # Track attempts
    attempt_count = 0
    
    async def mock_method(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise error
    
    # Attempt API call
    with pytest.raises(SlackAPIRetryError):
        await client._retry_api_call(mock_method, "test_method")
    
    # Verify retries
    expected_attempts = test_config.max_retries + 1
    assert attempt_count == expected_attempts


# Test rate limit handling
@pytest.mark.asyncio
async def test_triage_api_rate_limit_retries_with_backoff(test_config):
    """
    Test that TrIAge API rate limit (429) triggers retry with backoff.
    
    Validates: Requirements 11.4
    """
    client = TriageAPIClient(test_config)
    
    # Track sleep calls
    sleep_calls = []
    
    async def mock_sleep(duration):
        sleep_calls.append(duration)
    
    # Mock to fail once with 429, then succeed
    attempt_count = 0
    
    async def mock_request(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        mock_response = Mock()
        if attempt_count == 1:
            mock_response.status_code = 429
            mock_response.text = "Rate limited"
        else:
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={"ok": True})
        
        return mock_response
    
    with patch.object(client, '_client') as mock_client:
        mock_client.request = mock_request
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            # Attempt API call
            response = await client._make_request("GET", "/test")
            
            # Verify success after retry
            assert response.status_code == 200
            
            # Verify backoff was applied
            assert len(sleep_calls) == 1
            assert sleep_calls[0] > 0


@pytest.mark.asyncio
async def test_slack_api_rate_limit_respects_retry_after(test_config):
    """
    Test that Slack API rate limit respects Retry-After header.
    
    Validates: Requirements 11.4
    """
    client = SlackAPIClient(test_config)
    
    # Create rate limit error with Retry-After
    response = Mock()
    response.status_code = 429
    response.get = Mock(return_value="rate_limited")
    response.headers = {"Retry-After": "60"}
    
    error = SlackApiError("Rate limited", response)
    
    # Track sleep calls
    sleep_calls = []
    
    async def mock_sleep(duration):
        sleep_calls.append(duration)
    
    # Mock to fail once then succeed
    attempt_count = 0
    
    async def mock_method(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count == 1:
            raise error
        else:
            return {"ok": True}
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        # Attempt API call
        result = await client._retry_api_call(mock_method, "test_method")
        
        # Verify success
        assert result["ok"] is True
        
        # Verify Retry-After was respected
        assert len(sleep_calls) == 1
        assert sleep_calls[0] >= 60  # Should be at least Retry-After value


# Test invalid token handling
@pytest.mark.asyncio
async def test_triage_api_invalid_token_fails_immediately(test_config):
    """
    Test that TrIAge API invalid token (401) fails without retry.
    
    Validates: Requirements 11.4
    """
    client = TriageAPIClient(test_config)
    
    # Track attempts
    attempt_count = 0
    
    async def mock_request(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        return mock_response
    
    with patch.object(client, '_client') as mock_client:
        mock_client.request = mock_request
        
        # Attempt API call
        with pytest.raises(TriageAPIError) as exc_info:
            await client._make_request("GET", "/test")
        
        # Verify no retries (only 1 attempt)
        assert attempt_count == 1
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_slack_api_invalid_token_fails_immediately(test_config):
    """
    Test that Slack API invalid token fails without retry.
    
    Validates: Requirements 11.4
    """
    client = SlackAPIClient(test_config)
    
    # Create invalid auth error
    response = Mock()
    response.status_code = 401
    response.get = Mock(return_value="invalid_auth")
    response.headers = {}
    
    error = SlackApiError("Invalid auth", response)
    
    # Track attempts
    attempt_count = 0
    
    async def mock_method(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise error
    
    # Attempt API call
    with pytest.raises(SlackAPIRetryError):
        await client._retry_api_call(mock_method, "test_method")
    
    # Verify no retries
    assert attempt_count == 1


# Test retry queue for graceful degradation
@pytest.mark.asyncio
async def test_failed_messages_are_queued_for_retry(test_config):
    """
    Test that failed Slack messages are queued for retry.
    
    Validates: Requirements 11.1
    """
    queue = RetryQueue(test_config)
    await queue.connect()
    
    try:
        # Enqueue a failed message
        message_id = await queue.enqueue(
            message_type=MessageType.DAILY_PLAN,
            user_id="U123",
            team_id="T456",
            channel="C789",
            payload={"text": "Test message", "blocks": []}
        )
        
        # Verify message is in queue
        queue_size = await queue.get_queue_size()
        assert queue_size == 1
        
        # Get pending messages
        pending = await queue.get_pending_messages()
        assert len(pending) == 1
        assert pending[0].message_id == message_id
        
    finally:
        await queue.disconnect()


@pytest.mark.asyncio
async def test_retry_queue_respects_max_retries(test_config):
    """
    Test that retry queue removes messages after max retries.
    
    Validates: Requirements 11.1
    """
    queue = RetryQueue(test_config)
    await queue.connect()
    
    try:
        # Enqueue a message
        message_id = await queue.enqueue(
            message_type=MessageType.DAILY_PLAN,
            user_id="U123",
            team_id="T456",
            channel="C789",
            payload={"text": "Test message", "blocks": []}
        )
        
        # Mark as failed multiple times
        for i in range(6):  # Exceed max_retries
            await queue.mark_failure(message_id, f"Error {i}")
        
        # Verify message is removed after max retries
        pending = await queue.get_pending_messages()
        assert len(pending) == 0
        
    finally:
        await queue.disconnect()


@pytest.mark.asyncio
async def test_retry_queue_removes_expired_messages(test_config):
    """
    Test that retry queue removes messages older than 24 hours.
    
    Validates: Requirements 11.1
    """
    from datetime import datetime, timedelta
    
    queue = RetryQueue(test_config)
    await queue.connect()
    
    try:
        # Enqueue a message
        message_id = await queue.enqueue(
            message_type=MessageType.DAILY_PLAN,
            user_id="U123",
            team_id="T456",
            channel="C789",
            payload={"text": "Test message", "blocks": []}
        )
        
        # Manually update created_at to be old
        message_data = await queue.redis_client.hget(queue.queue_key, message_id)
        message = queue._deserialize_message(message_data)
        message.created_at = datetime.utcnow() - timedelta(hours=25)
        
        # Update in queue
        updated_data = queue._serialize_message(message)
        await queue.redis_client.hset(queue.queue_key, message_id, updated_data)
        
        # Get pending messages (should filter out expired)
        pending = await queue.get_pending_messages()
        assert len(pending) == 0
        
    finally:
        await queue.disconnect()


@pytest.mark.asyncio
async def test_successful_retry_removes_from_queue(test_config):
    """
    Test that successful retry removes message from queue.
    
    Validates: Requirements 11.1
    """
    queue = RetryQueue(test_config)
    await queue.connect()
    
    try:
        # Enqueue a message
        message_id = await queue.enqueue(
            message_type=MessageType.DAILY_PLAN,
            user_id="U123",
            team_id="T456",
            channel="C789",
            payload={"text": "Test message", "blocks": []}
        )
        
        # Mark as successful
        await queue.mark_success(message_id)
        
        # Verify message is removed
        queue_size = await queue.get_queue_size()
        assert queue_size == 0
        
    finally:
        await queue.disconnect()
