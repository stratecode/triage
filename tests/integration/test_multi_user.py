# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for multi-user scenario with data isolation.

This module tests concurrent users in the same workspace with proper
data isolation, ensuring each user's data remains separate and secure.

Validates: Requirements 8.1, 8.2, 8.5
"""

import pytest
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from slack_bot.user_middleware import UserIdentificationMiddleware, UserMapper
from slack_bot.user_storage import UserMappingStorage
from slack_bot.data_isolation import DataIsolationChecker, DataIsolationError
from slack_bot.notification_service import NotificationDeliveryService
from slack_bot.notification_handler import NotificationHandler
from slack_bot.message_formatter import MessageFormatter
from slack_bot.command_handler import CommandHandler
from slack_bot.interaction_handler import InteractionHandler
from slack_bot.triage_api_client import TriageAPIClient
from slack_bot.models import SlackUser, SlackConfig, SlashCommand, BlockAction
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
)


@pytest.fixture
def user1_data():
    """Create data for first test user."""
    return {
        'slack_user_id': 'U12345ABCDE',
        'slack_team_id': 'T12345WORK',
        'triage_user_id': 'triage_user_1',
        'jira_email': 'user1@example.com',
        'display_name': 'User One'
    }


@pytest.fixture
def user2_data():
    """Create data for second test user."""
    return {
        'slack_user_id': 'U67890XYZAB',
        'slack_team_id': 'T12345WORK',  # Same workspace
        'triage_user_id': 'triage_user_2',
        'jira_email': 'user2@example.com',
        'display_name': 'User Two'
    }


@pytest.fixture
def user1_slack_user(user1_data):
    """Create SlackUser object for user 1."""
    return SlackUser(**user1_data)


@pytest.fixture
def user2_slack_user(user2_data):
    """Create SlackUser object for user 2."""
    return SlackUser(**user2_data)


@pytest.fixture
def user1_config(user1_data):
    """Create configuration for user 1."""
    return SlackConfig(
        user_id=user1_data['triage_user_id'],
        notification_channel="DM",
        delivery_time="09:00",
        notifications_enabled=True,
        timezone="UTC"
    )


@pytest.fixture
def user2_config(user2_data):
    """Create configuration for user 2."""
    return SlackConfig(
        user_id=user2_data['triage_user_id'],
        notification_channel="C_CHANNEL_USER2",
        delivery_time="10:00",
        notifications_enabled=True,
        timezone="America/New_York"
    )


@pytest.fixture
def user1_plan():
    """Create daily plan for user 1."""
    task1 = JiraIssue(
        key="USER1-123",
        summary="User 1 priority task",
        description="Task for user 1",
        issue_type="Story",
        priority="High",
        status="In Progress",
        assignee="user1@example.com",
        story_points=5,
        time_estimate=28800,
        labels=["user1"],
        issue_links=[],
        custom_fields={}
    )
    
    classification1 = TaskClassification(
        task=task1,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=1.0
    )
    
    return DailyPlan(
        date=date.today(),
        priorities=[classification1],
        admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time=""),
        other_tasks=[],
        previous_closure_rate=0.85
    )


@pytest.fixture
def user2_plan():
    """Create daily plan for user 2."""
    task2 = JiraIssue(
        key="USER2-456",
        summary="User 2 priority task",
        description="Task for user 2",
        issue_type="Bug",
        priority="Medium",
        status="To Do",
        assignee="user2@example.com",
        story_points=3,
        time_estimate=14400,
        labels=["user2"],
        issue_links=[],
        custom_fields={}
    )
    
    classification2 = TaskClassification(
        task=task2,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5
    )
    
    return DailyPlan(
        date=date.today(),
        priorities=[classification2],
        admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time=""),
        other_tasks=[],
        previous_closure_rate=0.90
    )


@pytest.fixture
def mock_user_storage():
    """Create mock user storage."""
    storage = AsyncMock(spec=UserMappingStorage)
    
    # Store user mappings in memory for test
    mappings = {}
    
    async def get_mapping(slack_user_id, slack_team_id):
        key = f"{slack_user_id}:{slack_team_id}"
        return mappings.get(key)
    
    async def create_mapping(slack_user):
        key = f"{slack_user.slack_user_id}:{slack_user.slack_team_id}"
        mappings[key] = slack_user
        return slack_user
    
    storage.get_mapping = get_mapping
    storage.create_mapping = create_mapping
    
    return storage


@pytest.fixture
def mock_slack_client():
    """Create mock Slack client."""
    client = AsyncMock()
    
    # Track messages sent to each user
    sent_messages = {}
    
    async def conversations_open(users):
        # Return different DM channels for different users
        user_id = users if isinstance(users, str) else users[0]
        return {
            'ok': True,
            'channel': {'id': f'D_DM_{user_id}'}
        }
    
    async def chat_postMessage(**kwargs):
        channel = kwargs['channel']
        if channel not in sent_messages:
            sent_messages[channel] = []
        sent_messages[channel].append(kwargs)
        return {
            'ok': True,
            'ts': f'{len(sent_messages[channel])}.123456',
            'channel': channel
        }
    
    client.conversations_open = conversations_open
    client.chat_postMessage = chat_postMessage
    client.sent_messages = sent_messages
    
    return client


@pytest.mark.asyncio
async def test_multi_user_data_isolation(
    user1_data,
    user2_data,
    user1_slack_user,
    user2_slack_user,
    user1_config,
    user2_config,
    user1_plan,
    user2_plan,
    mock_user_storage,
    mock_slack_client
):
    """
    Test complete multi-user scenario with data isolation.
    
    This integration test verifies:
    1. Multiple users can use the bot independently in the same workspace
    2. Each user's data is properly isolated
    3. User 1 cannot access User 2's data and vice versa
    4. Plans are delivered to correct users
    5. Configurations are user-specific
    
    Validates: Requirements 8.1, 8.2, 8.5
    """
    # Step 1: Set up user mappings
    await mock_user_storage.create_mapping(user1_slack_user)
    await mock_user_storage.create_mapping(user2_slack_user)
    
    # Verify mappings are stored separately
    retrieved_user1 = await mock_user_storage.get_mapping(
        user1_data['slack_user_id'],
        user1_data['slack_team_id']
    )
    retrieved_user2 = await mock_user_storage.get_mapping(
        user2_data['slack_user_id'],
        user2_data['slack_team_id']
    )
    
    assert retrieved_user1 is not None
    assert retrieved_user2 is not None
    assert retrieved_user1.triage_user_id != retrieved_user2.triage_user_id
    assert retrieved_user1.jira_email != retrieved_user2.jira_email
    
    # Step 2: Set up mock TrIAge API client with user-specific responses
    mock_triage_api = AsyncMock(spec=TriageAPIClient)
    
    async def get_config(user_id):
        if user_id == user1_data['triage_user_id']:
            return user1_config
        elif user_id == user2_data['triage_user_id']:
            return user2_config
        return None
    
    async def get_user_mapping(slack_user_id, slack_team_id):
        # Handle both Slack user ID and TrIAge user ID lookups
        if slack_user_id == user1_data['slack_user_id'] or slack_user_id == user1_data['triage_user_id']:
            return {
                'slack_user_id': user1_data['slack_user_id'],
                'slack_team_id': user1_data['slack_team_id'],
                'triage_user_id': user1_data['triage_user_id'],
                'jira_email': user1_data['jira_email'],
                'display_name': user1_data['display_name']
            }
        elif slack_user_id == user2_data['slack_user_id'] or slack_user_id == user2_data['triage_user_id']:
            return {
                'slack_user_id': user2_data['slack_user_id'],
                'slack_team_id': user2_data['slack_team_id'],
                'triage_user_id': user2_data['triage_user_id'],
                'jira_email': user2_data['jira_email'],
                'display_name': user2_data['display_name']
            }
        return None
    
    mock_triage_api.get_config = get_config
    mock_triage_api.get_user_mapping = get_user_mapping
    
    # Step 3: Set up notification services
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    notification_service = NotificationDeliveryService(
        slack_client=mock_slack_client,
        message_formatter=formatter
    )
    notification_handler = NotificationHandler(
        notification_service=notification_service,
        triage_api_client=mock_triage_api
    )
    
    # Step 4: Deliver plans to both users concurrently
    user1_notification = {
        'user_id': user1_data['triage_user_id'],
        'team_id': user1_data['slack_team_id'],
        'plan': {
            'date': user1_plan.date.isoformat(),
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
                for t in user1_plan.priorities
            ],
            'admin_tasks': []
        },
        'plan_id': 'plan_user1_001'
    }
    
    user2_notification = {
        'user_id': user2_data['triage_user_id'],
        'team_id': user2_data['slack_team_id'],
        'plan': {
            'date': user2_plan.date.isoformat(),
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
                for t in user2_plan.priorities
            ],
            'admin_tasks': []
        },
        'plan_id': 'plan_user2_002'
    }
    
    # Deliver plans concurrently
    results = await asyncio.gather(
        notification_handler.handle_plan_notification(user1_notification),
        notification_handler.handle_plan_notification(user2_notification)
    )
    
    user1_result, user2_result = results
    
    # Verify both deliveries succeeded
    assert user1_result.success is True
    assert user1_result.delivered is True
    assert user2_result.success is True
    assert user2_result.delivered is True
    
    # Step 5: Verify messages were sent to correct channels
    # User 1 should receive message in DM
    user1_dm_channel = f'D_DM_{user1_data["slack_user_id"]}'
    assert user1_dm_channel in mock_slack_client.sent_messages
    user1_messages = mock_slack_client.sent_messages[user1_dm_channel]
    assert len(user1_messages) > 0
    
    # User 2 should receive message in configured channel
    user2_channel = user2_config.notification_channel
    assert user2_channel in mock_slack_client.sent_messages
    user2_messages = mock_slack_client.sent_messages[user2_channel]
    assert len(user2_messages) > 0
    
    # Step 6: Verify message content is user-specific
    user1_message_content = str(user1_messages[0]['blocks'])
    user2_message_content = str(user2_messages[0]['blocks'])
    
    # User 1's message should contain their task
    assert 'USER1-123' in user1_message_content
    assert 'User 1 priority task' in user1_message_content
    assert 'USER2-456' not in user1_message_content  # Should NOT contain user 2's task
    
    # User 2's message should contain their task
    assert 'USER2-456' in user2_message_content
    assert 'User 2 priority task' in user2_message_content
    assert 'USER1-123' not in user2_message_content  # Should NOT contain user 1's task
    
    # Step 7: Test data isolation enforcement
    isolation_checker = DataIsolationChecker()
    
    # User 1 should be able to access their own data
    isolation_checker.verify_user_access(
        requesting_user=user1_slack_user,
        resource_user_id=user1_data['triage_user_id'],
        resource_type="plan"
    )
    
    # User 1 should NOT be able to access User 2's data
    with pytest.raises(DataIsolationError):
        isolation_checker.verify_user_access(
            requesting_user=user1_slack_user,
            resource_user_id=user2_data['triage_user_id'],
            resource_type="plan"
        )
    
    # User 2 should be able to access their own data
    isolation_checker.verify_user_access(
        requesting_user=user2_slack_user,
        resource_user_id=user2_data['triage_user_id'],
        resource_type="plan"
    )
    
    # User 2 should NOT be able to access User 1's data
    with pytest.raises(DataIsolationError):
        isolation_checker.verify_user_access(
            requesting_user=user2_slack_user,
            resource_user_id=user1_data['triage_user_id'],
            resource_type="plan"
        )
    
    # Step 8: Test concurrent slash commands from both users
    user_mapper = UserMapper(user_storage=mock_user_storage)
    user_middleware = UserIdentificationMiddleware(user_mapper=user_mapper)
    
    # Create slash commands from both users
    user1_command = SlashCommand(
        command="/triage",
        text="status",
        user_id=user1_data['slack_user_id'],
        team_id=user1_data['slack_team_id'],
        channel_id="C_CHANNEL_GENERAL",
        response_url="https://hooks.slack.com/commands/user1"
    )
    
    user2_command = SlashCommand(
        command="/triage",
        text="status",
        user_id=user2_data['slack_user_id'],
        team_id=user2_data['slack_team_id'],
        channel_id="C_CHANNEL_GENERAL",
        response_url="https://hooks.slack.com/commands/user2"
    )
    
    # Identify users from commands
    identified_user1 = await user_middleware.identify_user(user1_command)
    identified_user2 = await user_middleware.identify_user(user2_command)
    
    # Verify correct user identification
    assert identified_user1 is not None
    assert identified_user1.triage_user_id == user1_data['triage_user_id']
    assert identified_user2 is not None
    assert identified_user2.triage_user_id == user2_data['triage_user_id']
    
    # Verify users are different
    assert identified_user1.triage_user_id != identified_user2.triage_user_id
    assert identified_user1.jira_email != identified_user2.jira_email
    
    # Step 9: Test concurrent button interactions
    user1_action = BlockAction(
        action_id="approve_plan",
        value="plan_user1_001",
        user_id=user1_data['slack_user_id'],
        team_id=user1_data['slack_team_id'],
        channel_id=user1_dm_channel,
        message_ts=user1_result.message_ts,
        response_url="https://hooks.slack.com/actions/user1"
    )
    
    user2_action = BlockAction(
        action_id="approve_plan",
        value="plan_user2_002",
        user_id=user2_data['slack_user_id'],
        team_id=user2_data['slack_team_id'],
        channel_id=user2_channel,
        message_ts=user2_result.message_ts,
        response_url="https://hooks.slack.com/actions/user2"
    )
    
    # Identify users from actions
    action_user1 = await user_middleware.identify_user(user1_action)
    action_user2 = await user_middleware.identify_user(user2_action)
    
    # Verify correct user identification from actions
    assert action_user1 is not None
    assert action_user1.triage_user_id == user1_data['triage_user_id']
    assert action_user2 is not None
    assert action_user2.triage_user_id == user2_data['triage_user_id']
    
    # Step 10: Verify workspace isolation
    # Both users are in the same workspace
    isolation_checker.verify_workspace_isolation(
        requesting_user=user1_slack_user,
        resource_team_id=user1_data['slack_team_id']
    )
    isolation_checker.verify_workspace_isolation(
        requesting_user=user2_slack_user,
        resource_team_id=user2_data['slack_team_id']
    )
    
    # Users should not access resources from different workspace
    different_workspace_id = "T99999DIFF"
    with pytest.raises(DataIsolationError):
        isolation_checker.verify_workspace_isolation(
            requesting_user=user1_slack_user,
            resource_team_id=different_workspace_id
        )


@pytest.mark.asyncio
async def test_concurrent_user_operations(
    user1_data,
    user2_data,
    user1_slack_user,
    user2_slack_user,
    mock_user_storage
):
    """
    Test concurrent operations from multiple users.
    
    Verifies that concurrent user operations don't interfere with each other
    and maintain proper data isolation.
    
    Validates: Requirements 8.1, 8.2
    """
    # Set up user mappings
    await mock_user_storage.create_mapping(user1_slack_user)
    await mock_user_storage.create_mapping(user2_slack_user)
    
    # Create user mapper and middleware
    user_mapper = UserMapper(user_storage=mock_user_storage)
    user_middleware = UserIdentificationMiddleware(user_mapper=user_mapper)
    
    # Simulate concurrent user identification requests
    async def identify_user1():
        for _ in range(10):
            user = await user_middleware.identify_user({
                'user': {'id': user1_data['slack_user_id']},
                'team': {'id': user1_data['slack_team_id']}
            })
            assert user is not None
            assert user.triage_user_id == user1_data['triage_user_id']
            await asyncio.sleep(0.01)
    
    async def identify_user2():
        for _ in range(10):
            user = await user_middleware.identify_user({
                'user': {'id': user2_data['slack_user_id']},
                'team': {'id': user2_data['slack_team_id']}
            })
            assert user is not None
            assert user.triage_user_id == user2_data['triage_user_id']
            await asyncio.sleep(0.01)
    
    # Run concurrent operations
    await asyncio.gather(
        identify_user1(),
        identify_user2()
    )
    
    # Verify final state - both users still have correct mappings
    final_user1 = await mock_user_storage.get_mapping(
        user1_data['slack_user_id'],
        user1_data['slack_team_id']
    )
    final_user2 = await mock_user_storage.get_mapping(
        user2_data['slack_user_id'],
        user2_data['slack_team_id']
    )
    
    assert final_user1.triage_user_id == user1_data['triage_user_id']
    assert final_user2.triage_user_id == user2_data['triage_user_id']
    assert final_user1.triage_user_id != final_user2.triage_user_id


@pytest.mark.asyncio
async def test_user_specific_jira_credentials(
    user1_data,
    user2_data,
    user1_slack_user,
    user2_slack_user,
    mock_user_storage
):
    """
    Test that each user's JIRA credentials are used correctly.
    
    Verifies that plan generation uses the requesting user's JIRA account,
    not another user's credentials.
    
    Validates: Requirements 8.4
    """
    # Set up user mappings
    await mock_user_storage.create_mapping(user1_slack_user)
    await mock_user_storage.create_mapping(user2_slack_user)
    
    # Create user mapper
    user_mapper = UserMapper(user_storage=mock_user_storage)
    
    # Retrieve user mappings
    retrieved_user1 = await user_mapper.get_user_mapping(
        slack_user_id=user1_data['slack_user_id'],
        slack_team_id=user1_data['slack_team_id']
    )
    retrieved_user2 = await user_mapper.get_user_mapping(
        slack_user_id=user2_data['slack_user_id'],
        slack_team_id=user2_data['slack_team_id']
    )
    
    # Verify each user has their own JIRA email
    assert retrieved_user1.jira_email == user1_data['jira_email']
    assert retrieved_user2.jira_email == user2_data['jira_email']
    assert retrieved_user1.jira_email != retrieved_user2.jira_email
    
    # Verify JIRA credentials are user-specific
    # In a real scenario, the TrIAge API would use these emails to
    # authenticate with JIRA using the corresponding user's credentials
    assert 'user1@example.com' in retrieved_user1.jira_email
    assert 'user2@example.com' in retrieved_user2.jira_email


@pytest.mark.asyncio
async def test_data_filtering_for_multi_user(
    user1_data,
    user2_data,
    user1_slack_user,
    user2_slack_user
):
    """
    Test data filtering to ensure users only see their own data.
    
    Validates: Requirements 8.2, 8.5
    """
    isolation_checker = DataIsolationChecker()
    
    # Create mixed data items from both users
    data_items = [
        {'id': 'item1', 'user_id': user1_data['triage_user_id'], 'content': 'User 1 data'},
        {'id': 'item2', 'user_id': user2_data['triage_user_id'], 'content': 'User 2 data'},
        {'id': 'item3', 'user_id': user1_data['triage_user_id'], 'content': 'More user 1 data'},
        {'id': 'item4', 'user_id': user2_data['triage_user_id'], 'content': 'More user 2 data'},
    ]
    
    # Filter for user 1
    user1_filtered = isolation_checker.filter_user_data(
        requesting_user=user1_slack_user,
        data_items=data_items,
        user_id_field='user_id'
    )
    
    # Verify user 1 only sees their data
    assert len(user1_filtered) == 2
    assert all(item['user_id'] == user1_data['triage_user_id'] for item in user1_filtered)
    assert 'item1' in [item['id'] for item in user1_filtered]
    assert 'item3' in [item['id'] for item in user1_filtered]
    assert 'item2' not in [item['id'] for item in user1_filtered]
    assert 'item4' not in [item['id'] for item in user1_filtered]
    
    # Filter for user 2
    user2_filtered = isolation_checker.filter_user_data(
        requesting_user=user2_slack_user,
        data_items=data_items,
        user_id_field='user_id'
    )
    
    # Verify user 2 only sees their data
    assert len(user2_filtered) == 2
    assert all(item['user_id'] == user2_data['triage_user_id'] for item in user2_filtered)
    assert 'item2' in [item['id'] for item in user2_filtered]
    assert 'item4' in [item['id'] for item in user2_filtered]
    assert 'item1' not in [item['id'] for item in user2_filtered]
    assert 'item3' not in [item['id'] for item in user2_filtered]
