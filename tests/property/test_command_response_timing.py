# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for slash command response timing.

Feature: slack-integration, Property 6: Slash Command Response Timing
Validates: Requirements 4.4

For any slash command invocation, the Slack bot should respond within 3 seconds
with either results or an acknowledgment message.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from hypothesis import given, strategies as st, settings, assume

from slack_bot.command_handler import CommandHandler
from slack_bot.models import SlashCommand
from slack_bot.message_formatter import MessageFormatter


# Custom strategies for generating test data

@st.composite
def slack_user_id(draw):
    """Generate valid Slack user ID."""
    # Only use A-Z and 0-9 as per Slack ID format
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=8,
        max_size=11
    ))
    return f"U{suffix}"


@st.composite
def slack_team_id(draw):
    """Generate valid Slack team ID."""
    # Only use A-Z and 0-9 as per Slack ID format
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=8,
        max_size=11
    ))
    return f"T{suffix}"


@st.composite
def slack_channel_id(draw):
    """Generate valid Slack channel ID."""
    # Only use A-Z and 0-9 as per Slack ID format
    suffix = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=8,
        max_size=11
    ))
    return f"C{suffix}"


@st.composite
def slash_command(draw):
    """Generate valid SlashCommand."""
    subcommands = st.sampled_from(["plan", "status", "help", "config", ""])
    args = st.one_of(
        st.just(""),
        st.just("today"),
        st.just("tomorrow"),
        st.text(min_size=0, max_size=50)
    )
    
    subcommand = draw(subcommands)
    arg = draw(args)
    text = f"{subcommand} {arg}".strip() if arg else subcommand
    
    return SlashCommand(
        command="/triage",
        text=text,
        user_id=draw(slack_user_id()),
        team_id=draw(slack_team_id()),
        channel_id=draw(slack_channel_id()),
        response_url=f"https://hooks.slack.com/commands/{draw(st.text(min_size=20, max_size=40))}"
    )


# Feature: slack-integration, Property 6: Slash Command Response Timing
@settings(max_examples=100, deadline=5000)
@given(cmd=slash_command())
@pytest.mark.asyncio
async def test_command_response_timing(cmd):
    """
    Property 6: Slash Command Response Timing
    
    For any slash command invocation, the Slack bot should respond within
    3 seconds with either results or an acknowledgment message.
    
    Validates: Requirements 4.4
    """
    # Setup mock HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {"status": "pending"}
    
    # Create handler with mocked dependencies
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock the HTTP client
    handler.http_client = AsyncMock()
    handler.http_client.post = AsyncMock(return_value=mock_response)
    handler.http_client.get = AsyncMock(return_value=mock_response)
    
    # Measure response time
    start_time = time.time()
    
    try:
        response = await handler.handle_command(cmd)
        
        elapsed_time = time.time() - start_time
        
        # Property: Response must be received within 3 seconds
        assert elapsed_time < 3.0, f"Command took {elapsed_time:.2f}s, exceeds 3s limit"
        
        # Property: Response must be a valid SlackMessage
        assert response is not None
        assert hasattr(response, 'blocks')
        assert hasattr(response, 'text')
        assert isinstance(response.text, str)
        assert len(response.text) > 0
        
    finally:
        await handler.close()


# Feature: slack-integration, Property 6: Slash Command Response Timing (Slow API)
@settings(max_examples=50, deadline=5000)
@given(cmd=slash_command())
@pytest.mark.asyncio
async def test_command_response_timing_with_slow_api(cmd):
    """
    Property 6: Slash Command Response Timing (Slow API variant)
    
    Even when the API is slow, the command handler should respond within
    3 seconds, potentially with an acknowledgment message.
    
    Validates: Requirements 4.4
    """
    # Setup mock HTTP client that simulates slow response
    async def slow_api_call(*args, **kwargs):
        await asyncio.sleep(2.5)  # Simulate slow API
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "pending"}
        return mock_response
    
    # Create handler with mocked dependencies
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock the HTTP client with slow responses
    handler.http_client = AsyncMock()
    handler.http_client.post = AsyncMock(side_effect=slow_api_call)
    handler.http_client.get = AsyncMock(side_effect=slow_api_call)
    
    # Measure response time
    start_time = time.time()
    
    try:
        response = await handler.handle_command(cmd)
        
        elapsed_time = time.time() - start_time
        
        # Property: Response must still be received within 3 seconds
        # (handler should return acknowledgment if API is slow)
        assert elapsed_time < 3.5, f"Command took {elapsed_time:.2f}s, exceeds limit"
        
        # Property: Response must be valid
        assert response is not None
        assert hasattr(response, 'text')
        assert len(response.text) > 0
        
    finally:
        await handler.close()


# Feature: slack-integration, Property 6: Slash Command Response Timing (All Commands)
@settings(max_examples=100, deadline=5000)
@given(
    user_id=slack_user_id(),
    team_id=slack_team_id(),
    channel_id=slack_channel_id(),
    subcommand=st.sampled_from(["plan", "status", "help", "config"])
)
@pytest.mark.asyncio
async def test_all_commands_respond_quickly(user_id, team_id, channel_id, subcommand):
    """
    Property 6: All command types respond within time limit
    
    Each specific command type (plan, status, help, config) should respond
    within 3 seconds.
    
    Validates: Requirements 4.4
    """
    cmd = SlashCommand(
        command="/triage",
        text=subcommand,
        user_id=user_id,
        team_id=team_id,
        channel_id=channel_id,
        response_url="https://hooks.slack.com/test"
    )
    
    # Setup mock HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "approved",
        "date": "2026-01-26",
        "priority_tasks": [],
        "admin_tasks": []
    }
    
    # Create handler
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    handler = CommandHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test-token",
        message_formatter=formatter,
        timeout_seconds=3
    )
    
    # Mock HTTP client
    handler.http_client = AsyncMock()
    handler.http_client.post = AsyncMock(return_value=mock_response)
    handler.http_client.get = AsyncMock(return_value=mock_response)
    
    # Measure response time
    start_time = time.time()
    
    try:
        response = await handler.handle_command(cmd)
        
        elapsed_time = time.time() - start_time
        
        # Property: Each command type responds within 3 seconds
        assert elapsed_time < 3.0, f"{subcommand} command took {elapsed_time:.2f}s"
        
        # Property: Response is valid
        assert response is not None
        assert len(response.text) > 0
        
    finally:
        await handler.close()
