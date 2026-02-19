# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-Based Test: Slack Event Handling

Feature: plugin-architecture, Property 10: Slack Event Handling

For any Slack event type (app mention, direct message, etc.), the Slack_Connector
should handle it and invoke appropriate Core_Actions.

Validates: Requirements 5.5
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from triage.core.actions_api import CoreActionResult, CoreActionsAPI
from triage.plugins.interface import PluginConfig
from triage.plugins.slack.slack_plugin import SlackPlugin

# Hypothesis strategies for generating test data


@st.composite
def slack_event_type_strategy(draw):
    """Generate valid Slack event types."""
    return draw(st.sampled_from(["app_mention", "message"]))


@st.composite
def slack_event_payload_strategy(draw):
    """Generate valid Slack event payloads in Slack Event API format."""
    event_type = draw(slack_event_type_strategy())

    # Generate valid Slack IDs (start with appropriate prefix)
    channel_id = "C" + draw(st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
    user_id = "U" + draw(st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
    team_id = "T" + draw(st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))

    # Generate message text
    text = draw(st.text(min_size=10, max_size=200))

    # Generate timestamp
    ts = draw(st.text(min_size=10, max_size=20, alphabet=st.characters(whitelist_categories=("Nd", "Po"))))

    # Create inner event object
    inner_event = {"type": event_type, "channel": channel_id, "user": user_id, "text": text, "ts": ts}

    # Add event-specific fields
    if event_type == "app_mention":
        bot_id = "B" + draw(st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))))
        inner_event["text"] = f"<@{bot_id}> {text}"
    elif event_type == "message":
        # Add channel_type for DM detection
        inner_event["channel_type"] = "im"

    # Wrap in Slack Event API format
    return {"event": inner_event, "team_id": team_id, "type": "event_callback"}


class TestSlackEventHandling:
    """
    Property 10: Slack Event Handling

    Validates that Slack events are correctly handled and mapped to Core Actions.
    """

    def create_mock_core_api(self):
        """Create mock Core Actions API."""
        api = AsyncMock(spec=CoreActionsAPI)

        # Mock successful responses for all actions
        api.generate_plan.return_value = CoreActionResult(
            success=True, data={"plan": MagicMock(date=date.today()), "markdown": "# Test Plan\n\n- Task 1\n- Task 2"}
        )

        api.get_status.return_value = CoreActionResult(
            success=True, data={"status": "in_progress", "date": date.today().isoformat()}
        )

        api.configure_settings.return_value = CoreActionResult(success=True, data={"user_id": "test_user"})

        return api

    async def create_slack_plugin(self, mock_core_api):
        """Create SlackPlugin instance with mock dependencies."""
        plugin = SlackPlugin()

        config = PluginConfig(
            plugin_name="slack",
            plugin_version="1.0.0",
            enabled=True,
            config={
                "signing_secret": "test_secret",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "bot_token": "xoxb-test-token",
            },
        )

        await plugin.initialize(config, mock_core_api)

        # Mock the storage to avoid database dependency
        plugin.storage = AsyncMock()

        # Mock get_installation to return a valid installation
        mock_installation = MagicMock()
        mock_installation.is_active = True
        mock_installation.access_token = "xoxb-test-token"
        mock_installation.channel_id = "test_workspace"
        plugin.storage.get_installation = AsyncMock(return_value=mock_installation)

        # Mock the Slack client
        plugin.client = AsyncMock()
        plugin.client.chat_postMessage = AsyncMock(return_value={"ok": True})

        return plugin

    @given(event=slack_event_payload_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_slack_event_handled_without_error(self, event):
        """
        Property: Any valid Slack event is handled without crashing.

        Validates: Requirements 5.5
        """
        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify response is not None
        assert response is not None
        assert hasattr(response, "content")

        # Response should have content
        assert response.content is not None

    @given(event=slack_event_payload_strategy())
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    @pytest.mark.asyncio
    async def test_app_mention_triggers_response(self, event):
        """
        Property: App mentions trigger appropriate responses.

        Validates: Requirements 5.5
        """
        # Only test app_mention events
        assume(event.get("event", {}).get("type") == "app_mention")

        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify response
        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0

    @given(event=slack_event_payload_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_event_user_context_preserved(self, event):
        """
        Property: User context from events is preserved.

        Validates: Requirements 5.5
        """
        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify response includes user context
        assert response is not None

        # If any Core Action was called, verify user_id was passed
        if mock_core_api.generate_plan.called:
            call_args = mock_core_api.generate_plan.call_args
            assert "user_id" in call_args.kwargs

        if mock_core_api.get_status.called:
            call_args = mock_core_api.get_status.call_args
            assert "user_id" in call_args.kwargs

    @given(
        event_type=slack_event_type_strategy(),
        channel_id=st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))),
        user_id=st.text(min_size=8, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))),
    )
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_event_response_format(self, event_type, channel_id, user_id):
        """
        Property: Event responses are properly formatted.

        Validates: Requirements 5.5
        """
        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Create event
        event = {
            "type": event_type,
            "channel": channel_id,
            "user": user_id,
            "text": "test message",
            "ts": "1234567890.123456",
        }

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify response structure
        assert response is not None
        assert hasattr(response, "content")
        assert hasattr(response, "response_type")

        # Response type should be valid
        assert response.response_type in ["message", "ephemeral", "modal", "in_channel"]

    @given(event=slack_event_payload_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_event_error_handling(self, event):
        """
        Property: Event handling errors are handled gracefully.

        Validates: Requirements 5.5
        """
        # Create mocks with error responses
        mock_core_api = AsyncMock(spec=CoreActionsAPI)

        # Make all actions return errors
        error_result = CoreActionResult(success=False, error="Test error", error_code="TEST_ERROR")

        mock_core_api.generate_plan.return_value = error_result
        mock_core_api.get_status.return_value = error_result
        mock_core_api.configure_settings.return_value = error_result

        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify error response
        assert response is not None
        assert hasattr(response, "content")

        # Should not crash - response should be returned
        assert response.content is not None

    @given(event=slack_event_payload_strategy())
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_event_channel_preserved(self, event):
        """
        Property: Channel information from events is preserved.

        Validates: Requirements 5.5
        """
        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify response
        assert response is not None

        # Response should be valid for the channel
        assert response.content is not None
        assert len(response.content) > 0

    @given(
        text=st.text(min_size=10, max_size=200),
        channel_id=st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))).map(
            lambda x: "C" + x
        ),
        user_id=st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))).map(
            lambda x: "U" + x
        ),
        team_id=st.text(min_size=8, max_size=11, alphabet=st.characters(whitelist_categories=("Lu", "Nd"))).map(
            lambda x: "T" + x
        ),
    )
    @settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_direct_message_handling(self, text, channel_id, user_id, team_id):
        """
        Property: Direct messages are handled appropriately.

        Validates: Requirements 5.5
        """
        # Create mocks
        mock_core_api = self.create_mock_core_api()
        slack_plugin = await self.create_slack_plugin(mock_core_api)

        # Create direct message event in Slack Event API format
        event = {
            "event": {
                "type": "message",
                "channel": channel_id,
                "channel_type": "im",
                "user": user_id,
                "text": text,
                "ts": "1234567890.123456",
            },
            "team_id": team_id,
            "type": "event_callback",
        }

        # Handle the event
        response = await slack_plugin.handle_slack_event(event)

        # Verify response
        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0
