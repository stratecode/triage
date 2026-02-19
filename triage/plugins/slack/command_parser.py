# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Slack Command Parser

Parses Slack slash commands and interactive component payloads into
channel-agnostic PluginMessage objects.

Validates: Requirements 8.1, 8.2, 8.3
"""

import logging
from typing import Any, Dict

from ..interface import PluginMessage

logger = logging.getLogger(__name__)


class SlackCommandParser:
    """
    Parses Slack commands and events into PluginMessage objects.

    Handles:
    - Slash commands (/triage plan, /triage status, etc.)
    - Interactive component events (button clicks)
    - App mentions and direct messages

    Validates: Requirements 8.1, 8.2, 8.3
    """

    @staticmethod
    def parse_slash_command(payload: Dict[str, Any]) -> PluginMessage:
        """
        Parse Slack slash command payload.

        Slack sends slash commands as form-encoded data with fields:
        - team_id: Workspace ID
        - user_id: User ID
        - command: The command (/triage)
        - text: Command arguments
        - channel_id: Channel where command was invoked
        - response_url: URL for delayed responses

        Args:
            payload: Slack slash command payload

        Returns:
            PluginMessage with parsed command and parameters

        Validates: Requirements 8.1, 8.2
        """
        team_id = payload.get("team_id", "")
        user_id = payload.get("user_id", "")
        text = payload.get("text", "").strip()
        channel_id = payload.get("channel_id", "")
        response_url = payload.get("response_url", "")

        # Parse command and parameters from text
        # Format: /triage <command> [param1=value1] [param2=value2]
        parts = text.split() if text else []
        command = parts[0] if parts else "help"

        # Parse parameters (key=value format)
        parameters = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                parameters[key.strip()] = value.strip()
            else:
                # Treat as positional parameter
                parameters[f"arg_{len(parameters)}"] = part

        logger.info(
            "Parsed slash command",
            extra={"command": command, "parameters": parameters, "user_id": user_id, "team_id": team_id},
        )

        return PluginMessage(
            channel_id=team_id,
            user_id=user_id,
            content=text,
            command=command,
            parameters=parameters,
            metadata={"slack_channel_id": channel_id, "response_url": response_url, "command_type": "slash_command"},
        )

    @staticmethod
    def parse_interactive_component(payload: Dict[str, Any]) -> PluginMessage:
        """
        Parse Slack interactive component payload.

        Handles button clicks, modal submissions, and other interactive elements.

        Args:
            payload: Slack interactive component payload (JSON)

        Returns:
            PluginMessage with action information

        Validates: Requirements 8.4, 8.5
        """
        team_id = payload.get("team", {}).get("id", "")
        user_id = payload.get("user", {}).get("id", "")

        # Get action details
        actions = payload.get("actions", [])
        action = actions[0] if actions else {}
        action_id = action.get("action_id", "")
        action_value = action.get("value", "")

        # Extract command from action_id
        # Convention: action_id is the command (e.g., 'approve_plan', 'reject_plan')
        command = action_id.replace("_", " ").strip()
        if "_" in action_id:
            command = action_id.split("_")[0]  # e.g., 'approve' from 'approve_plan'

        # Get message metadata if available
        message = payload.get("message", {})
        message_ts = message.get("ts", "")

        # Get channel
        channel = payload.get("channel", {})
        channel_id = channel.get("id", "")

        # Get response URL
        response_url = payload.get("response_url", "")

        # Extract metadata from message blocks if available
        metadata = {
            "slack_channel_id": channel_id,
            "response_url": response_url,
            "message_ts": message_ts,
            "action_id": action_id,
            "action_value": action_value,
            "command_type": "interactive_component",
        }

        # Try to extract plan_date from message blocks
        blocks = message.get("blocks", [])
        for block in blocks:
            if block.get("type") == "context":
                elements = block.get("elements", [])
                for element in elements:
                    text = element.get("text", "")
                    if "plan_date:" in text:
                        # Extract date from text like "plan_date: 2026-02-18"
                        date_str = text.split("plan_date:")[1].strip()
                        metadata["plan_date"] = date_str

        logger.info(
            "Parsed interactive component",
            extra={"command": command, "action_id": action_id, "user_id": user_id, "team_id": team_id},
        )

        return PluginMessage(
            channel_id=team_id, user_id=user_id, content=action_value, command=command, parameters={}, metadata=metadata
        )

    @staticmethod
    def parse_app_mention(event: Dict[str, Any]) -> PluginMessage:
        """
        Parse Slack app mention event.

        Handles @mentions of the bot in channels.

        Args:
            event: Slack event payload

        Returns:
            PluginMessage with mention text

        Validates: Requirement 5.5
        """
        event_data = event.get("event", {})

        team_id = event.get("team_id", "")
        user_id = event_data.get("user", "")
        text = event_data.get("text", "")
        channel_id = event_data.get("channel", "")
        thread_ts = event_data.get("thread_ts")

        # Remove bot mention from text
        # Format: <@BOTID> command text
        clean_text = text
        if "<@" in text:
            # Remove the mention
            parts = text.split(">", 1)
            if len(parts) > 1:
                clean_text = parts[1].strip()

        # Parse as command
        parts = clean_text.split() if clean_text else []
        command = parts[0] if parts else "help"

        # Parse parameters
        parameters = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                parameters[key.strip()] = value.strip()

        logger.info(
            "Parsed app mention",
            extra={"command": command, "user_id": user_id, "team_id": team_id, "channel_id": channel_id},
        )

        return PluginMessage(
            channel_id=team_id,
            user_id=user_id,
            content=clean_text,
            command=command,
            parameters=parameters,
            thread_id=thread_ts,
            metadata={"slack_channel_id": channel_id, "command_type": "app_mention"},
        )

    @staticmethod
    def parse_direct_message(event: Dict[str, Any]) -> PluginMessage:
        """
        Parse Slack direct message event.

        Handles DMs sent to the bot.

        Args:
            event: Slack event payload

        Returns:
            PluginMessage with message text

        Validates: Requirement 5.5
        """
        event_data = event.get("event", {})

        team_id = event.get("team_id", "")
        user_id = event_data.get("user", "")
        text = event_data.get("text", "")
        channel_id = event_data.get("channel", "")
        thread_ts = event_data.get("thread_ts")

        # Parse as command
        parts = text.split() if text else []
        command = parts[0] if parts else "help"

        # Parse parameters
        parameters = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                parameters[key.strip()] = value.strip()

        logger.info("Parsed direct message", extra={"command": command, "user_id": user_id, "team_id": team_id})

        return PluginMessage(
            channel_id=team_id,
            user_id=user_id,
            content=text,
            command=command,
            parameters=parameters,
            thread_id=thread_ts,
            metadata={"slack_channel_id": channel_id, "command_type": "direct_message"},
        )
