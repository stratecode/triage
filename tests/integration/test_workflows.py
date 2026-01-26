# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for complete approval workflow.

This module tests the end-to-end approval workflow including:
- Plan delivery to Slack
- User button click interaction
- TrIAge API call for approval
- Message update to show approval status

Validates: Requirements 2.1, 3.2, 3.5
"""

import pytest
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any

from slack_bot.notification_service import NotificationDeliveryService
from slack_bot.notification_handler import NotificationHandler
from slack_bot.message_formatter import MessageFormatter
from slack_bot.interaction_handler import InteractionHandler
from slack_bot.triage_api_client import TriageAPIClient
from slack_bot.models import SlackConfig, BlockAction
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
    
    # Mock chat_postEphemeral for ephemeral messages
    client.chat_postEphemeral = AsyncMock(return_value={
        'ok': True
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
    
    # Mock reject_plan
    client.reject_plan = AsyncMock(return_value={
        'success': True,
        'plan_id': 'plan_123',
        'rejected': True
    })
    
    return client


@pytest.mark.asyncio
async def test_complete_approval_workflow(
    sample_daily_plan,
    sample_user_config,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test complete approval workflow from plan delivery to approval confirmation.
    
    This integration test verifies the entire flow:
    1. Plan is delivered to Slack with approval buttons
    2. User clicks "Approve" button
    3. TrIAge API is called to approve the plan
    4. Message is updated to show approval status
    5. Action buttons are disabled
    
    Validates: Requirements 2.1, 3.2, 3.5
    """
    # Step 1: Set up services
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    
    notification_handler = NotificationHandler(
        notification_service=notification_service,
        triage_api_client=mock_triage_api_client
    )
    
    # Step 2: Deliver plan to Slack
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
        'plan_id': 'plan_approval_test_123'
    }
    
    # Deliver the plan
    delivery_response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    # Verify plan was delivered successfully
    assert delivery_response.success is True, "Plan delivery should succeed"
    assert delivery_response.delivered is True, "Plan should be delivered"
    assert delivery_response.message_ts is not None, "Should have message timestamp"
    message_ts = delivery_response.message_ts
    
    # Verify Slack API was called to send message
    mock_slack_client.chat_postMessage.assert_called_once()
    post_message_call = mock_slack_client.chat_postMessage.call_args
    
    # Verify message contains approval buttons
    blocks = post_message_call.kwargs['blocks']
    action_blocks = [b for b in blocks if b['type'] == 'actions']
    assert len(action_blocks) > 0, "Message should have action buttons"
    
    buttons = action_blocks[0]['elements']
    assert len(buttons) == 3, "Should have 3 buttons"
    
    button_action_ids = [btn['action_id'] for btn in buttons]
    assert 'approve_plan' in button_action_ids, "Should have approve button"
    assert 'reject_plan' in button_action_ids, "Should have reject button"
    assert 'modify_plan' in button_action_ids, "Should have modify button"
    
    # Verify button values contain plan_id
    approve_button = next(btn for btn in buttons if btn['action_id'] == 'approve_plan')
    assert approve_button['value'] == 'plan_approval_test_123'
    
    # Step 3: Simulate user clicking "Approve" button
    # Create mock HTTP client for interaction handler
    mock_triage_http_client = AsyncMock()
    mock_triage_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {'success': True, 'approved': True}
    ))
    mock_triage_http_client.aclose = AsyncMock()
    
    mock_slack_http_client = AsyncMock()
    mock_slack_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {'ok': True, 'ts': message_ts}
    ))
    mock_slack_http_client.aclose = AsyncMock()
    
    # Create interaction handler
    interaction_handler = InteractionHandler(
        triage_api_url="https://triage-api.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=formatter
    )
    
    # Replace HTTP clients with mocks
    interaction_handler.triage_client = mock_triage_http_client
    interaction_handler.slack_client = mock_slack_http_client
    
    # Create button action
    approve_action = BlockAction(
        action_id="approve_plan",
        value="plan_approval_test_123",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="D12345ABCDE",
        message_ts=message_ts,
        response_url="https://hooks.slack.com/actions/test"
    )
    
    # Handle the approval action
    await interaction_handler.handle_action(approve_action)
    
    # Step 4: Verify TrIAge API was called to approve plan
    mock_triage_http_client.post.assert_called()
    api_calls = mock_triage_http_client.post.call_args_list
    
    # Find the approval API call
    approval_call = None
    for call_obj in api_calls:
        if '/approve' in str(call_obj):
            approval_call = call_obj
            break
    
    assert approval_call is not None, "Should call TrIAge API to approve plan"
    assert '/api/v1/plans/plan_approval_test_123/approve' in approval_call.args[0]
    
    # Verify request payload
    approval_payload = approval_call.kwargs['json']
    assert approval_payload['user_id'] == 'U12345ABCDE'
    assert approval_payload['team_id'] == 'T12345ABCDE'
    
    # Step 5: Verify message was updated to show approval status
    mock_slack_http_client.post.assert_called()
    slack_calls = mock_slack_http_client.post.call_args_list
    
    # Find the chat.update call
    update_call = None
    for call_obj in slack_calls:
        if '/chat.update' in str(call_obj):
            update_call = call_obj
            break
    
    assert update_call is not None, "Should update message to show approval"
    
    # Verify update payload
    update_payload = update_call.kwargs['json']
    assert update_payload['channel'] == 'D12345ABCDE'
    assert update_payload['ts'] == message_ts
    
    # Verify updated message shows approval
    updated_blocks = update_payload['blocks']
    updated_text = str(updated_blocks)
    assert '✅' in updated_text or 'Approved' in updated_text, "Should show approval status"
    
    # Verify buttons are disabled (no action blocks in updated message)
    updated_action_blocks = [b for b in updated_blocks if b['type'] == 'actions']
    assert len(updated_action_blocks) == 0, "Action buttons should be removed/disabled"
    
    # Cleanup
    await interaction_handler.close()


