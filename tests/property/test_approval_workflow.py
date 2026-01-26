# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for approval workflow.

Feature: slack-integration
Property 4: Approval State Transition
Property 5: Rejection Feedback Collection

Validates: Requirements 3.2, 3.3, 3.5, 6.1, 6.2, 6.3
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings, assume
from slack_bot.models import BlockAction
from slack_bot.interaction_handler import InteractionHandler
from slack_bot.message_formatter import MessageFormatter


# Custom strategies

@st.composite
def slack_user_id_strategy(draw):
    """Generate valid Slack user IDs (format: U + 8-11 alphanumeric chars)."""
    length = draw(st.integers(min_value=8, max_value=11))
    chars = ''.join(draw(st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')) for _ in range(length))
    return f"U{chars}"


@st.composite
def slack_team_id_strategy(draw):
    """Generate valid Slack team IDs (format: T + 8-11 alphanumeric chars)."""
    length = draw(st.integers(min_value=8, max_value=11))
    chars = ''.join(draw(st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')) for _ in range(length))
    return f"T{chars}"


@st.composite
def slack_channel_id_strategy(draw):
    """Generate valid Slack channel IDs."""
    length = draw(st.integers(min_value=8, max_value=11))
    chars = ''.join(draw(st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')) for _ in range(length))
    return f"C{chars}"


@st.composite
def plan_id_strategy(draw):
    """Generate valid plan IDs."""
    return f"plan_{draw(st.text(min_size=8, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))}"


@st.composite
def message_ts_strategy(draw):
    """Generate valid Slack message timestamps."""
    timestamp = draw(st.integers(min_value=1600000000, max_value=2000000000))
    microseconds = draw(st.integers(min_value=0, max_value=999999))
    return f"{timestamp}.{microseconds:06d}"


@st.composite
def approve_action_strategy(draw):
    """Generate valid approve button actions."""
    return BlockAction(
        action_id="approve_plan",
        value=draw(plan_id_strategy()),
        user_id=draw(slack_user_id_strategy()),
        team_id=draw(slack_team_id_strategy()),
        message_ts=draw(message_ts_strategy()),
        response_url=draw(st.from_regex(r'https://hooks\.slack\.com/actions/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+')),
        channel_id=draw(slack_channel_id_strategy()),
    )


@st.composite
def reject_action_strategy(draw):
    """Generate valid reject button actions."""
    return BlockAction(
        action_id="reject_plan",
        value=draw(plan_id_strategy()),
        user_id=draw(slack_user_id_strategy()),
        team_id=draw(slack_team_id_strategy()),
        message_ts=draw(message_ts_strategy()),
        response_url=draw(st.from_regex(r'https://hooks\.slack\.com/actions/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+')),
        channel_id=draw(slack_channel_id_strategy()),
    )


# Property Tests

# Feature: slack-integration, Property 4: Approval State Transition
@given(action=approve_action_strategy())
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_approval_state_transition(action):
    """
    For any plan approval action, executing the action should update the plan
    state in the TrIAge API and disable the action buttons in the Slack message.
    
    Property: Approval actions result in API state update and message update.
    
    Validates: Requirements 3.2, 3.5
    """
    # Create mock HTTP clients
    mock_triage_client = AsyncMock()
    mock_slack_client = AsyncMock()
    
    # Mock successful API response
    mock_triage_response = MagicMock()
    mock_triage_response.status_code = 200
    mock_triage_response.json.return_value = {"status": "approved"}
    mock_triage_client.post = AsyncMock(return_value=mock_triage_response)
    
    # Mock successful Slack update response
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": action.message_ts}
    mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Create handler with mocked clients
    formatter = MessageFormatter()
    handler = InteractionHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test",
        message_formatter=formatter
    )
    
    # Replace clients with mocks
    handler.triage_client = mock_triage_client
    handler.slack_client = mock_slack_client
    
    # Execute approval action
    await handler.handle_approve(action)
    
    # Verify TrIAge API was called to approve plan
    mock_triage_client.post.assert_called_once()
    call_args = mock_triage_client.post.call_args
    assert f"/api/v1/plans/{action.value}/approve" in str(call_args)
    assert call_args[1]["json"]["user_id"] == action.user_id
    assert call_args[1]["json"]["team_id"] == action.team_id
    
    # Verify Slack message was updated
    mock_slack_client.post.assert_called_once()
    slack_call_args = mock_slack_client.post.call_args
    assert "/chat.update" in str(slack_call_args)
    
    # Verify message update includes approval status
    update_payload = slack_call_args[1]["json"]
    assert update_payload["channel"] == action.channel_id
    assert update_payload["ts"] == action.message_ts
    assert "Approved" in update_payload["text"]
    
    # Verify blocks contain approval indicator
    blocks = update_payload["blocks"]
    assert any("✅" in str(block) or "Approved" in str(block) for block in blocks)


# Feature: slack-integration, Property 4: Rejection State Transition
@given(action=reject_action_strategy())
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_rejection_state_transition(action):
    """
    For any plan rejection action, executing the action should update the plan
    state in the TrIAge API and disable the action buttons in the Slack message.
    
    Property: Rejection actions result in API state update and message update.
    
    Validates: Requirements 3.2, 3.5
    """
    # Create mock HTTP clients
    mock_triage_client = AsyncMock()
    mock_slack_client = AsyncMock()
    
    # Mock successful API response
    mock_triage_response = MagicMock()
    mock_triage_response.status_code = 200
    mock_triage_response.json.return_value = {"status": "rejected"}
    mock_triage_client.post = AsyncMock(return_value=mock_triage_response)
    
    # Mock successful Slack responses
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": action.message_ts}
    mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Create handler with mocked clients
    formatter = MessageFormatter()
    handler = InteractionHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test",
        message_formatter=formatter
    )
    
    # Replace clients with mocks
    handler.triage_client = mock_triage_client
    handler.slack_client = mock_slack_client
    
    # Execute rejection action
    await handler.handle_reject(action)
    
    # Verify TrIAge API was called to reject plan
    assert mock_triage_client.post.call_count >= 1
    first_call_args = mock_triage_client.post.call_args_list[0]
    assert f"/api/v1/plans/{action.value}/reject" in str(first_call_args)
    assert first_call_args[1]["json"]["user_id"] == action.user_id
    assert first_call_args[1]["json"]["team_id"] == action.team_id
    
    # Verify Slack message was updated (at least once for status update)
    assert mock_slack_client.post.call_count >= 1
    
    # Find the update call (not the feedback thread message)
    update_calls = [
        call for call in mock_slack_client.post.call_args_list
        if "/chat.update" in str(call)
    ]
    assert len(update_calls) >= 1
    
    # Verify message update includes rejection status
    update_payload = update_calls[0][1]["json"]
    assert update_payload["channel"] == action.channel_id
    assert update_payload["ts"] == action.message_ts
    assert "Rejected" in update_payload["text"]
    
    # Verify blocks contain rejection indicator
    blocks = update_payload["blocks"]
    assert any("❌" in str(block) or "Rejected" in str(block) for block in blocks)


# Feature: slack-integration, Property 5: Rejection Feedback Collection
@given(action=reject_action_strategy())
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_rejection_feedback_collection(action):
    """
    For any plan rejection, the system should create a feedback thread and
    prompt the user for rejection reason.
    
    Property: Rejection creates feedback collection thread.
    
    Validates: Requirements 3.3, 6.1, 6.2, 6.3
    """
    # Create mock HTTP clients
    mock_triage_client = AsyncMock()
    mock_slack_client = AsyncMock()
    
    # Mock successful API response
    mock_triage_response = MagicMock()
    mock_triage_response.status_code = 200
    mock_triage_response.json.return_value = {"status": "rejected"}
    mock_triage_client.post = AsyncMock(return_value=mock_triage_response)
    
    # Mock successful Slack responses
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True, "ts": action.message_ts}
    mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Create handler with mocked clients
    formatter = MessageFormatter()
    handler = InteractionHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test",
        message_formatter=formatter
    )
    
    # Replace clients with mocks
    handler.triage_client = mock_triage_client
    handler.slack_client = mock_slack_client
    
    # Execute rejection action
    await handler.handle_reject(action)
    
    # Verify TrIAge API was called to reject plan
    assert mock_triage_client.post.call_count >= 1
    
    # Verify Slack API was called multiple times (update + feedback thread)
    assert mock_slack_client.post.call_count >= 2
    
    # Find the feedback thread message call
    feedback_calls = [
        call for call in mock_slack_client.post.call_args_list
        if "/chat.postMessage" in str(call)
    ]
    
    # Should have at least one postMessage call for feedback
    assert len(feedback_calls) >= 1
    
    # Verify feedback message is in a thread
    feedback_payload = feedback_calls[0][1]["json"]
    assert feedback_payload["channel"] == action.channel_id
    assert feedback_payload["thread_ts"] == action.message_ts
    
    # Verify feedback message prompts for reason
    feedback_text = str(feedback_payload.get("blocks", [])) + feedback_payload.get("text", "")
    assert any(keyword in feedback_text.lower() for keyword in ["feedback", "why", "reason", "rejected"])


# Feature: slack-integration, Property 4: Approval Idempotency
@given(action=approve_action_strategy())
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_approval_idempotency(action):
    """
    For any plan approval action, if the plan is already approved, the system
    should handle it gracefully without error.
    
    Property: Duplicate approval actions are handled gracefully.
    
    Validates: Requirements 3.2, 3.5
    """
    # Create mock HTTP clients
    mock_triage_client = AsyncMock()
    mock_slack_client = AsyncMock()
    
    # Mock 409 Conflict response (already processed)
    mock_triage_response = MagicMock()
    mock_triage_response.status_code = 409
    mock_triage_response.json.return_value = {"error": "already_processed"}
    mock_triage_client.post = AsyncMock(return_value=mock_triage_response)
    
    # Mock successful Slack response
    mock_slack_response = MagicMock()
    mock_slack_response.json.return_value = {"ok": True}
    mock_slack_client.post = AsyncMock(return_value=mock_slack_response)
    
    # Create handler with mocked clients
    formatter = MessageFormatter()
    handler = InteractionHandler(
        triage_api_url="https://api.triage.example.com",
        triage_api_token="test_token",
        slack_bot_token="xoxb-test",
        message_formatter=formatter
    )
    
    # Replace clients with mocks
    handler.triage_client = mock_triage_client
    handler.slack_client = mock_slack_client
    
    # Execute approval action (should not raise exception)
    await handler.handle_approve(action)
    
    # Verify TrIAge API was called
    mock_triage_client.post.assert_called_once()
    
    # Verify ephemeral error message was sent to user
    assert mock_slack_client.post.call_count >= 1
    ephemeral_calls = [
        call for call in mock_slack_client.post.call_args_list
        if "/chat.postEphemeral" in str(call)
    ]
    assert len(ephemeral_calls) >= 1
    
    # Verify error message mentions already processed
    ephemeral_payload = ephemeral_calls[0][1]["json"]
    error_text = str(ephemeral_payload.get("blocks", [])) + ephemeral_payload.get("text", "")
    assert any(keyword in error_text.lower() for keyword in ["already", "processed"])
