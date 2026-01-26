# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for plan delivery routing.

Feature: slack-integration
Properties:
- Property 2: Plan Delivery Routing

Validates: Requirements 2.1
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, assume, settings
from hypothesis import HealthCheck

from slack_bot.notification_service import NotificationDeliveryService
from slack_bot.message_formatter import MessageFormatter
from slack_bot.models import SlackConfig
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
)


# Custom strategies for generating test data

@st.composite
def jira_issue_strategy(draw):
    """Generate random JiraIssue objects."""
    issue_types = ["Story", "Bug", "Task", "Epic"]
    priorities = ["Blocker", "High", "Medium", "Low"]
    statuses = ["To Do", "In Progress", "Done"]
    
    project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    key = f"{project}-{number}"
    
    return JiraIssue(
        key=key,
        summary=draw(st.text(min_size=5, max_size=200)),
        description=draw(st.text(min_size=0, max_size=500)),
        issue_type=draw(st.sampled_from(issue_types)),
        priority=draw(st.sampled_from(priorities)),
        status=draw(st.sampled_from(statuses)),
        assignee=draw(st.emails()),
        story_points=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=13))),
        time_estimate=draw(st.one_of(st.none(), st.integers(min_value=3600, max_value=86400))),
        labels=draw(st.lists(st.text(min_size=1, max_size=20), max_size=5)),
        issue_links=[],
        custom_fields={},
    )


@st.composite
def task_classification_strategy(draw):
    """Generate random TaskClassification objects."""
    issue = draw(jira_issue_strategy())
    category = draw(st.sampled_from(list(TaskCategory)))
    
    is_priority_eligible = category == TaskCategory.PRIORITY_ELIGIBLE
    has_dependencies = category == TaskCategory.DEPENDENT
    
    if is_priority_eligible:
        estimated_days = draw(st.floats(min_value=0.1, max_value=1.0))
    else:
        estimated_days = draw(st.floats(min_value=0.1, max_value=10.0))
    
    blocking_reason = None
    if category == TaskCategory.BLOCKING:
        blocking_reason = draw(st.text(min_size=10, max_size=100))
    
    return TaskClassification(
        task=issue,
        category=category,
        is_priority_eligible=is_priority_eligible,
        has_dependencies=has_dependencies,
        estimated_days=estimated_days,
        blocking_reason=blocking_reason,
    )


@st.composite
def admin_block_strategy(draw):
    """Generate random AdminBlock objects."""
    num_tasks = draw(st.integers(min_value=0, max_value=5))
    tasks = []
    for _ in range(num_tasks):
        issue = draw(jira_issue_strategy())
        classification = TaskClassification(
            task=issue,
            category=TaskCategory.ADMINISTRATIVE,
            is_priority_eligible=False,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.1, max_value=0.5)),
        )
        tasks.append(classification)
    
    time_allocation = draw(st.integers(min_value=0, max_value=90))
    hour = draw(st.integers(min_value=13, max_value=17))
    start_min = draw(st.integers(min_value=0, max_value=30))
    end_hour = hour + 1 if start_min + time_allocation <= 60 else hour + 2
    end_min = (start_min + time_allocation) % 60
    scheduled_time = f"{hour:02d}:{start_min:02d}-{end_hour:02d}:{end_min:02d}"
    
    return AdminBlock(
        tasks=tasks,
        time_allocation_minutes=time_allocation,
        scheduled_time=scheduled_time,
    )


@st.composite
def daily_plan_strategy(draw):
    """Generate random DailyPlan objects."""
    num_priorities = draw(st.integers(min_value=0, max_value=3))
    priorities = []
    for _ in range(num_priorities):
        issue = draw(jira_issue_strategy())
        classification = TaskClassification(
            task=issue,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.1, max_value=1.0)),
        )
        priorities.append(classification)
    
    admin_block = draw(admin_block_strategy())
    
    num_other = draw(st.integers(min_value=0, max_value=5))
    other_tasks = [draw(task_classification_strategy()) for _ in range(num_other)]
    
    previous_closure_rate = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0)))
    
    plan_date = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    
    return DailyPlan(
        date=plan_date,
        priorities=priorities,
        admin_block=admin_block,
        other_tasks=other_tasks,
        previous_closure_rate=previous_closure_rate,
    )


@st.composite
def slack_user_id_strategy(draw):
    """Generate valid Slack user IDs."""
    # Slack user IDs start with U followed by 8-11 alphanumeric characters
    suffix = draw(st.text(
        min_size=8,
        max_size=11,
        alphabet=st.characters(whitelist_categories=("Lu", "Nd"))
    ))
    return f"U{suffix}"