@pytest.mark.asyncio
async def test_complete_rejection_workflow(
    sample_daily_plan,
    sample_user_config,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test complete rejection workflow from plan delivery to rejection confirmation.
    
    This integration test verifies:
    1. Plan is delivered to Slack with action buttons
    2. User clicks "Reject" button
    3. TrIAge API is called to reject the plan
    4. Message is updated to show rejection status
    5. Feedback thread is created
    
    Validates: Requirements 2.1, 3.3, 3.5
    """
    # Set up services
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
        'plan_id': 'plan_rejection_test_456'
    }
    
    delivery_response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    assert delivery_response.success is True
    assert delivery_response.delivered is True
    message_ts = delivery_response.message_ts
    
    # Create interaction handler with mocks
    mock_triage_http_client = AsyncMock()
    mock_triage_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {'success': True, 'rejected': True}
    ))
    mock_triage_http_client.aclose = AsyncMock()
    
    mock_slack_http_client = AsyncMock()
    mock_slack_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {'ok': True, 'ts': message_ts}
    ))
    mock_slack_http_client.aclose = AsyncMock()
    
    interaction_handler = InteractionHandler(
        triage_api_url="https://triage-api.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=formatter
    )
    
    interaction_handler.triage_client = mock_triage_http_client
    interaction_handler.slack_client = mock_slack_http_client
    
    # Simulate rejection button click
    reject_action = BlockAction(
        action_id="reject_plan",
        value="plan_rejection_test_456",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="D12345ABCDE",
        message_ts=message_ts,
        response_url="https://hooks.slack.com/actions/test"
    )
    
    await interaction_handler.handle_action(reject_action)
    
    # Verify TrIAge API was called to reject plan
    mock_triage_http_client.post.assert_called()
    api_calls = mock_triage_http_client.post.call_args_list
    
    rejection_call = None
    for call_obj in api_calls:
        if '/reject' in str(call_obj):
            rejection_call = call_obj
            break
    
    assert rejection_call is not None, "Should call TrIAge API to reject plan"
    assert '/api/v1/plans/plan_rejection_test_456/reject' in rejection_call.args[0]
    
    # Verify message was updated to show rejection
    slack_calls = mock_slack_http_client.post.call_args_list
    
    update_call = None
    feedback_call = None
    
    for call_obj in slack_calls:
        call_str = str(call_obj)
        if '/chat.update' in call_str:
            update_call = call_obj
        elif '/chat.postMessage' in call_str:
            feedback_call = call_obj
    
    assert update_call is not None, "Should update message to show rejection"
    
    # Verify updated message shows rejection
    update_payload = update_call.kwargs['json']
    updated_blocks = update_payload['blocks']
    updated_text = str(updated_blocks)
    assert '❌' in updated_text or 'Rejected' in updated_text, "Should show rejection status"
    
    # Verify feedback thread was created
    assert feedback_call is not None, "Should create feedback thread"
    feedback_payload = feedback_call.kwargs['json']
    assert feedback_payload['thread_ts'] == message_ts, "Should be in thread"
    assert 'feedback' in str(feedback_payload).lower(), "Should prompt for feedback"
    
    # Cleanup
    await interaction_handler.close()


@pytest.mark.asyncio
async def test_approval_workflow_with_api_error(
    sample_daily_plan,
    sample_user_config,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test approval workflow when TrIAge API returns an error.
    
    Verifies that errors are handled gracefully and user receives
    appropriate error message.
    
    Validates: Requirements 3.2, 11.3
    """
    # Set up services
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
        'plan_id': 'plan_error_test_789'
    }
    
    delivery_response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    assert delivery_response.success is True
    message_ts = delivery_response.message_ts
    
    # Create interaction handler with failing API
    mock_triage_http_client = AsyncMock()
    mock_triage_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=500,  # Internal server error
        json=lambda: {'error': 'Internal server error'}
    ))
    mock_triage_http_client.aclose = AsyncMock()
    
    mock_slack_http_client = AsyncMock()
    mock_slack_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {'ok': True}
    ))
    mock_slack_http_client.aclose = AsyncMock()
    
    interaction_handler = InteractionHandler(
        triage_api_url="https://triage-api.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=formatter
    )
    
    interaction_handler.triage_client = mock_triage_http_client
    interaction_handler.slack_client = mock_slack_http_client
    
    # Simulate approval button click
    approve_action = BlockAction(
        action_id="approve_plan",
        value="plan_error_test_789",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="D12345ABCDE",
        message_ts=message_ts,
        response_url="https://hooks.slack.com/actions/test"
    )
    
    await interaction_handler.handle_action(approve_action)
    
    # Verify TrIAge API was called
    mock_triage_http_client.post.assert_called()
    
    # Verify error message was sent to user
    slack_calls = mock_slack_http_client.post.call_args_list
    
    ephemeral_call = None
    for call_obj in slack_calls:
        if '/chat.postEphemeral' in str(call_obj):
            ephemeral_call = call_obj
            break
    
    assert ephemeral_call is not None, "Should send error message to user"
    
    # Verify error message content
    error_payload = ephemeral_call.kwargs['json']
    error_text = str(error_payload)
    assert 'error' in error_text.lower() or 'failed' in error_text.lower(), \
        "Should contain error information"
    
    # Cleanup
    await interaction_handler.close()


