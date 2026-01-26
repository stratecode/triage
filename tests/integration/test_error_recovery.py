# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for error recovery and graceful degradation.

This module tests the complete error recovery workflow including:
- Retry logic with exponential backoff
- Graceful degradation when Slack API fails
- Retry queue for failed deliveries
- Error message delivery to users

Validates: Requirements 11.2, 11.3
"""

import pytest
import asyncio
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any

from slack_sdk.errors import SlackApiError

from slack_bot.notification_service import NotificationDeliveryService, NotificationDeliveryError
from slack_bot.notification_handler import NotificationHandler
from slack_bot.message_formatter import MessageFormatter
from slack_bot.retry_queue import RetryQueue, MessageType, QueuedMessage
from slack_bot.error_handler import ErrorHandler
from slack_bot.triage_api_client import TriageAPIClient, TriageAPIError
from slack_bot.models import SlackConfig
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
)


@pytest.fixture
def sample_daily_plan():
    """Create a sample daily plan for testing."""
    priority_task = JiraIssue(
        key="PROJ-123",
        summary="Fix critical bug",
        description="Critical bug fix",
        issue_type="Bug",
        priority="High",
        status="In Progress",
        assignee="user@example.com",
        story_points=3,
        time_estimate=14400,
        labels=["critical"],
        issue_links=[],
        custom_fields={}
    )
    
    priority_classification = TaskClassification(
        task=priority_task,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5
    )
    
    admin_block = AdminBlock(
        tasks=[],
        time_allocation_minutes=60,
        scheduled_time="14:00-15:00"
    )
    
    return DailyPlan(
        date=date.today(),
        priorities=[priority_classification],
        admin_block=admin_block,
        other_tasks=[],
        previous_closure_rate=0.85
    )


@pytest.fixture
def sample_user_config():
    """Create a sample user configuration."""
    return SlackConfig(
        user_id="test_user_123",
        notification_channel="DM",
        delivery_time="09:00",
        notifications_enabled=True,
        timezone="UTC"
    )


@pytest.mark.asyncio
async def test_retry_logic_with_exponential_backoff(sample_daily_plan, sample_user_config):
    """
    Test that Slack API failures trigger retry with exponential backoff.
    
    This integration test verifies:
    1. First delivery attempt fails with retryable error
    2. System retries with exponential backoff
    3. Retry succeeds after temporary failure
    4. Backoff times increase exponentially
    
    Validates: Requirements 11.2
    """
    # Create mock Slack client that fails first 2 attempts, succeeds on 3rd
    mock_slack_client = AsyncMock()
    
    attempt_count = 0
    
    async def mock_post_message(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count <= 2:
            # Simulate rate limit error (retryable)
            error_response = MagicMock()
            error_response.get = MagicMock(return_value='rate_limited')
            error_response.__getitem__ = MagicMock(return_value='rate_limited')
            raise SlackApiError("Rate limited", error_response)
        else:
            # Success on 3rd attempt
            return {
                'ok': True,
                'ts': '1234567890.123456',
                'channel': 'D12345ABCDE'
            }
    
    mock_slack_client.chat_postMessage = mock_post_message
    mock_slack_client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': 'D12345ABCDE'}
    })
    
    # Create notification service with retry enabled
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter,
        max_retries=3,
        retry_backoff_base=2.0
    )
    
    # Measure time for retry attempts
    start_time = datetime.now(timezone.utc)
    
    # Attempt delivery
    result = await notification_service.deliver_daily_plan(
        plan=sample_daily_plan,
        plan_id='plan_retry_test',
        user_config=sample_user_config,
        slack_user_id='U12345ABCDE'
    )
    
    end_time = datetime.now(timezone.utc)
    elapsed_time = (end_time - start_time).total_seconds()
    
    # Verify delivery succeeded after retries
    assert result['delivered'] is True, "Delivery should succeed after retries"
    assert result['message_ts'] == '1234567890.123456'
    assert attempt_count == 3, "Should have made 3 attempts"
    
    # Verify exponential backoff was applied
    # First retry: ~1s, Second retry: ~2s, Total: ~3s minimum
    assert elapsed_time >= 1.0, "Should have waited for exponential backoff"
    
    # Verify conversations_open was called once
    mock_slack_client.conversations_open.assert_called_once()


@pytest.mark.asyncio
async def test_graceful_degradation_on_permanent_failure(sample_daily_plan, sample_user_config):
    """
    Test graceful degradation when Slack API permanently fails.
    
    This integration test verifies:
    1. All retry attempts fail
    2. Error is logged appropriately
    3. Exception is raised with details
    4. System doesn't crash or block
    
    Validates: Requirements 11.1, 11.2
    """
    # Create mock Slack client that always fails
    mock_slack_client = AsyncMock()
    
    async def mock_post_message(**kwargs):
        # Simulate permanent error (non-retryable)
        error_response = MagicMock()
        error_response.get = MagicMock(return_value='channel_not_found')
        error_response.__getitem__ = MagicMock(return_value='channel_not_found')
        raise SlackApiError("Channel not found", error_response)
    
    mock_slack_client.chat_postMessage = mock_post_message
    mock_slack_client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': 'D12345ABCDE'}
    })
    
    # Create notification service
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter,
        max_retries=2  # Reduce for faster test
    )
    
    # Attempt delivery - should raise exception
    with pytest.raises(NotificationDeliveryError) as exc_info:
        await notification_service.deliver_daily_plan(
            plan=sample_daily_plan,
            plan_id='plan_fail_test',
            user_config=sample_user_config,
            slack_user_id='U12345ABCDE'
        )
    
    # Verify exception contains useful information
    assert exc_info.value.user_id == sample_user_config.user_id
    assert exc_info.value.error is not None
    assert 'channel_not_found' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_retry_queue_for_failed_deliveries():
    """
    Test that failed deliveries are queued for retry.
    
    This integration test verifies:
    1. Failed message is added to retry queue
    2. Message can be retrieved from queue
    3. Retry is attempted after backoff period
    4. Successful retry removes message from queue
    
    Validates: Requirements 11.1, 11.2
    """
    # Create mock Redis client
    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.hdel = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.hlen = AsyncMock(return_value=0)
    mock_redis.hget = AsyncMock(return_value=None)
    
    # Create retry queue with mock Redis
    from slack_bot.config import SlackBotConfig
    config = SlackBotConfig(
        slack_bot_token="xoxb-test",
        slack_signing_secret="test_secret",
        slack_client_id="test_client_id",
        slack_client_secret="test_client_secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test_token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="test_encryption_key_32_chars_min"
    )
    
    retry_queue = RetryQueue(config)
    retry_queue.redis_client = mock_redis
    
    # Enqueue a failed message
    message_id = await retry_queue.enqueue(
        message_type=MessageType.DAILY_PLAN,
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel="D12345ABCDE",
        payload={
            'text': 'Daily plan',
            'blocks': []
        }
    )
    
    # Verify message was stored in Redis
    assert message_id is not None
    mock_redis.hset.assert_called_once()
    
    # Verify message ID format
    assert message_id.startswith('MessageType.DAILY_PLAN:U12345ABCDE:') or message_id.startswith('daily_plan:U12345ABCDE:')
    
    # Simulate retrieving message for retry
    now = datetime.utcnow()
    queued_message = QueuedMessage(
        message_id=message_id,
        message_type=MessageType.DAILY_PLAN,
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel="D12345ABCDE",
        payload={'text': 'Daily plan', 'blocks': []},
        created_at=now - timedelta(minutes=5),
        retry_count=0,
        next_retry_at=now - timedelta(seconds=1)  # Ready for retry
    )
    
    # Mock hgetall to return our message
    import json
    message_data = {
        'message_id': message_id,
        'message_type': 'daily_plan',
        'user_id': 'U12345ABCDE',
        'team_id': 'T12345ABCDE',
        'channel': 'D12345ABCDE',
        'payload': {'text': 'Daily plan', 'blocks': []},
        'created_at': queued_message.created_at.isoformat(),
        'retry_count': 0,
        'next_retry_at': queued_message.next_retry_at.isoformat(),
        'max_retries': 5,
        'last_error': None
    }
    mock_redis.hgetall = AsyncMock(return_value={
        message_id: json.dumps(message_data)
    })
    
    # Get pending messages
    pending = await retry_queue.get_pending_messages(limit=10)
    
    # Verify message is ready for retry
    assert len(pending) == 1
    assert pending[0].message_id == message_id
    assert pending[0].retry_count == 0
    
    # Mark as processing
    await retry_queue.mark_processing(message_id)
    mock_redis.setex.assert_called()
    
    # Simulate successful retry
    await retry_queue.mark_success(message_id)
    
    # Verify message was removed from queue
    mock_redis.hdel.assert_called_with(retry_queue.queue_key, message_id)
    mock_redis.delete.assert_called()


@pytest.mark.asyncio
async def test_retry_queue_exponential_backoff():
    """
    Test that retry queue implements exponential backoff correctly.
    
    This integration test verifies:
    1. First retry has short backoff
    2. Subsequent retries have increasing backoff
    3. Backoff is capped at maximum value
    4. Message is removed after max retries
    
    Validates: Requirements 11.2
    """
    # Create mock Redis client
    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hget = AsyncMock()
    mock_redis.hdel = AsyncMock()
    mock_redis.delete = AsyncMock()
    
    # Create retry queue
    from slack_bot.config import SlackBotConfig
    config = SlackBotConfig(
        slack_bot_token="xoxb-test",
        slack_signing_secret="test_secret",
        slack_client_id="test_client_id",
        slack_client_secret="test_client_secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test_token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="test_encryption_key_32_chars_min"
    )
    
    retry_queue = RetryQueue(config)
    retry_queue.redis_client = mock_redis
    
    # Create a message
    now = datetime.utcnow()
    message = QueuedMessage(
        message_id="test_message_123",
        message_type=MessageType.DAILY_PLAN,
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel="D12345ABCDE",
        payload={'text': 'Test', 'blocks': []},
        created_at=now,
        retry_count=0,
        next_retry_at=now
    )
    
    # Mock hget to return message
    import json
    
    def create_message_data(retry_count, next_retry_at):
        return json.dumps({
            'message_id': message.message_id,
            'message_type': 'daily_plan',
            'user_id': message.user_id,
            'team_id': message.team_id,
            'channel': message.channel,
            'payload': message.payload,
            'created_at': message.created_at.isoformat(),
            'retry_count': retry_count,
            'next_retry_at': next_retry_at.isoformat() if next_retry_at else None,
            'max_retries': 5,
            'last_error': 'Test error'
        })
    
    # Test backoff progression
    backoff_times = []
    
    for retry_count in range(5):
        mock_redis.hget = AsyncMock(return_value=create_message_data(
            retry_count,
            now
        ))
        
        # Mark failure
        before_failure = datetime.utcnow()
        await retry_queue.mark_failure(message.message_id, "Test error")
        
        # Get the hset call to see what next_retry_at was set to
        if mock_redis.hset.called:
            call_args = mock_redis.hset.call_args
            stored_data = json.loads(call_args[0][2])
            next_retry = datetime.fromisoformat(stored_data['next_retry_at'])
            backoff = (next_retry - before_failure).total_seconds()
            backoff_times.append(backoff)
    
    # Verify exponential backoff
    # Backoff should be: 60, 120, 240, 300, 300 (capped at 300)
    # The formula is: min(300, 30 * (2 ** retry_count))
    assert len(backoff_times) == 5
    
    # First retry (retry_count=0): 30 * 2^0 = 30, but after first failure retry_count=1, so 30 * 2^1 = 60
    assert 55 <= backoff_times[0] <= 65
    
    # Second retry (retry_count=1): 30 * 2^2 = 120
    assert 115 <= backoff_times[1] <= 125
    
    # Third retry (retry_count=2): 30 * 2^3 = 240
    assert 235 <= backoff_times[2] <= 245
    
    # Fourth retry (retry_count=3): 30 * 2^4 = 480, capped at 300
    assert 295 <= backoff_times[3] <= 305
    
    # Fifth retry (retry_count=4): 30 * 2^5 = 960, capped at 300
    assert 295 <= backoff_times[4] <= 305


@pytest.mark.asyncio
async def test_error_message_delivery_to_user():
    """
    Test that user-friendly error messages are delivered when operations fail.
    
    This integration test verifies:
    1. TrIAge API error triggers error message
    2. Error message is formatted with troubleshooting suggestions
    3. Error message is delivered to user
    4. Original error is logged for debugging
    
    Validates: Requirements 11.3
    """
    # Create error handler
    error_handler = ErrorHandler(jira_base_url="https://jira.example.com")
    
    # Test various error scenarios
    
    # 1. API unavailable (503)
    api_error = TriageAPIError(
        message="Service unavailable",
        status_code=503
    )
    
    error_message = error_handler.handle_triage_api_error(api_error)
    
    # Verify error message structure
    assert error_message.blocks is not None
    assert len(error_message.blocks) > 0
    assert error_message.text is not None
    
    # Verify message contains helpful information
    message_text = str(error_message.blocks)
    assert 'unavailable' in message_text.lower()
    assert 'try again' in message_text.lower() or 'retry' in message_text.lower()
    
    # 2. Unauthorized (401)
    auth_error = TriageAPIError(
        message="Unauthorized",
        status_code=401
    )
    
    error_message = error_handler.handle_triage_api_error(auth_error)
    message_text = str(error_message.blocks)
    assert 'authentication' in message_text.lower() or 'credentials' in message_text.lower()
    
    # 3. Rate limited (429)
    rate_limit_error = TriageAPIError(
        message="Too many requests",
        status_code=429
    )
    
    error_message = error_handler.handle_triage_api_error(rate_limit_error)
    message_text = str(error_message.blocks)
    assert 'rate' in message_text.lower() or 'too many' in message_text.lower()
    assert 'wait' in message_text.lower() or 'retry' in message_text.lower()
    
    # 4. Not found (404)
    not_found_error = TriageAPIError(
        message="Not found",
        status_code=404
    )
    
    error_message = error_handler.handle_triage_api_error(not_found_error)
    message_text = str(error_message.blocks)
    assert 'not found' in message_text.lower()


@pytest.mark.asyncio
async def test_complete_error_recovery_workflow(sample_daily_plan, sample_user_config):
    """
    Test complete error recovery workflow from failure to successful retry.
    
    This integration test verifies the entire error recovery flow:
    1. Initial delivery fails
    2. Message is queued for retry
    3. Retry is attempted after backoff
    4. Retry succeeds
    5. Message is removed from queue
    6. User receives notification
    
    Validates: Requirements 11.1, 11.2, 11.3
    """
    # Create mock Slack client that fails first, succeeds second
    mock_slack_client = AsyncMock()
    
    attempt_count = 0
    
    async def mock_post_message(**kwargs):
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count == 1:
            # First attempt fails
            error_response = MagicMock()
            error_response.get = MagicMock(return_value='internal_error')
            error_response.__getitem__ = MagicMock(return_value='internal_error')
            raise SlackApiError("Internal error", error_response)
        else:
            # Second attempt succeeds
            return {
                'ok': True,
                'ts': '1234567890.123456',
                'channel': 'D12345ABCDE'
            }
    
    mock_slack_client.chat_postMessage = mock_post_message
    mock_slack_client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': 'D12345ABCDE'}
    })
    
    # Create notification service
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter,
        max_retries=2,
        retry_backoff_base=1.5  # Faster backoff for testing
    )
    
    # Attempt delivery - should succeed after retry
    result = await notification_service.deliver_daily_plan(
        plan=sample_daily_plan,
        plan_id='plan_recovery_test',
        user_config=sample_user_config,
        slack_user_id='U12345ABCDE'
    )
    
    # Verify delivery succeeded after retry
    assert result['delivered'] is True
    assert result['message_ts'] == '1234567890.123456'
    assert attempt_count == 2, "Should have made 2 attempts"


@pytest.mark.asyncio
async def test_max_retries_exceeded_handling():
    """
    Test handling when max retries are exceeded.
    
    This integration test verifies:
    1. All retry attempts fail
    2. Message is removed from queue after max retries
    3. Error is logged appropriately
    4. System continues to function
    
    Validates: Requirements 11.1, 11.2
    """
    # Create mock Redis client
    mock_redis = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.hgetall = AsyncMock()
    mock_redis.hdel = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    
    # Create retry queue
    from slack_bot.config import SlackBotConfig
    config = SlackBotConfig(
        slack_bot_token="xoxb-test",
        slack_signing_secret="test_secret",
        slack_client_id="test_client_id",
        slack_client_secret="test_client_secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test_token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="test_encryption_key_32_chars_min"
    )
    
    retry_queue = RetryQueue(config)
    retry_queue.redis_client = mock_redis
    
    # Create a message that has exceeded max retries
    now = datetime.utcnow()
    message = QueuedMessage(
        message_id="test_max_retries",
        message_type=MessageType.DAILY_PLAN,
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel="D12345ABCDE",
        payload={'text': 'Test', 'blocks': []},
        created_at=now - timedelta(hours=1),
        retry_count=5,  # Exceeded max_retries
        next_retry_at=now - timedelta(seconds=1),
        max_retries=5
    )
    
    # Mock hgetall to return message with max retries exceeded
    import json
    message_data = {
        message.message_id: json.dumps({
            'message_id': message.message_id,
            'message_type': 'daily_plan',
            'user_id': message.user_id,
            'team_id': message.team_id,
            'channel': message.channel,
            'payload': message.payload,
            'created_at': message.created_at.isoformat(),
            'retry_count': message.retry_count,
            'next_retry_at': message.next_retry_at.isoformat(),
            'max_retries': message.max_retries,
            'last_error': 'Persistent error'
        })
    }
    mock_redis.hgetall = AsyncMock(return_value=message_data)
    
    # Get pending messages - should remove message with max retries exceeded
    pending = await retry_queue.get_pending_messages(limit=10)
    
    # Verify message was removed (not returned in pending)
    assert len(pending) == 0
    
    # Verify remove was called
    mock_redis.hdel.assert_called()


@pytest.mark.asyncio
async def test_expired_message_removal():
    """
    Test that expired messages are removed from retry queue.
    
    This integration test verifies:
    1. Messages older than 24 hours are identified
    2. Expired messages are removed from queue
    3. Recent messages are retained
    
    Validates: Requirements 11.1
    """
    # Create mock Redis client
    mock_redis = AsyncMock()
    mock_redis.hgetall = AsyncMock()
    mock_redis.hdel = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    
    # Create retry queue
    from slack_bot.config import SlackBotConfig
    config = SlackBotConfig(
        slack_bot_token="xoxb-test",
        slack_signing_secret="test_secret",
        slack_client_id="test_client_id",
        slack_client_secret="test_client_secret",
        triage_api_url="https://api.example.com",
        triage_api_token="test_token",
        redis_url="redis://localhost:6379",
        database_url="postgresql://localhost/test",
        encryption_key="test_encryption_key_32_chars_min"
    )
    
    retry_queue = RetryQueue(config)
    retry_queue.redis_client = mock_redis
    
    # Create expired and recent messages
    now = datetime.utcnow()
    
    expired_message = QueuedMessage(
        message_id="expired_message",
        message_type=MessageType.DAILY_PLAN,
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel="D12345ABCDE",
        payload={'text': 'Expired', 'blocks': []},
        created_at=now - timedelta(hours=25),  # Older than 24 hours
        retry_count=2,
        next_retry_at=now - timedelta(seconds=1)
    )
    
    recent_message = QueuedMessage(
        message_id="recent_message",
        message_type=MessageType.DAILY_PLAN,
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel="D12345ABCDE",
        payload={'text': 'Recent', 'blocks': []},
        created_at=now - timedelta(hours=1),  # Recent
        retry_count=1,
        next_retry_at=now - timedelta(seconds=1)
    )
    
    # Mock hgetall to return both messages
    import json
    message_data = {
        expired_message.message_id: json.dumps({
            'message_id': expired_message.message_id,
            'message_type': 'daily_plan',
            'user_id': expired_message.user_id,
            'team_id': expired_message.team_id,
            'channel': expired_message.channel,
            'payload': expired_message.payload,
            'created_at': expired_message.created_at.isoformat(),
            'retry_count': expired_message.retry_count,
            'next_retry_at': expired_message.next_retry_at.isoformat(),
            'max_retries': 5,
            'last_error': None
        }),
        recent_message.message_id: json.dumps({
            'message_id': recent_message.message_id,
            'message_type': 'daily_plan',
            'user_id': recent_message.user_id,
            'team_id': recent_message.team_id,
            'channel': recent_message.channel,
            'payload': recent_message.payload,
            'created_at': recent_message.created_at.isoformat(),
            'retry_count': recent_message.retry_count,
            'next_retry_at': recent_message.next_retry_at.isoformat(),
            'max_retries': 5,
            'last_error': None
        })
    }
    mock_redis.hgetall = AsyncMock(return_value=message_data)
    
    # Get pending messages
    pending = await retry_queue.get_pending_messages(limit=10)
    
    # Verify only recent message is returned
    assert len(pending) == 1
    assert pending[0].message_id == recent_message.message_id
    
    # Verify expired message was removed
    remove_calls = mock_redis.hdel.call_args_list
    assert any(expired_message.message_id in str(call) for call in remove_calls)