@st.composite
def slack_channel_id_strategy(draw):
    """Generate valid Slack channel IDs."""
    # Slack channel IDs start with C followed by 8-11 alphanumeric characters
    suffix = draw(st.text(
        min_size=8,
        max_size=11,
        alphabet=st.characters(whitelist_categories=("Lu", "Nd"))
    ))
    return f"C{suffix}"


@st.composite
def slack_config_strategy(draw):
    """Generate random SlackConfig objects."""
    user_id = draw(st.text(min_size=5, max_size=50))
    
    # Notification channel can be "DM" or a channel ID
    use_dm = draw(st.booleans())
    if use_dm:
        notification_channel = "DM"
    else:
        notification_channel = draw(slack_channel_id_strategy())
    
    delivery_time = f"{draw(st.integers(min_value=0, max_value=23)):02d}:{draw(st.integers(min_value=0, max_value=59)):02d}"
    notifications_enabled = draw(st.booleans())
    timezone = draw(st.sampled_from(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]))
    
    return SlackConfig(
        user_id=user_id,
        notification_channel=notification_channel,
        delivery_time=delivery_time,
        notifications_enabled=notifications_enabled,
        timezone=timezone,
    )


# Property Tests

# Feature: slack-integration, Property 2: Plan Delivery Routing
@given(
    plan=daily_plan_strategy(),
    plan_id=st.text(min_size=1, max_size=50),
    user_config=slack_config_strategy(),
    slack_user_id=slack_user_id_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
def test_property_2_plan_delivery_routing(plan, plan_id, user_config, slack_user_id):
    """
    Property 2: Plan Delivery Routing
    
    For any generated daily plan and user configuration, the plan should be
    delivered to the user's configured Slack channel or DM, never to an
    incorrect destination.
    
    This property verifies that:
    1. If notifications are enabled, delivery is attempted
    2. If notifications are disabled, delivery is skipped
    3. The correct channel/DM is targeted based on configuration
    4. DM resolution works correctly when configured
    5. Channel IDs are used directly when configured
    
    Validates: Requirements 2.1
    """
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    
    # Mock conversations_open for DM resolution
    mock_dm_channel_id = "D12345ABCDE"
    mock_slack_client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': mock_dm_channel_id}
    })
    
    # Mock chat_postMessage for message delivery
    mock_message_ts = "1234567890.123456"
    mock_slack_client.chat_postMessage = AsyncMock(return_value={
        'ok': True,
        'ts': mock_message_ts,
        'channel': user_config.notification_channel if user_config.notification_channel != "DM" else mock_dm_channel_id
    })
    
    # Create message formatter
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Create notification service
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter,
        max_retries=3,
        retry_backoff_base=2.0
    )
    
    # Deliver plan
    result = asyncio.run(service.deliver_daily_plan(
        plan=plan,
        plan_id=plan_id,
        user_config=user_config,
        slack_user_id=slack_user_id
    ))
    
    # Verify delivery behavior based on configuration
    if not user_config.notifications_enabled:
        # Property: If notifications disabled, delivery should be skipped
        assert result['delivered'] is False, \
            "Plan should not be delivered when notifications are disabled"
        assert result['reason'] == 'notifications_disabled', \
            "Reason should indicate notifications are disabled"
        
        # Slack API should not be called
        mock_slack_client.chat_postMessage.assert_not_called()
    
    else:
        # Property: If notifications enabled, delivery should be attempted
        assert result['delivered'] is True, \
            "Plan should be delivered when notifications are enabled"
        
        # Verify correct channel resolution
        if user_config.notification_channel == "DM":
            # Property: DM configuration should open conversation with user
            mock_slack_client.conversations_open.assert_called_once()
            call_args = mock_slack_client.conversations_open.call_args
            assert slack_user_id in call_args.kwargs['users'], \
                f"DM should be opened with user {slack_user_id}"
            
            # Property: Message should be sent to resolved DM channel
            mock_slack_client.chat_postMessage.assert_called_once()
            call_args = mock_slack_client.chat_postMessage.call_args
            assert call_args.kwargs['channel'] == mock_dm_channel_id, \
                f"Message should be sent to DM channel {mock_dm_channel_id}"
        
        else:
            # Property: Channel ID should be used directly without resolution
            mock_slack_client.conversations_open.assert_not_called()
            
            # Property: Message should be sent to configured channel
            mock_slack_client.chat_postMessage.assert_called_once()
            call_args = mock_slack_client.chat_postMessage.call_args
            assert call_args.kwargs['channel'] == user_config.notification_channel, \
                f"Message should be sent to configured channel {user_config.notification_channel}"
        
        # Property: Result should contain delivery metadata
        assert 'message_ts' in result, "Result should contain message timestamp"
        assert result['message_ts'] == mock_message_ts, \
            f"Message timestamp should be {mock_message_ts}"
        
        assert 'channel' in result, "Result should contain channel ID"
        expected_channel = mock_dm_channel_id if user_config.notification_channel == "DM" else user_config.notification_channel
        assert result['channel'] == expected_channel, \
            f"Result channel should be {expected_channel}"
        
        assert 'user_id' in result, "Result should contain user ID"
        assert result['user_id'] == user_config.user_id, \
            f"Result user_id should be {user_config.user_id}"
        
        assert 'plan_id' in result, "Result should contain plan ID"
        assert result['plan_id'] == plan_id, \
            f"Result plan_id should be {plan_id}"