@pytest.mark.asyncio
async def test_approval_workflow_with_already_processed_plan(
    sample_daily_plan,
    sample_user_config,
    mock_slack_client,
    mock_triage_api_client
):
    """
    Test approval workflow when plan has already been processed.
    
    Verifies that duplicate approvals are handled correctly.
    
    Validates: Requirements 3.2, 3.5
    """
    # Set up services
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
        'plan_id': 'plan_duplicate_test_999'
    }
    
    delivery_response = await notification_handler.handle_plan_notification(
        request_data=plan_notification_request
    )
    
    assert delivery_response.success is True
    message_ts = delivery_response.message_ts
    
    # Create interaction handler with API returning 409 Conflict
    mock_triage_http_client = AsyncMock()
    mock_triage_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=409,  # Conflict - already processed
        json=lambda: {'error': 'Plan already processed'}
    ))
    mock_triage_http_client.aclose = AsyncMock()
    
    mock_slack_http_client = AsyncMock()
    mock_slack_http_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=lambda: {'ok': True}
    ))
    mock_slack_http_client.aclose = AsyncMock()
    
    interaction_handler = InteractionHandler(
        triage_api_url="https://triage-api.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test-token",
        message_formatter=formatter
    )
    
    interaction_handler.triage_client = mock_triage_http_client
    interaction_handler.slack_client = mock_slack_http_client
    
    # Simulate approval button click
    approve_action = BlockAction(
        action_id="approve_plan",
        value="plan_duplicate_test_999",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="D12345ABCDE",
        message_ts=message_ts,
        response_url="https://hooks.slack.com/actions/test"
    )
    
    await interaction_handler.handle_action(approve_action)
    
    # Verify appropriate error message was sent
    slack_calls = mock_slack_http_client.post.call_args_list
    
    ephemeral_call = None
    for call_obj in slack_calls:
        if '/chat.postEphemeral' in str(call_obj):
            ephemeral_call = call_obj
            break
    
    assert ephemeral_call is not None, "Should send message about duplicate action"
    
    error_payload = ephemeral_call.kwargs['json']
    error_text = str(error_payload)
    assert 'already' in error_text.lower() or 'processed' in error_text.lower(), \
        "Should indicate plan was already processed"
    
    # Cleanup
    await interaction_handler.close()
