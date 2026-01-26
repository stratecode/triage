# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for CommandHandler.

Tests specific examples and edge cases for each slash command.
Validates: Requirements 4.1, 4.2, 4.3, 10.1
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from slack_bot.command_handler import CommandHandler
from slack_bot.models import SlashCommand
from slack_bot.message_formatter import MessageFormatter


@pytest.fixture
def command_handler():
    """Create CommandHandler instance for testing."""
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client
    handler.http_client = AsyncMock()
    
    yield handler
    
    # Cleanup
    # Note: In real tests, we'd await handler.close() but pytest fixtures don't support async cleanup easily


@pytest.fixture
def sample_command():
    """Create sample SlashCommand for testing."""
    return SlashCommand(
        command="/triage",
        text="help",
        user_id="U12345ABC",
        team_id="T12345ABC",
        channel_id="C12345ABC",
        response_url="https://hooks.slack.com/commands/test123"
    )


# Tests for /triage plan command

@pytest.mark.asyncio
async def test_plan_command_today(command_handler, sample_command):
    """
    Test /triage plan with 'today' argument.
    Validates: Requirements 4.1
    """
    sample_command.text = "plan today"
    
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 202
    command_handler.http_client.post = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    assert "generating" in response.text.lower() or "plan" in response.text.lower()
    
    # Verify API was called with correct parameters
    command_handler.http_client.post.assert_called_once()
    call_args = command_handler.http_client.post.call_args
    assert call_args[0][0] == "/api/v1/plans/generate"
    assert call_args[1]["json"]["date"] == "today"


@pytest.mark.asyncio
async def test_plan_command_tomorrow(command_handler, sample_command):
    """
    Test /triage plan with 'tomorrow' argument.
    Validates: Requirements 4.1
    """
    sample_command.text = "plan tomorrow"
    
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 202
    command_handler.http_client.post = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    assert "tomorrow" in response.text.lower()
    
    # Verify API was called with correct date
    call_args = command_handler.http_client.post.call_args
    assert call_args[1]["json"]["date"] == "tomorrow"


@pytest.mark.asyncio
async def test_plan_command_specific_date(command_handler, sample_command):
    """
    Test /triage plan with specific date in YYYY-MM-DD format.
    Validates: Requirements 4.1
    """
    sample_command.text = "plan 2026-01-30"
    
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 202
    command_handler.http_client.post = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    
    # Verify API was called with correct date
    call_args = command_handler.http_client.post.call_args
    assert call_args[1]["json"]["date"] == "2026-01-30"


@pytest.mark.asyncio
async def test_plan_command_invalid_date(command_handler, sample_command):
    """
    Test /triage plan with invalid date format.
    Validates: Requirements 4.1
    """
    sample_command.text = "plan invalid-date"
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    assert "invalid" in response.text.lower()
    assert "yyyy-mm-dd" in str(response.blocks).lower()
    
    # Verify API was NOT called
    command_handler.http_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_plan_command_no_date(command_handler, sample_command):
    """
    Test /triage plan without date argument (defaults to today).
    Validates: Requirements 4.1
    """
    sample_command.text = "plan"
    
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 202
    command_handler.http_client.post = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    
    # Verify API was called with 'today' as default
    call_args = command_handler.http_client.post.call_args
    assert call_args[1]["json"]["date"] == "today"


# Tests for /triage status command

@pytest.mark.asyncio
async def test_status_command_with_active_plan(command_handler, sample_command):
    """
    Test /triage status when user has an active plan.
    Validates: Requirements 4.2
    """
    sample_command.text = "status"
    
    # Mock API response with active plan
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "approved",
        "date": "2026-01-26",
        "priority_tasks": [
            {"key": "PROJ-123", "summary": "Task 1"},
            {"key": "PROJ-124", "summary": "Task 2"}
        ],
        "admin_tasks": [
            {"key": "PROJ-125", "summary": "Admin task"}
        ]
    }
    command_handler.http_client.get = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    assert "approved" in blocks_text
    assert "2026-01-26" in blocks_text
    assert "2" in blocks_text  # 2 priority tasks
    assert "1" in blocks_text  # 1 admin task


@pytest.mark.asyncio
async def test_status_command_without_active_plan(command_handler, sample_command):
    """
    Test /triage status when user has no active plan.
    Validates: Requirements 4.2
    """
    sample_command.text = "status"
    
    # Mock API response with 404 (no plan)
    mock_response = MagicMock()
    mock_response.status_code = 404
    command_handler.http_client.get = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    assert "no active plan" in blocks_text or "don't have" in blocks_text
    assert "/triage plan" in str(response.blocks)


# Tests for /triage help command

