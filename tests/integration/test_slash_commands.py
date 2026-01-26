# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Integration tests for slash command execution.

This module tests the end-to-end slash command workflow including:
- Command receipt from Slack
- API call to TrIAge backend
- Response delivery to user

Validates: Requirements 4.1, 4.2, 4.3
"""

import pytest
import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from slack_bot.command_handler import CommandHandler
from slack_bot.message_formatter import MessageFormatter
from slack_bot.models import SlashCommand


@pytest.fixture
def message_formatter():
    """Create a message formatter instance."""
    return MessageFormatter(jira_base_url="https://jira.example.com")


@pytest.fixture
def mock_triage_api():
    """Create a mock TrIAge API server."""
    mock_client = AsyncMock()
    
    # Mock plan generation endpoint
    mock_client.post = AsyncMock()
    
    # Mock status endpoint
    mock_client.get = AsyncMock()
    
    # Mock config endpoints
    mock_client.put = AsyncMock()
    
    # Mock close
    mock_client.aclose = AsyncMock()
    
    return mock_client


@pytest.fixture
def command_handler(message_formatter, mock_triage_api):
    """Create a command handler with mocked API client."""
    handler = CommandHandler(
        triage_api_url="https://triage-api.example.com",
        triage_api_token="test_token_12345",
        message_formatter=message_formatter,
        timeout_seconds=3
    )
    
    # Replace HTTP client with mock
    handler.http_client = mock_triage_api
    
    return handler


@pytest.mark.asyncio
async def test_plan_command_execution(command_handler, mock_triage_api):
    """
    Test complete /triage plan command execution.
    
    This integration test verifies:
    1. Command is received and parsed
    2. TrIAge API is called to generate plan
    3. Response is delivered to user within 3 seconds
    
    Validates: Requirements 4.1, 4.4
    """
    # Step 1: Create slash command
    plan_command = SlashCommand(
        command="/triage",
        text="plan",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Step 2: Mock API response for plan generation
    mock_response = MagicMock()
    mock_response.status_code = 202  # Accepted - async processing
    mock_response.json.return_value = {
        'success': True,
        'message': 'Plan generation started'
    }
    mock_triage_api.post.return_value = mock_response
    
    # Step 3: Handle command and measure response time
    import time
    start_time = time.time()
    
    response = await command_handler.handle_command(plan_command)
    
    end_time = time.time()
    response_time = end_time - start_time
    
    # Step 4: Verify response time is within 3 seconds
    assert response_time < 3.0, f"Response took {response_time}s, should be < 3s"
    
    # Step 5: Verify TrIAge API was called correctly
    mock_triage_api.post.assert_called_once()
    call_args = mock_triage_api.post.call_args
    
    # Verify endpoint
    assert '/api/v1/plans/generate' in call_args.args[0]
    
    # Verify request payload
    request_payload = call_args.kwargs['json']
    assert request_payload['user_id'] == 'U12345ABCDE'
    assert request_payload['team_id'] == 'T12345ABCDE'
    assert request_payload['date'] == 'today'
    
    # Step 6: Verify response message
    assert response is not None
    assert response.text is not None
    assert len(response.text) > 0
    
    # Verify response contains blocks
    assert len(response.blocks) > 0
    
    # Verify response indicates plan generation started
    response_text = str(response.blocks)
    assert 'plan' in response_text.lower() or 'generat' in response_text.lower()


@pytest.mark.asyncio
async def test_plan_command_with_date_parameter(command_handler, mock_triage_api):
    """
    Test /triage plan command with date parameter.
    
    Validates: Requirements 4.1
    """
    # Create command with date parameter
    plan_command = SlashCommand(
        command="/triage",
        text="plan 2026-01-20",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API response
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {'success': True}
    mock_triage_api.post.return_value = mock_response
    
    # Handle command
    response = await command_handler.handle_command(plan_command)
    
    # Verify API was called with correct date
    call_args = mock_triage_api.post.call_args
    request_payload = call_args.kwargs['json']
    assert request_payload['date'] == '2026-01-20'
    
    # Verify response
    assert response is not None
    assert len(response.blocks) > 0


@pytest.mark.asyncio
async def test_plan_command_with_invalid_date(command_handler, mock_triage_api):
    """
    Test /triage plan command with invalid date format.
    
    Validates: Requirements 4.5
    """
    # Create command with invalid date
    plan_command = SlashCommand(
        command="/triage",
        text="plan invalid-date",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Handle command
    response = await command_handler.handle_command(plan_command)
    
    # Verify API was NOT called
    mock_triage_api.post.assert_not_called()
    
    # Verify error response
    assert response is not None
    response_text = str(response.blocks)
    assert 'invalid' in response_text.lower() or 'error' in response_text.lower()
    assert 'date' in response_text.lower()


@pytest.mark.asyncio
async def test_status_command_execution(command_handler, mock_triage_api):
    """
    Test complete /triage status command execution.
    
    This integration test verifies:
    1. Command is received and parsed
    2. TrIAge API is called to fetch plan status
    3. Response is delivered with plan information
    
    Validates: Requirements 4.2, 4.4
    """
    # Step 1: Create slash command
    status_command = SlashCommand(
        command="/triage",
        text="status",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Step 2: Mock API response with plan status
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'status': 'approved',
        'date': '2026-01-20',
        'priority_tasks': [
            {'key': 'PROJ-123', 'summary': 'Fix bug'},
            {'key': 'PROJ-456', 'summary': 'Add feature'}
        ],
        'admin_tasks': [
            {'key': 'PROJ-789', 'summary': 'Update docs'}
        ]
    }
    mock_triage_api.get.return_value = mock_response
    
    # Step 3: Handle command and measure response time
    import time
    start_time = time.time()
    
    response = await command_handler.handle_command(status_command)
    
    end_time = time.time()
    response_time = end_time - start_time
    
    # Step 4: Verify response time
    assert response_time < 3.0, f"Response took {response_time}s, should be < 3s"
    
    # Step 5: Verify TrIAge API was called
    mock_triage_api.get.assert_called_once()
    call_args = mock_triage_api.get.call_args
    
    # Verify endpoint
    assert '/api/v1/plans/current' in call_args.args[0]
    
    # Verify query parameters
    query_params = call_args.kwargs['params']
    assert query_params['user_id'] == 'U12345ABCDE'
    assert query_params['team_id'] == 'T12345ABCDE'
    
    # Step 6: Verify response contains plan status
    assert response is not None
    assert len(response.blocks) > 0
    
    response_text = str(response.blocks)
    assert 'approved' in response_text.lower()
    assert '2026-01-20' in response_text
    assert '2' in response_text  # 2 priority tasks
    assert '1' in response_text  # 1 admin task


@pytest.mark.asyncio
async def test_status_command_no_active_plan(command_handler, mock_triage_api):
    """
    Test /triage status command when no active plan exists.
    
    Validates: Requirements 4.2
    """
    # Create command
    status_command = SlashCommand(
        command="/triage",
        text="status",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API response - no plan found
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {'error': 'No active plan'}
    mock_triage_api.get.return_value = mock_response
    
    # Handle command
    response = await command_handler.handle_command(status_command)
    
    # Verify response indicates no plan
    assert response is not None
    response_text = str(response.blocks)
    assert 'no' in response_text.lower() and 'plan' in response_text.lower()


@pytest.mark.asyncio
async def test_help_command_execution(command_handler, mock_triage_api):
    """
    Test complete /triage help command execution.
    
    This integration test verifies:
    1. Command is received and parsed
    2. Help information is returned
    3. Response contains all available commands
    
    Validates: Requirements 4.3, 4.4
    """
    # Step 1: Create slash command
    help_command = SlashCommand(
        command="/triage",
        text="help",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Step 2: Handle command and measure response time
    import time
    start_time = time.time()
    
    response = await command_handler.handle_command(help_command)
    
    end_time = time.time()
    response_time = end_time - start_time
    
    # Step 3: Verify response time
    assert response_time < 3.0, f"Response took {response_time}s, should be < 3s"
    
    # Step 4: Verify no API calls were made (help is local)
    mock_triage_api.post.assert_not_called()
    mock_triage_api.get.assert_not_called()
    
    # Step 5: Verify response contains help information
    assert response is not None
    assert len(response.blocks) > 0
    
    response_text = str(response.blocks)
    
    # Verify all commands are documented
    assert '/triage plan' in response_text
    assert '/triage status' in response_text
    assert '/triage config' in response_text
    assert '/triage help' in response_text
    
    # Verify examples are provided
    assert 'example' in response_text.lower() or 'usage' in response_text.lower()


@pytest.mark.asyncio
async def test_config_command_display(command_handler, mock_triage_api):
    """
    Test /triage config command to display configuration.
    
    Validates: Requirements 10.1
    """
    # Create command
    config_command = SlashCommand(
        command="/triage",
        text="config",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API response with user config
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'notification_channel': 'DM',
        'delivery_time': '09:00',
        'notifications_enabled': True,
        'timezone': 'UTC'
    }
    mock_triage_api.get.return_value = mock_response
    
    # Handle command
    response = await command_handler.handle_command(config_command)
    
    # Verify API was called
    mock_triage_api.get.assert_called_once()
    call_args = mock_triage_api.get.call_args
    assert '/slack-config' in call_args.args[0]
    
    # Verify response contains configuration
    assert response is not None
    response_text = str(response.blocks)
    assert 'DM' in response_text or 'Direct Message' in response_text
    assert '09:00' in response_text
    assert 'Enabled' in response_text or 'enabled' in response_text


@pytest.mark.asyncio
async def test_command_error_handling_api_unavailable(command_handler, mock_triage_api):
    """
    Test error handling when TrIAge API is unavailable.
    
    Validates: Requirements 4.5, 11.3
    """
    # Create command
    plan_command = SlashCommand(
        command="/triage",
        text="plan",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API to raise connection error
    import httpx
    mock_triage_api.post.side_effect = httpx.ConnectError("Connection refused")
    
    # Handle command
    response = await command_handler.handle_command(plan_command)
    
    # Verify error response
    assert response is not None
    response_text = str(response.blocks)
    assert 'error' in response_text.lower() or 'unavailable' in response_text.lower()
    assert 'try again' in response_text.lower()


@pytest.mark.asyncio
async def test_command_error_handling_timeout(command_handler, mock_triage_api):
    """
    Test error handling when API request times out.
    
    Validates: Requirements 4.5, 11.3
    """
    # Create command
    plan_command = SlashCommand(
        command="/triage",
        text="plan",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API to raise timeout
    import httpx
    mock_triage_api.post.side_effect = httpx.TimeoutException("Request timed out")
    
    # Handle command
    response = await command_handler.handle_command(plan_command)
    
    # Verify error response
    assert response is not None
    response_text = str(response.blocks)
    assert 'timeout' in response_text.lower() or 'timed out' in response_text.lower()


@pytest.mark.asyncio
async def test_command_error_handling_unauthorized(command_handler, mock_triage_api):
    """
    Test error handling when user is not authorized.
    
    Validates: Requirements 4.5
    """
    # Create command
    plan_command = SlashCommand(
        command="/triage",
        text="plan",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API to return 401
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {'error': 'Unauthorized'}
    mock_triage_api.post.return_value = mock_response
    
    # Handle command
    response = await command_handler.handle_command(plan_command)
    
    # Verify error response
    assert response is not None
    response_text = str(response.blocks)
    assert 'auth' in response_text.lower() or 'unauthorized' in response_text.lower()


@pytest.mark.asyncio
async def test_command_error_handling_not_configured(command_handler, mock_triage_api):
    """
    Test error handling when user account is not configured.
    
    Validates: Requirements 4.5
    """
    # Create command
    plan_command = SlashCommand(
        command="/triage",
        text="plan",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Mock API to return 404
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {'error': 'User not found'}
    mock_triage_api.post.return_value = mock_response
    
    # Handle command
    response = await command_handler.handle_command(plan_command)
    
    # Verify error response
    assert response is not None
    response_text = str(response.blocks)
    assert 'config' in response_text.lower() or 'not configured' in response_text.lower()


@pytest.mark.asyncio
async def test_unknown_command_handling(command_handler, mock_triage_api):
    """
    Test handling of unknown subcommands.
    
    Validates: Requirements 4.5
    """
    # Create command with unknown subcommand
    unknown_command = SlashCommand(
        command="/triage",
        text="unknown_subcommand",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    # Handle command
    response = await command_handler.handle_command(unknown_command)
    
    # Verify no API calls were made
    mock_triage_api.post.assert_not_called()
    mock_triage_api.get.assert_not_called()
    
    # Verify error response
    assert response is not None
    response_text = str(response.blocks)
    assert 'unknown' in response_text.lower() or 'invalid' in response_text.lower()
    assert 'help' in response_text.lower()


@pytest.mark.asyncio
async def test_multiple_commands_sequential(command_handler, mock_triage_api):
    """
    Test executing multiple commands sequentially.
    
    Verifies that command handler maintains state correctly across
    multiple invocations.
    
    Validates: Requirements 4.1, 4.2, 4.3
    """
    # Mock API responses
    mock_plan_response = MagicMock()
    mock_plan_response.status_code = 202
    mock_plan_response.json.return_value = {'success': True}
    
    mock_status_response = MagicMock()
    mock_status_response.status_code = 200
    mock_status_response.json.return_value = {
        'status': 'pending',
        'date': '2026-01-20',
        'priority_tasks': [],
        'admin_tasks': []
    }
    
    # Set up mock to return different responses
    mock_triage_api.post.return_value = mock_plan_response
    mock_triage_api.get.return_value = mock_status_response
    
    # Execute plan command
    plan_command = SlashCommand(
        command="/triage",
        text="plan",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    plan_response = await command_handler.handle_command(plan_command)
    assert plan_response is not None
    assert len(plan_response.blocks) > 0
    
    # Execute status command
    status_command = SlashCommand(
        command="/triage",
        text="status",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    status_response = await command_handler.handle_command(status_command)
    assert status_response is not None
    assert len(status_response.blocks) > 0
    
    # Execute help command
    help_command = SlashCommand(
        command="/triage",
        text="help",
        user_id="U12345ABCDE",
        team_id="T12345ABCDE",
        channel_id="C12345ABCDE",
        response_url="https://hooks.slack.com/commands/test"
    )
    
    help_response = await command_handler.handle_command(help_command)
    assert help_response is not None
    assert len(help_response.blocks) > 0
    
    # Verify all commands were processed
    assert mock_triage_api.post.call_count == 1  # plan command
    assert mock_triage_api.get.call_count == 1   # status command


@pytest.mark.asyncio
async def test_command_handler_cleanup(command_handler):
    """
    Test that command handler properly cleans up resources.
    
    Validates proper resource management.
    """
    # Verify handler can be closed
    await command_handler.close()
    
    # Verify HTTP client was closed
    command_handler.http_client.aclose.assert_called_once()
