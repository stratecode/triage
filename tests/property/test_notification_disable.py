# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for notification disable behavior.

Feature: slack-integration, Property 23: Notification Disable Behavior

For any user with notifications disabled, slash commands should still function
normally, but proactive notifications (daily plans, blocking tasks) should not
be sent.

Validates: Requirements 10.5
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from slack_bot.models import SlackConfig
from slack_bot.notification_service import NotificationDeliveryService
from triage.models import DailyPlan, JiraIssue, TaskClassification


# Custom strategies for generating test data
@st.composite
def user_id_strategy(draw):
    """Generate valid user IDs."""
    return f"user_{draw(st.integers(min_value=1, max_value=999999))}"


@st.composite
def slack_user_id_strategy(draw):
    """Generate valid Slack user IDs."""
    user_num = draw(st.integers(min_value=100000000, max_value=999999999))
    return f"U{user_num}"


@st.composite
def channel_strategy(draw):
    """Generate valid channel configurations."""
    is_dm = draw(st.booleans())
    if is_dm:
        return "DM"
    else:
        channel_num = draw(st.integers(min_value=100000000, max_value=999999999))
        return f"C{channel_num}"


@st.composite
def slack_config_strategy(draw):
    """Generate valid SlackConfig objects."""
    return SlackConfig(
        user_id=draw(user_id_strategy()),
        notification_channel=draw(channel_strategy()),
        delivery_time=f"{draw(st.integers(0, 23)):02d}:{draw(st.integers(0, 59)):02d}",
        notifications_enabled=draw(st.booleans()),
        timezone=draw(st.sampled_from(["UTC", "America/New_York", "Europe/London"]))
    )


@st.composite
def jira_issue_strategy(draw):
    """Generate valid JIRA issues."""
    return JiraIssue(
        key=f"PROJ-{draw(st.integers(1, 9999))}",
        summary=draw(st.text(min_size=10, max_size=100)),
        description=draw(st.text(min_size=0, max_size=200)),
        issue_type=draw(st.sampled_from(["Story", "Bug", "Task"])),
        status=draw(st.sampled_from(["To Do", "In Progress", "Blocked", "Done"])),
        assignee=draw(st.text(min_size=5, max_size=50)),
        priority=draw(st.sampled_from(["High", "Medium", "Low"]))
    )


@st.composite
def task_classification_strategy(draw):
    """Generate valid TaskClassification objects."""
    from triage.models import TaskCategory
    
    return TaskClassification(
        task=draw(jira_issue_strategy()),
        category=draw(st.sampled_from(list(TaskCategory))),
        is_priority_eligible=draw(st.booleans()),
        has_dependencies=draw(st.booleans()),
        estimated_days=draw(st.floats(min_value=0.1, max_value=5.0))
    )


@st.composite
def admin_block_strategy(draw):
    """Generate valid AdminBlock objects."""
    from triage.models import AdminBlock
    
    num_tasks = draw(st.integers(0, 10))
    
    return AdminBlock(
        tasks=[draw(task_classification_strategy()) for _ in range(num_tasks)],
        time_allocation_minutes=draw(st.integers(30, 90)),
        scheduled_time="14:00-15:30"
    )


@st.composite
def daily_plan_strategy(draw):
    """Generate valid DailyPlan objects."""
    from triage.models import DailyPlan
    
    num_priority = draw(st.integers(0, 3))
    num_other = draw(st.integers(0, 5))
    
    return DailyPlan(
        date=date.today(),
        priorities=[draw(task_classification_strategy()) for _ in range(num_priority)],
        admin_block=draw(admin_block_strategy()),
        other_tasks=[draw(task_classification_strategy()) for _ in range(num_other)]
    )


# Feature: slack-integration, Property 23: Notification Disable Behavior
@settings(max_examples=100, deadline=2000)
@given(
    config=slack_config_strategy(),
    plan=daily_plan_strategy(),
    slack_user_id=slack_user_id_strategy()
)
@pytest.mark.asyncio
async def test_daily_plan_notification_disable_behavior(config, plan, slack_user_id):
    """
    Property 23: Notification Disable Behavior (Daily Plans)
    
    For any user with notifications disabled, daily plan notifications
    should not be delivered, but the function should return a result
    indicating notifications were disabled.
    
    Validates: Requirements 10.5
    """
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    mock_slack_client.chat_postMessage = AsyncMock()
    
    # Create mock message formatter
    mock_formatter = MagicMock()
    mock_formatter.format_daily_plan = MagicMock(return_value=MagicMock(
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test plan"}}],
        text="Test plan"
    ))
    
    # Create notification service
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=mock_formatter
    )
    
    # Generate plan ID
    plan_id = f"plan_{config.user_id}_{plan.date.isoformat()}"
    
    # Deliver plan
    result = await service.deliver_daily_plan(
        plan=plan,
        plan_id=plan_id,
        user_config=config,
        slack_user_id=slack_user_id
    )
    
    # Verify behavior based on notifications_enabled
    if config.notifications_enabled:
        # Notifications enabled: message should be delivered
        assert result['delivered'] is True
        assert 'message_ts' in result
        assert result['user_id'] == config.user_id
        
        # Verify Slack API was called
        mock_slack_client.chat_postMessage.assert_called_once()
    else:
        # Notifications disabled: message should NOT be delivered
        assert result['delivered'] is False
        assert result['reason'] == 'notifications_disabled'
        assert result['user_id'] == config.user_id
        
        # Verify Slack API was NOT called
        mock_slack_client.chat_postMessage.assert_not_called()


