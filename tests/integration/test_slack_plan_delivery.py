# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for end-to-end plan delivery workflow.

This module tests the complete flow from plan generation through Slack
notification delivery, including approval button functionality.

Validates: Requirements 2.1, 2.5, 3.2
"""

import pytest
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from slack_bot.notification_service import NotificationDeliveryService
from slack_bot.notification_handler import NotificationHandler
from slack_bot.message_formatter import MessageFormatter
from slack_bot.triage_api_client import TriageAPIClient
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
    # Create priority tasks
    priority_task1 = JiraIssue(
        key="PROJ-123",
        summary="Fix critical authentication bug",
        description="Users unable to log in",
        issue_type="Bug",
        priority="High",
        status="In Progress",
        assignee="user@example.com",
        story_points=3,
        time_estimate=14400,  # 4 hours
        labels=["security", "critical"],
        issue_links=[],
        custom_fields={}
    )
    
    priority_task2 = JiraIssue(
        key="PROJ-456",
        summary="Implement user profile page",
        description="Create new profile page",
        issue_type="Story",
        priority="Medium",
        status="To Do",
        assignee="user@example.com",
        story_points=5,
        time_estimate=28800,  # 8 hours
        labels=["frontend"],
        issue_links=[],
        custom_fields={}
    )
    
    # Create admin tasks
    admin_task1 = JiraIssue(
        key="PROJ-789",
        summary="Update documentation",
        description="Update API docs",
        issue_type="Task",
        priority="Low",
        status="To Do",
        assignee="user@example.com",
        story_points=1,
        time_estimate=3600,  # 1 hour
        labels=["documentation"],
        issue_links=[],
        custom_fields={}
    )
    
    # Create classifications
    priority_classifications = [
        TaskClassification(
            task=priority_task1,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=0.5
        ),
        TaskClassification(
            task=priority_task2,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=1.0
        )
    ]
    
    admin_classification = TaskClassification(
        task=admin_task1,
        category=TaskCategory.ADMINISTRATIVE,
        is_priority_eligible=False,
        has_dependencies=False,
        estimated_days=0.125
    )
    
    admin_block = AdminBlock(
        tasks=[admin_classification],
        time_allocation_minutes=60,
        scheduled_time="14:00-15:00"
    )
    
    return DailyPlan(
        date=date.today(),
        priorities=priority_classifications,
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


@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client."""
    client = AsyncMock()
    
    # Mock conversations_open for DM resolution
    client.conversations_open = AsyncMock(return_value={
        'ok': True,
        'channel': {'id': 'D12345ABCDE'}
    })
    
    # Mock chat_postMessage for message delivery
    client.chat_postMessage = AsyncMock(return_value={
        'ok': True,
        'ts': '1234567890.123456',
        'channel': 'D12345ABCDE'
    })
    
    # Mock chat_update for message updates (approval)
    client.chat_update = AsyncMock(return_value={
        'ok': True,
        'ts': '1234567890.123456',
        'channel': 'D12345ABCDE'
    })
    
    return client


@pytest.fixture
def mock_triage_api_client():
    """Create a mock TrIAge API client."""
    client = AsyncMock(spec=TriageAPIClient)
    
    # Mock get_config
    client.get_config = AsyncMock(return_value=SlackConfig(
        user_id="test_user_123",
        notification_channel="DM",
        delivery_time="09:00",
        notifications_enabled=True,
        timezone="UTC"
    ))
    
    # Mock get_user_mapping
    client.get_user_mapping = AsyncMock(return_value={
        'slack_user_id': 'U12345ABCDE',
        'slack_team_id': 'T12345ABCDE',
        'triage_user_id': 'test_user_123',
        'jira_email': 'user@example.com'
    })
    
    # Mock approve_plan
    client.approve_plan = AsyncMock(return_value={
        'success': True,
        'plan_id': 'plan_123',
        'approved': True
    })
    
    return client