# Additional property: Verify message content is formatted correctly
@given(
    plan=daily_plan_strategy(),
    plan_id=st.text(min_size=1, max_size=50),
    user_config=slack_config_strategy(),
    slack_user_id=slack_user_id_strategy()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
def test_plan_delivery_message_content(plan, plan_id, user_config, slack_user_id):
    """
    Verify that delivered plan messages contain properly formatted content.
    
    For any plan delivery, the message sent to Slack should:
    1. Contain Block Kit blocks
    2. Have fallback text
    3. Include plan information
    """
    # Skip if notifications disabled (no message sent)
    assume(user_config.notifications_enabled)
    
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    
    # Mock DM resolution
    mock_dm_channel_id = "D12345ABCDE"
    mock_slack_client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': mock_dm_channel_id}
    })
    
    # Capture message content
    sent_message = None
    
    async def capture_message(**kwargs):
        nonlocal sent_message
        sent_message = kwargs
        return {
            'ok': True,
            'ts': "1234567890.123456",
            'channel': kwargs['channel']
        }
    
    mock_slack_client.chat_postMessage = AsyncMock(side_effect=capture_message)
    
    # Create message formatter
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Create notification service
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    
    # Deliver plan
    result = asyncio.run(service.deliver_daily_plan(
        plan=plan,
        plan_id=plan_id,
        user_config=user_config,
        slack_user_id=slack_user_id
    ))
    
    # Verify message was sent
    assert sent_message is not None, "Message should have been sent"
    
    # Property: Message must have blocks
    assert 'blocks' in sent_message, "Message must contain blocks"
    assert len(sent_message['blocks']) > 0, "Message must have at least one block"
    
    # Property: Message must have fallback text
    assert 'text' in sent_message, "Message must contain fallback text"
    assert len(sent_message['text']) > 0, "Fallback text must not be empty"
    
    # Property: Blocks should be valid Block Kit format
    for block in sent_message['blocks']:
        assert 'type' in block, "Each block must have a type"
        assert isinstance(block, dict), "Each block must be a dictionary"


# Property: Verify retry behavior on transient failures
@given(
    plan=daily_plan_strategy(),
    plan_id=st.text(min_size=1, max_size=50),
    user_config=slack_config_strategy(),
    slack_user_id=slack_user_id_strategy(),
    num_failures=st.integers(min_value=1, max_value=2)
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_plan_delivery_retry_on_failure(plan, plan_id, user_config, slack_user_id, num_failures):
    """
    Verify that plan delivery retries on transient failures.
    
    For any plan delivery that encounters retryable errors, the service
    should retry with exponential backoff and eventually succeed.
    """
    # Skip if notifications disabled
    assume(user_config.notifications_enabled)
    
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    
    # Mock DM resolution
    mock_dm_channel_id = "D12345ABCDE"
    mock_slack_client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': mock_dm_channel_id}
    })
    
    # Mock chat_postMessage to fail a few times then succeed
    call_count = 0
    
    async def failing_then_success(**kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count <= num_failures:
            # Simulate retryable error
            from slack_sdk.errors import SlackApiError
            error_response = {'error': 'rate_limited', 'ok': False}
            raise SlackApiError("Rate limited", error_response)
        else:
            # Success
            return {
                'ok': True,
                'ts': "1234567890.123456",
                'channel': kwargs['channel']
            }
    
    mock_slack_client.chat_postMessage = AsyncMock(side_effect=failing_then_success)
    
    # Create message formatter
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Create notification service with retries
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter,
        max_retries=3,
        retry_backoff_base=1.1  # Small backoff for faster tests
    )
    
    # Deliver plan
    result = asyncio.run(service.deliver_daily_plan(
        plan=plan,
        plan_id=plan_id,
        user_config=user_config,
        slack_user_id=slack_user_id
    ))
    
    # Property: Delivery should eventually succeed after retries
    assert result['delivered'] is True, \
        f"Delivery should succeed after {num_failures} retries"
    
    # Property: Service should have retried the correct number of times
    assert call_count == num_failures + 1, \
        f"Expected {num_failures + 1} calls (failures + success), got {call_count}"