@pytest.mark.asyncio
async def test_help_command_completeness(command_handler, sample_command):
    """
    Test /triage help displays all available commands.
    Validates: Requirements 4.3
    """
    sample_command.text = "help"
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Verify all commands are documented
    assert "/triage plan" in str(response.blocks)
    assert "/triage status" in str(response.blocks)
    assert "/triage config" in str(response.blocks)
    assert "/triage help" in str(response.blocks)
    
    # Verify examples are provided
    assert "example" in blocks_text


@pytest.mark.asyncio
async def test_help_command_empty_text(command_handler, sample_command):
    """
    Test /triage with no subcommand defaults to help.
    Validates: Requirements 4.3
    """
    sample_command.text = ""
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should show help
    assert "available commands" in blocks_text or "help" in blocks_text


# Tests for /triage config command

@pytest.mark.asyncio
async def test_config_command_display(command_handler, sample_command):
    """
    Test /triage config displays user configuration.
    Validates: Requirements 10.1
    """
    sample_command.text = "config"
    
    # Mock API response with config
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "notification_channel": "C12345ABC",
        "delivery_time": "09:00",
        "notifications_enabled": True,
        "timezone": "America/New_York"
    }
    command_handler.http_client.get = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks)
    
    # Verify config details are displayed
    assert "09:00" in blocks_text
    assert "America/New_York" in blocks_text
    assert "Enabled" in blocks_text or "enabled" in blocks_text.lower()


@pytest.mark.asyncio
async def test_config_command_dm_channel(command_handler, sample_command):
    """
    Test /triage config displays DM as notification channel.
    Validates: Requirements 10.1
    """
    sample_command.text = "config"
    
    # Mock API response with DM channel
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "notification_channel": "DM",
        "delivery_time": "09:00",
        "notifications_enabled": True,
        "timezone": "UTC"
    }
    command_handler.http_client.get = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks)
    
    # Verify DM is displayed as "Direct Message"
    assert "Direct Message" in blocks_text


@pytest.mark.asyncio
async def test_config_command_not_found(command_handler, sample_command):
    """
    Test /triage config when user configuration not found.
    Validates: Requirements 10.1
    """
    sample_command.text = "config"
    
    # Mock API response with 404
    mock_response = MagicMock()
    mock_response.status_code = 404
    command_handler.http_client.get = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should indicate config not found
    assert "not found" in blocks_text or "not been set up" in blocks_text
    assert "administrator" in blocks_text


# Edge case tests

@pytest.mark.asyncio
async def test_unknown_subcommand(command_handler, sample_command):
    """
    Test handling of unknown subcommand.
    Validates: Requirements 4.5
    """
    sample_command.text = "unknown_command"
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should indicate unknown command
    assert "unknown" in blocks_text
    assert "/triage help" in str(response.blocks)


@pytest.mark.asyncio
async def test_api_401_error(command_handler, sample_command):
    """
    Test handling of 401 authentication error.
    Validates: Requirements 4.5
    """
    sample_command.text = "plan"
    
    # Mock API response with 401
    mock_response = MagicMock()
    mock_response.status_code = 401
    command_handler.http_client.post = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should indicate authentication failure
    assert "authentication" in blocks_text or "unauthorized" in blocks_text


@pytest.mark.asyncio
async def test_api_404_not_configured(command_handler, sample_command):
    """
    Test handling of 404 when user not configured.
    Validates: Requirements 4.5
    """
    sample_command.text = "plan"
    
    # Mock API response with 404
    mock_response = MagicMock()
    mock_response.status_code = 404
    command_handler.http_client.post = AsyncMock(return_value=mock_response)
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should indicate not configured
    assert "not configured" in blocks_text
    assert "/triage config" in str(response.blocks)


@pytest.mark.asyncio
async def test_network_timeout(command_handler, sample_command):
    """
    Test handling of network timeout.
    Validates: Requirements 4.5
    """
    sample_command.text = "status"
    
    # Mock timeout exception
    command_handler.http_client.get = AsyncMock(
        side_effect=httpx.TimeoutException("Request timed out")
    )
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should indicate service unavailable or connection issue
    assert "unavailable" in blocks_text or "connect" in blocks_text or "try again" in blocks_text


@pytest.mark.asyncio
async def test_network_connection_error(command_handler, sample_command):
    """
    Test handling of network connection error.
    Validates: Requirements 4.5
    """
    sample_command.text = "plan"
    
    # Mock connection error
    command_handler.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection failed")
    )
    
    response = await command_handler.handle_command(sample_command)
    
    assert response is not None
    blocks_text = str(response.blocks).lower()
    
    # Should indicate connection issue
    assert "unavailable" in blocks_text or "connect" in blocks_text
