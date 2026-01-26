# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for Slack API retry behavior.

Feature: slack-integration, Property 24: Slack API Retry Behavior

**Validates: Requirements 11.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, Mock, patch
from slack_sdk.errors import SlackApiError

from slack_bot.slack_api_client import SlackAPIClient, SlackAPIRetryError
from slack_bot.config import SlackBotConfig


# Custom strategies
@st.composite
def slack_config(draw):
    """Generate valid SlackBotConfig for testing."""
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
        max_retries=draw(st.integers(min_value=1, max_value=5)),
        retry_backoff_base=draw(st.floats(min_value=1.5, max_value=3.0))
    )


@st.composite
def retryable_status_code(draw):
    """Generate retryable HTTP status codes."""
    return draw(st.sampled_from([429, 500, 502, 503, 504]))


@st.composite
def non_retryable_status_code(draw):
    """Generate non-retryable HTTP status codes."""
    return draw(st.sampled_from([400, 401, 403, 404]))


def create_slack_error(status_code: int, error_code: str = "internal_error"):
    """Create a mock SlackApiError."""
    response = Mock()
    response.status_code = status_code
    response.get = Mock(return_value=error_code)
    response.headers = {}
    
    error = SlackApiError("Test error", response)
    return error


# Feature: slack-integration, Property 24: Slack API Retry Behavior
@pytest.mark.asyncio
@given(
    config=slack_config(),
    status_code=retryable_status_code()
)
@settings(max_examples=20, deadline=None)
async def test_retryable_errors_are_retried(config, status_code):
    """
    Property 24: Slack API Retry Behavior
    
    For any Slack API call that fails with a retryable error,
    the system should retry with exponential backoff up to 3 attempts
    before giving up.
    
    Validates: Requirements 11.2
    """
    client = SlackAPIClient(config)
    
    # Create mock that always fails with retryable error
    error = create_slack_error(status_code)
    mock_method = AsyncMock(side_effect=error)
    
    # Track number of attempts
    attempt_count = 0
    
    async def counting_mock(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise error
    
    mock_method.side_effect = counting_mock
    
    # Attempt API call
    with pytest.raises(SlackAPIRetryError) as exc_info:
        await client._retry_api_call(
            mock_method,
            "test_method",
            channel="C123",
            text="test"
        )
    
    # Verify retry behavior
    expected_attempts = config.max_retries + 1
    assert attempt_count == expected_attempts, \
        f"Expected {expected_attempts} attempts, got {attempt_count}"
    
    # Verify error contains attempt count
    assert exc_info.value.attempts == expected_attempts


# Feature: slack-integration, Property 24: Slack API Retry Behavior
@pytest.mark.asyncio
@given(
    config=slack_config(),
    status_code=non_retryable_status_code()
)
@settings(max_examples=20, deadline=None)
async def test_non_retryable_errors_fail_immediately(config, status_code):
    """
    Property 24: Slack API Retry Behavior
    
    For any Slack API call that fails with a non-retryable error,
    the system should fail immediately without retrying.
    
    Validates: Requirements 11.2
    """
    client = SlackAPIClient(config)
    
    # Create mock that fails with non-retryable error
    error = create_slack_error(status_code, "invalid_auth")
    mock_method = AsyncMock(side_effect=error)
    
    # Track number of attempts
    attempt_count = 0
    
    async def counting_mock(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise error
    
    mock_method.side_effect = counting_mock
    
    # Attempt API call
    with pytest.raises(SlackAPIRetryError):
        await client._retry_api_call(
            mock_method,
            "test_method",
            channel="C123",
            text="test"
        )
    
    # Verify no retries (only 1 attempt)
    assert attempt_count == 1, \
        f"Non-retryable error should not be retried, got {attempt_count} attempts"


# Feature: slack-integration, Property 24: Slack API Retry Behavior
@pytest.mark.asyncio
@given(
    config=slack_config(),
    success_on_attempt=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=20, deadline=None)
async def test_successful_retry_stops_retrying(config, success_on_attempt):
    """
    Property 24: Slack API Retry Behavior
    
    For any Slack API call that succeeds after N retries,
    the system should stop retrying and return the successful response.
    
    Validates: Requirements 11.2
    """
    assume(success_on_attempt <= config.max_retries + 1)
    
    client = SlackAPIClient(config)
    
    # Track attempts
    attempt_count = 0
    
    async def mock_method(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < success_on_attempt:
            # Fail with retryable error
            raise create_slack_error(503)
        else:
            # Succeed
            return {"ok": True, "channel": "C123"}
    
    # Attempt API call
    result = await client._retry_api_call(
        mock_method,
        "test_method",
        channel="C123",
        text="test"
    )
    
    # Verify success
    assert result["ok"] is True
    assert attempt_count == success_on_attempt, \
        f"Expected {success_on_attempt} attempts, got {attempt_count}"


# Feature: slack-integration, Property 24: Slack API Retry Behavior
@pytest.mark.asyncio
@given(
    config=slack_config(),
    retry_after=st.integers(min_value=1, max_value=60)
)
@settings(max_examples=20, deadline=None)
async def test_rate_limit_respects_retry_after_header(config, retry_after):
    """
    Property 24: Slack API Retry Behavior
    
    For any Slack API call that fails with rate limiting (429),
    the system should respect the Retry-After header if provided.
    
    Validates: Requirements 11.2
    """
    client = SlackAPIClient(config)
    
    # Create rate limit error with Retry-After header
    response = Mock()
    response.status_code = 429
    response.get = Mock(return_value="rate_limited")
    response.headers = {"Retry-After": str(retry_after)}
    
    error = SlackApiError("Rate limited", response)
    
    # Mock that fails once then succeeds
    attempt_count = 0
    
    async def mock_method(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count == 1:
            raise error
        else:
            return {"ok": True}
    
    # Patch sleep to verify backoff calculation
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        result = await client._retry_api_call(
            mock_method,
            "test_method",
            channel="C123",
            text="test"
        )
        
        # Verify success
        assert result["ok"] is True
        
        # Verify sleep was called with value based on retry_after
        assert mock_sleep.called
        sleep_time = mock_sleep.call_args[0][0]
        
        # Sleep time should be retry_after + jitter (10%)
        assert sleep_time >= retry_after
        assert sleep_time <= retry_after * 1.1


# Feature: slack-integration, Property 24: Slack API Retry Behavior
@pytest.mark.asyncio
@given(
    config=slack_config()
)
@settings(max_examples=20, deadline=None)
async def test_exponential_backoff_increases_wait_time(config):
    """
    Property 24: Slack API Retry Behavior
    
    For any sequence of retries, the wait time between attempts
    should increase exponentially.
    
    Validates: Requirements 11.2
    """
    client = SlackAPIClient(config)
    
    # Create retryable error
    error = create_slack_error(503)
    
    # Mock that always fails
    mock_method = AsyncMock(side_effect=error)
    
    # Track sleep times
    sleep_times = []
    
    async def mock_sleep(duration):
        sleep_times.append(duration)
    
    # Patch sleep to capture backoff times
    with patch('asyncio.sleep', side_effect=mock_sleep):
        with pytest.raises(SlackAPIRetryError):
            await client._retry_api_call(
                mock_method,
                "test_method",
                channel="C123",
                text="test"
            )
    
    # Verify exponential backoff
    if len(sleep_times) > 1:
        for i in range(len(sleep_times) - 1):
            # Each wait should be longer than the previous (accounting for jitter)
            # Base formula: backoff_base^attempt
            expected_min = config.retry_backoff_base ** i
            assert sleep_times[i] >= expected_min * 0.9, \
                f"Backoff at attempt {i} should be at least {expected_min * 0.9}, got {sleep_times[i]}"


# Feature: slack-integration, Property 24: Slack API Retry Behavior
@pytest.mark.asyncio
@given(
    config=slack_config()
)
@settings(max_examples=20, deadline=None)
async def test_jitter_is_applied_to_backoff(config):
    """
    Property 24: Slack API Retry Behavior
    
    For any retry attempt, jitter should be applied to the backoff time
    to prevent thundering herd problems.
    
    Validates: Requirements 11.2
    """
    client = SlackAPIClient(config)
    
    # Calculate backoff for same attempt multiple times
    backoff_times = [
        client._calculate_backoff(attempt=1)
        for _ in range(10)
    ]
    
    # Verify jitter causes variation
    # All values should be within expected range
    base_backoff = config.retry_backoff_base ** 1
    for backoff in backoff_times:
        assert backoff >= base_backoff, \
            f"Backoff {backoff} should be at least base {base_backoff}"
        assert backoff <= base_backoff * 1.1, \
            f"Backoff {backoff} should not exceed base * 1.1 ({base_backoff * 1.1})"
    
    # Verify there is some variation (not all identical)
    unique_values = len(set(backoff_times))
    assert unique_values > 1, \
        "Jitter should cause variation in backoff times"