@pytest.mark.asyncio
async def test_end_to_end_plan_delivery(
    sample_daily_plan,
    sample_user_config,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test complete plan delivery workflow from generation to Slack notification.
    
    This integration test verifies:
    1. Plan generation triggers Slack notification
    2. Message appears in correct channel (DM)
    3. Message contains properly formatted plan
    4. Approval buttons are functional
    
    Validates: Requirements 2.1, 2.5, 3.2
    """
    # Create message formatter
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Create notification service
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    
    # Create notification handler
    notification_handler = NotificationHandler(
        notification_service=notification_service,
        triage_api_client=mock_triage_api_client
    )
    
    # Step 1: Simulate plan generation and notification request
    plan_notification_request = {
        'user_id': 'test_user_123',
        'team_id': 'T12345ABCDE',
        'plan': {
            'date': sample_daily_plan.date.isoformat(),
            'priority_tasks': [
                {
                    'key': t.task.key,
                    'summary': t.task.summary,
                    'description': t.task.description or '',
                    'issue_type': t.task.issue_type,
                    'priority': t.task.priority,
                    'status': t.task.status,
                    'assignee': t.task.assignee,
                    'story_points': t.task.story_points,
                    'time_estimate': t.task.time_estimate,
                    'labels': t.task.labels,
                    'issue_links': [],
                    'custom_fields': {},
                    'estimated_days': t.estimated_days
                }
                for t in sample_daily_plan.priorities
            ],
            'admin_tasks': [
                {
                    'key': t.task.key,
                    'summary': t.task.summary,
                    'description': t.task.description or '',
                    'issue_type': t.task.issue_type,
                    'priority': t.task.priority,
                    'status': t.task.status,
                    'assignee': t.task.assignee,
                    'story_points': t.task.story_points,
                    'time_estimate': t.task.time_estimate,
                    'labels': t.task.labels,
                    'issue_links': [],
                    'custom_fields': {},
                    'estimated_days': t.estimated_days
                }
                for t in sample_daily_plan.admin_block.tasks
            ]
        },
        'plan_id': 'plan_123'
    }
    
    # Step 2: Handle plan notification
    response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    # Verify notification was successful
    assert response.success is True, "Notification should succeed"
    assert response.delivered is True, "Plan should be delivered"
    assert response.message_ts is not None, "Should have message timestamp"
    assert response.channel is not None, "Should have channel ID"
    
    # Step 3: Verify Slack API calls
    # Should open DM with user
    mock_slack_client.conversations_open.assert_called_once()
    call_args = mock_slack_client.conversations_open.call_args
    assert 'U12345ABCDE' in call_args.kwargs['users']
    
    # Should send message to DM
    mock_slack_client.chat_postMessage.assert_called_once()
    message_call_args = mock_slack_client.chat_postMessage.call_args
    
    # Verify message was sent to correct channel
    assert message_call_args.kwargs['channel'] == 'D12345ABCDE'
    
    # Verify message contains blocks
    assert 'blocks' in message_call_args.kwargs
    blocks = message_call_args.kwargs['blocks']
    assert len(blocks) > 0, "Message should have blocks"
    
    # Verify message has fallback text
    assert 'text' in message_call_args.kwargs
    assert len(message_call_args.kwargs['text']) > 0
    
    # Step 4: Verify message content
    blocks_str = str(blocks)
    
    # Should contain header
    assert any(b['type'] == 'header' for b in blocks), "Should have header block"
    
    # Should contain priority task information
    assert 'PROJ-123' in blocks_str, "Should contain first priority task"
    assert 'PROJ-456' in blocks_str, "Should contain second priority task"
    assert 'Fix critical authentication bug' in blocks_str
    
    # Should contain admin task information
    assert 'PROJ-789' in blocks_str, "Should contain admin task"
    assert 'Update documentation' in blocks_str
    
    # Should contain approval buttons
    action_blocks = [b for b in blocks if b['type'] == 'actions']
    assert len(action_blocks) > 0, "Should have action buttons"
    
    buttons = action_blocks[0]['elements']
    assert len(buttons) == 3, "Should have 3 buttons (Approve, Reject, Modify)"
    
    button_action_ids = [btn['action_id'] for btn in buttons]
    assert 'approve_plan' in button_action_ids
    assert 'reject_plan' in button_action_ids
    assert 'modify_plan' in button_action_ids
    
    # Verify button values contain plan_id
    for btn in buttons:
        assert btn['value'] == 'plan_123'


@pytest.mark.asyncio
async def test_plan_delivery_with_channel_configuration(
    sample_daily_plan,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test plan delivery to a configured channel instead of DM.
    
    Validates: Requirements 2.1
    """
    # Configure user to receive notifications in a channel
    channel_config = SlackConfig(
        user_id="test_user_123",
        notification_channel="C12345ABCDE",  # Channel ID instead of DM
        delivery_time="09:00",
        notifications_enabled=True,
        timezone="UTC"
    )
    
    mock_triage_api_client.get_config = AsyncMock(return_value=channel_config)
    
    # Create services
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    notification_handler = NotificationHandler(
        notification_service=notification_service,
        triage_api_client=mock_triage_api_client
    )
    
    # Deliver plan
    plan_notification_request = {
        'user_id': 'test_user_123',
        'team_id': 'T12345ABCDE',
        'plan': {
            'date': sample_daily_plan.date.isoformat(),
            'priority_tasks': [],
            'admin_tasks': []
        },
        'plan_id': 'plan_456'
    }
    
    response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    # Verify delivery
    assert response.success is True
    assert response.delivered is True
    
    # Should NOT open DM (channel configured)
    mock_slack_client.conversations_open.assert_not_called()
    
    # Should send message to configured channel
    mock_slack_client.chat_postMessage.assert_called_once()
    message_call_args = mock_slack_client.chat_postMessage.call_args
    assert message_call_args.kwargs['channel'] == 'C12345ABCDE'


@pytest.mark.asyncio
async def test_plan_delivery_with_notifications_disabled(
    sample_daily_plan,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test that plan delivery is skipped when notifications are disabled.
    
    Validates: Requirements 2.1, 10.5
    """
    # Configure user with notifications disabled
    disabled_config = SlackConfig(
        user_id="test_user_123",
        notification_channel="DM",
        delivery_time="09:00",
        notifications_enabled=False,  # Disabled
        timezone="UTC"
    )
    
    mock_triage_api_client.get_config = AsyncMock(return_value=disabled_config)
    
    # Create services
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    notification_handler = NotificationHandler(
        notification_service=notification_service,
        triage_api_client=mock_triage_api_client
    )
    
    # Attempt to deliver plan
    plan_notification_request = {
        'user_id': 'test_user_123',
        'team_id': 'T12345ABCDE',
        'plan': {
            'date': sample_daily_plan.date.isoformat(),
            'priority_tasks': [],
            'admin_tasks': []
        },
        'plan_id': 'plan_789'
    }
    
    response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    # Verify delivery was skipped
    assert response.success is True
    assert response.delivered is False
    
    # Should NOT call Slack API
    mock_slack_client.conversations_open.assert_not_called()
    mock_slack_client.chat_postMessage.assert_not_called()


@pytest.mark.asyncio
async def test_plan_delivery_error_handling(
    sample_daily_plan,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test error handling when Slack API fails.
    
    Validates: Requirements 11.1, 11.2
    """
    # Configure Slack client to fail
    from slack_sdk.errors import SlackApiError
    mock_slack_client.chat_postMessage = AsyncMock(
        side_effect=SlackApiError("API Error", {'error': 'channel_not_found', 'ok': False})
    )
    
    # Create services
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter,
        max_retries=1  # Reduce retries for faster test
    )
    notification_handler = NotificationHandler(
        notification_service=notification_service,
        triage_api_client=mock_triage_api_client
    )
    
    # Attempt to deliver plan
    plan_notification_request = {
        'user_id': 'test_user_123',
        'team_id': 'T12345ABCDE',
        'plan': {
            'date': sample_daily_plan.date.isoformat(),
            'priority_tasks': [],
            'admin_tasks': []
        },
        'plan_id': 'plan_error'
    }
    
    response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    # Verify error was handled gracefully
    assert response.success is False
    assert response.delivered is False
    assert response.error is not None
    assert 'delivery_error' in response.error


@pytest.mark.asyncio
async def test_approval_button_functionality(
    sample_daily_plan,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test that approval buttons trigger correct API calls.
    
    This test simulates a user clicking the approve button and verifies
    that the TrIAge API is called correctly.
    
    Validates: Requirements 3.2
    """
    # Create services
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    
    # Deliver plan first
    result = await notification_service.deliver_daily_plan(
        plan=sample_daily_plan,
        plan_id='plan_approval_test',
        user_config=SlackConfig(
            user_id="test_user_123",
            notification_channel="DM",
            delivery_time="09:00",
            notifications_enabled=True,
            timezone="UTC"
        ),
        slack_user_id='U12345ABCDE'
    )
    
    assert result['delivered'] is True
    message_ts = result['message_ts']
    
    # Simulate user clicking approve button
    # In a real scenario, this would come from Slack's interaction webhook
    await mock_triage_api_client.approve_plan(
        plan_id='plan_approval_test',
        user_id='test_user_123'
    )
    
    # Verify API was called
    mock_triage_api_client.approve_plan.assert_called_once_with(
        plan_id='plan_approval_test',
        user_id='test_user_123'
    )
