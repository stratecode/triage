# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Minimal plugin template for TrIAge.

Copy this template to create a new plugin:
1. Copy triage/plugins/template to triage/plugins/yourplugin
2. Rename TemplatePlugin to YourPlugin
3. Update get_name() to return your plugin name
4. Implement the required methods
5. Add your plugin to triage/plugins/__init__.py
"""

import logging
from typing import Any, Dict, Optional

from triage.core.actions_api import CoreActionsAPI
from triage.plugins.interface import PluginConfig, PluginInterface, PluginMessage, PluginResponse, PluginStatus

logger = logging.getLogger(__name__)


class TemplatePlugin(PluginInterface):
    """Minimal plugin template."""

    def __init__(self):
        self.name = "template"  # TODO: Change to your plugin name
        self.version = "1.0.0"
        self.core_api: Optional[CoreActionsAPI] = None
        self.config: Optional[PluginConfig] = None

    # ========== Metadata Methods ==========

    def get_name(self) -> str:
        """Return unique plugin identifier."""
        return self.name

    def get_version(self) -> str:
        """Return plugin version."""
        return self.version

    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON schema for configuration validation."""
        return {
            "type": "object",
            "required": [],  # TODO: Add required config fields
            "properties": {
                # TODO: Define your configuration schema
                # Example:
                # "api_key": {
                #     "type": "string",
                #     "description": "API key for authentication"
                # }
            },
        }

    # ========== Lifecycle Methods ==========

    async def initialize(self, config: PluginConfig, core_api: CoreActionsAPI) -> None:
        """Initialize plugin with configuration and core API access."""
        self.config = config
        self.core_api = core_api

        # TODO: Initialize your API clients, connections, etc.

        logger.info(f"Initialized {self.name} plugin v{self.version}")

    async def start(self) -> None:
        """Start the plugin."""
        # TODO: Register webhooks, open connections, etc.
        logger.info(f"Started {self.name} plugin")

    async def stop(self) -> None:
        """Stop the plugin gracefully."""
        # TODO: Close connections, cleanup resources
        logger.info(f"Stopped {self.name} plugin")

    async def health_check(self) -> PluginStatus:
        """Check plugin health status."""
        # TODO: Implement health check (ping API, check connection, etc.)
        return PluginStatus.HEALTHY

    # ========== Message Handling Methods ==========

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        """Handle incoming message from the channel."""
        try:
            # TODO: Parse command and parameters
            command = message.command

            # TODO: Route to appropriate handler
            if command == "plan":
                return await self._handle_plan_command(message)
            elif command == "status":
                return await self._handle_status_command(message)
            else:
                return PluginResponse(
                    content="Unknown command. Available commands: plan, status", response_type="ephemeral"
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return PluginResponse(content="An error occurred. Please try again.", response_type="ephemeral")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        """Send a message to the channel."""
        try:
            # TODO: Convert PluginResponse to your platform's format
            # TODO: Send using your platform's API

            logger.info(f"Sent message to {channel_id}/{user_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return False

    # ========== Event Handling Method ==========

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle events from TrIAge Core."""
        try:
            if event_type == "plan_generated":
                await self._handle_plan_generated(event_data)
            elif event_type == "task_blocked":
                await self._handle_task_blocked(event_data)
            elif event_type == "approval_timeout":
                await self._handle_approval_timeout(event_data)

        except Exception as e:
            logger.error(f"Error handling event {event_type}: {e}", exc_info=True)

    # ========== Private Helper Methods ==========

    async def _handle_plan_command(self, message: PluginMessage) -> PluginResponse:
        """Handle plan generation command."""
        # Invoke core action
        result = await self.core_api.generate_plan(
            user_id=message.user_id, closure_rate=message.parameters.get("closure_rate")
        )

        if result.success:
            return PluginResponse(content=result.data["markdown"], response_type="message")
        else:
            return PluginResponse(content=f"Error: {result.error}", response_type="ephemeral")

    async def _handle_status_command(self, message: PluginMessage) -> PluginResponse:
        """Handle status check command."""
        result = await self.core_api.get_status(user_id=message.user_id)

        if result.success:
            status = result.data
            return PluginResponse(
                content=f"Status: {status['status']}\nCompletion: {status['completion_rate']:.0%}",
                response_type="message",
            )
        else:
            return PluginResponse(content=f"Error: {result.error}", response_type="ephemeral")

    async def _handle_plan_generated(self, event_data: Dict[str, Any]) -> None:
        """Handle plan_generated event."""
        response = PluginResponse(
            content=f"📋 Your daily plan is ready!\n\n{event_data['plan_markdown']}", response_type="message"
        )

        await self.send_message(event_data["channel_id"], event_data["user_id"], response)

    async def _handle_task_blocked(self, event_data: Dict[str, Any]) -> None:
        """Handle task_blocked event."""
        response = PluginResponse(
            content=f"⚠️ Task {event_data['task_key']} is blocked: {event_data['blocker_reason']}",
            response_type="message",
        )

        await self.send_message(event_data["channel_id"], event_data["user_id"], response)

    async def _handle_approval_timeout(self, event_data: Dict[str, Any]) -> None:
        """Handle approval_timeout event."""
        response = PluginResponse(
            content=f"⏰ Plan approval timed out for {event_data['plan_date']}", response_type="message"
        )

        await self.send_message(event_data["channel_id"], event_data["user_id"], response)