# Feature: slack-integration, Property 23: Notification Disable Behavior
@settings(max_examples=100, deadline=2000)
@given(
    config=slack_config_strategy(),
    task=jira_issue_strategy(),
    slack_user_id=slack_user_id_strategy()
)
@pytest.mark.asyncio
async def test_blocking_task_notification_disable_behavior(config, task, slack_user_id):
    """
    Property 23: Notification Disable Behavior (Blocking Tasks)
    
    For any user with notifications disabled, blocking task notifications
    should not be delivered, but the function should return a result
    indicating notifications were disabled.
    
    Validates: Requirements 10.5
    """
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    mock_slack_client.chat_postMessage = AsyncMock()
    
    # Create mock message formatter
    mock_formatter = MagicMock()
    mock_formatter.format_blocking_task_alert = MagicMock(return_value=MagicMock(
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Blocking task"}}],
        text="Blocking task"
    ))
    
    # Create notification service
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=mock_formatter
    )
    
    # Deliver blocking task alert
    result = await service.deliver_blocking_task_alert(
        task=task,
        blocker_reason="Third-party dependency",
        user_config=config,
        slack_user_id=slack_user_id
    )
    
    # Verify behavior based on notifications_enabled
    if config.notifications_enabled:
        # Notifications enabled: message should be delivered
        assert result['delivered'] is True
        assert 'message_ts' in result
        assert result['user_id'] == config.user_id
        
        # Verify Slack API was called
        mock_slack_client.chat_postMessage.assert_called_once()
    else:
        # Notifications disabled: message should NOT be delivered
        assert result['delivered'] is False
        assert result['reason'] == 'notifications_disabled'
        assert result['user_id'] == config.user_id
        
        # Verify Slack API was NOT called
        mock_slack_client.chat_postMessage.assert_not_called()


# Feature: slack-integration, Property 23: Notification Disable Behavior
@settings(max_examples=100, deadline=2000)
@given(
    config=slack_config_strategy(),
    task=jira_issue_strategy(),
    slack_user_id=slack_user_id_strategy()
)
@pytest.mark.asyncio
async def test_resolution_notification_disable_behavior(config, task, slack_user_id):
    """
    Property 23: Notification Disable Behavior (Resolution Notifications)
    
    For any user with notifications disabled, blocking task resolution
    notifications should not be delivered, but the function should return
    a result indicating notifications were disabled.
    
    Validates: Requirements 10.5
    """
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    mock_slack_client.chat_postMessage = AsyncMock()
    
    # Create mock message formatter
    mock_formatter = MagicMock()
    mock_formatter.format_blocking_task_resolved = MagicMock(return_value=MagicMock(
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Task resolved"}}],
        text="Task resolved"
    ))
    
    # Create notification service
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=mock_formatter
    )
    
    # Deliver resolution notification
    result = await service.deliver_blocking_task_resolved_notification(
        task=task,
        user_config=config,
        slack_user_id=slack_user_id
    )
    
    # Verify behavior based on notifications_enabled
    if config.notifications_enabled:
        # Notifications enabled: message should be delivered
        assert result['delivered'] is True
        assert 'message_ts' in result
        assert result['user_id'] == config.user_id
        
        # Verify Slack API was called
        mock_slack_client.chat_postMessage.assert_called_once()
    else:
        # Notifications disabled: message should NOT be delivered
        assert result['delivered'] is False
        assert result['reason'] == 'notifications_disabled'
        assert result['user_id'] == config.user_id
        
        # Verify Slack API was NOT called
        mock_slack_client.chat_postMessage.assert_not_called()


# Feature: slack-integration, Property 23: Notification Disable Behavior
@settings(max_examples=50, deadline=2000)
@given(
    enabled_config=slack_config_strategy(),
    disabled_config=slack_config_strategy(),
    plan=daily_plan_strategy(),
    slack_user_id=slack_user_id_strategy()
)
@pytest.mark.asyncio
async def test_notification_toggle_effect(enabled_config, disabled_config, plan, slack_user_id):
    """
    Property 23: Notification Disable Behavior (Toggle Effect)
    
    For any user configuration, toggling notifications_enabled should
    change delivery behavior: enabled delivers, disabled does not.
    
    Validates: Requirements 10.5
    """
    # Force one config to be enabled and one disabled
    enabled_config.notifications_enabled = True
    disabled_config.notifications_enabled = False
    
    # Use same user ID for both configs
    disabled_config.user_id = enabled_config.user_id
    
    # Create mock Slack client
    mock_slack_client = AsyncMock()
    mock_slack_client.chat_postMessage = AsyncMock()
    
    # Create mock message formatter
    mock_formatter = MagicMock()
    mock_formatter.format_daily_plan = MagicMock(return_value=MagicMock(
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test plan"}}],
        text="Test plan"
    ))
    
    # Create notification service
    service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=mock_formatter
    )
    
    plan_id = f"plan_{enabled_config.user_id}_{plan.date.isoformat()}"
    
    # Test with notifications enabled
    result_enabled = await service.deliver_daily_plan(
        plan=plan,
        plan_id=plan_id,
        user_config=enabled_config,
        slack_user_id=slack_user_id
    )
    
    # Should be delivered
    assert result_enabled['delivered'] is True
    assert mock_slack_client.chat_postMessage.call_count == 1
    
    # Reset mock
    mock_slack_client.chat_postMessage.reset_mock()
    
    # Test with notifications disabled
    result_disabled = await service.deliver_daily_plan(
        plan=plan,
        plan_id=plan_id,
        user_config=disabled_config,
        slack_user_id=slack_user_id
    )
    
    # Should NOT be delivered
    assert result_disabled['delivered'] is False
    assert result_disabled['reason'] == 'notifications_disabled'
    assert mock_slack_client.chat_postMessage.call_count == 0
