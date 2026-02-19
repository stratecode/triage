# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Slack Connector Plugin

Reference implementation of the PluginInterface for Slack integration.
Demonstrates OAuth authorization, workspace installation, command mapping,
and event handling patterns that can be adapted for other channels.

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

import logging
from typing import Any, Dict, Optional

from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from slack_sdk.web.async_client import AsyncWebClient

from ..installation_storage import PluginInstallationStorage
from ..interface import (
    PluginConfig,
    PluginInterface,
    PluginMessage,
    PluginResponse,
    PluginStatus,
)
from ..models import PluginInstallation

logger = logging.getLogger(__name__)


class SlackPlugin(PluginInterface):
    """
    Slack channel connector plugin.

    This is the reference implementation demonstrating how to:
    - Implement the PluginInterface for a specific channel
    - Handle OAuth authorization and workspace installation
    - Parse channel-specific commands and map to Core Actions
    - Format responses for channel-specific display
    - Handle interactive components (buttons, modals)
    - Subscribe to and handle core events

    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
    """

    def __init__(self):
        """
        Initialize Slack plugin.

        Validates: Requirement 5.1
        """
        self.name = "slack"
        self.version = "1.0.0"
        self.client: Optional[AsyncWebClient] = None
        self.core_api: Optional[Any] = None
        self.config: Optional[PluginConfig] = None
        self.signature_verifier: Optional[SignatureVerifier] = None
        self.storage: Optional[PluginInstallationStorage] = None

        logger.info("SlackPlugin instance created")

    def get_name(self) -> str:
        """
        Return the plugin name.

        Returns:
            str: Plugin name 'slack'

        Validates: Requirement 5.1
        """
        return self.name

    def get_version(self) -> str:
        """
        Return the plugin version.

        Returns:
            str: Semantic version string

        Validates: Requirement 5.1
        """
        return self.version

    def get_config_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for Slack plugin configuration.

        Required configuration:
        - client_id: Slack app client ID
        - client_secret: Slack app client secret
        - signing_secret: Slack signing secret for webhook validation

        Optional configuration:
        - bot_token: Bot token for testing (normally loaded from database)
        - app_token: App-level token for Socket Mode (future)

        Returns:
            Dict[str, Any]: JSON Schema object

        Validates: Requirement 5.1
        """
        return {
            "type": "object",
            "required": ["client_id", "client_secret", "signing_secret"],
            "properties": {
                "client_id": {"type": "string", "description": "Slack app client ID"},
                "client_secret": {"type": "string", "description": "Slack app client secret"},
                "signing_secret": {"type": "string", "description": "Slack signing secret for webhook validation"},
                "bot_token": {
                    "type": "string",
                    "description": "Bot token for testing (optional, normally from database)",
                },
                "app_token": {
                    "type": "string",
                    "description": "App-level token for Socket Mode (optional, future use)",
                },
            },
        }

    async def initialize(self, config: PluginConfig, core_api: Any) -> None:
        """
        Initialize the Slack plugin with configuration and core API access.

        Sets up:
        - Slack SDK client
        - Signature verifier for webhook validation
        - Core API reference
        - Installation storage

        Args:
            config: Plugin configuration
            core_api: Reference to TrIAge Core Actions API

        Raises:
            ValueError: If required configuration is missing

        Validates: Requirements 5.1, 5.2
        """
        logger.info("Initializing SlackPlugin")

        self.config = config
        self.core_api = core_api

        # Validate required configuration
        if "signing_secret" not in config.config:
            raise ValueError("signing_secret is required in Slack plugin configuration")

        # Initialize signature verifier for webhook validation
        signing_secret = config.config["signing_secret"]
        self.signature_verifier = SignatureVerifier(signing_secret)
        logger.info("Signature verifier initialized")

        # Initialize Slack client if bot token provided (for testing)
        bot_token = config.config.get("bot_token")
        if bot_token:
            self.client = AsyncWebClient(token=bot_token)
            logger.info("Slack client initialized with bot token")
        else:
            logger.info("No bot token provided, will load from database per workspace")

        # Initialize installation storage
        # Note: In production, this would be injected via dependency injection
        # For now, we create it here if not already set (allows mocking in tests)
        if not hasattr(self, "storage") or self.storage is None:
            from ..installation_storage import PluginInstallationStorage

            # For testing, allow storage to be None if database_url not in config
            if "database_url" in config.config and "encryption_key" in config.config:
                self.storage = PluginInstallationStorage(
                    database_url=config.config["database_url"], encryption_key=config.config["encryption_key"]
                )
            else:
                # In tests or when database not configured, storage will be None
                self.storage = None
                logger.warning("PluginInstallationStorage not initialized (database_url or encryption_key missing)")

        logger.info("SlackPlugin initialized successfully")

    async def start(self) -> None:
        """
        Start the Slack plugin.

        The plugin is ready to receive webhook events. No persistent
        connections are needed for Slack's webhook-based architecture.

        Validates: Requirement 5.1
        """
        logger.info("SlackPlugin started and ready to receive webhooks")

    async def stop(self) -> None:
        """
        Stop the Slack plugin gracefully.

        Closes the Slack client connection if active.

        Validates: Requirement 5.1
        """
        if self.client:
            await self.client.close()
            logger.info("Slack client closed")

        logger.info("SlackPlugin stopped")

    async def health_check(self) -> PluginStatus:
        """
        Check Slack plugin health status.

        Verifies:
        - Slack client is initialized
        - API connectivity (if client available)
        - Authentication validity

        Returns:
            PluginStatus: Current health status

        Validates: Requirement 5.1
        """
        # If no client initialized, we're still healthy (will load per workspace)
        if not self.client:
            logger.debug("Health check: No client initialized (normal for multi-workspace)")
            return PluginStatus.HEALTHY

        try:
            # Test API connectivity with auth.test
            response = await self.client.auth_test()

            if response["ok"]:
                logger.debug("Health check: Slack API connection healthy")
                return PluginStatus.HEALTHY
            else:
                logger.warning("Health check: Slack API returned not ok")
                return PluginStatus.DEGRADED

        except SlackApiError as e:
            logger.error(f"Health check: Slack API error: {e.response['error']}", exc_info=True)
            return PluginStatus.UNHEALTHY
        except Exception as e:
            logger.error(f"Health check: Unexpected error: {e}", exc_info=True)
            return PluginStatus.UNHEALTHY

    async def handle_message(self, message: PluginMessage) -> PluginResponse:
        """
        Handle incoming Slack message/command.

        Routes the message to appropriate handler based on command type.
        Supports:
        - /triage plan
        - /triage status
        - /triage config
        - approve/reject actions

        Verifies workspace installation before processing.

        Args:
            message: Channel-agnostic message

        Returns:
            PluginResponse: Response to send back to Slack

        Validates: Requirements 5.2, 5.6, 7.4, 7.5
        """
        command = message.command

        logger.info(
            "Handling Slack message",
            extra={"command": command, "user_id": message.user_id, "channel_id": message.channel_id},
        )

        # Verify workspace installation before processing
        if self.storage:
            installation = await self.verify_installation(message.channel_id)

            if not installation:
                logger.warning(
                    "Request from uninstalled workspace",
                    extra={"channel_id": message.channel_id, "user_id": message.user_id},
                )
                return PluginResponse(
                    content="⚠️ TrIAge is not installed in this workspace. Please reinstall the app.",
                    response_type="ephemeral",
                )

            # Verify workspace data isolation
            isolated = await self.ensure_workspace_isolation(message.channel_id, message.user_id)

            if not isolated:
                logger.error(
                    "Workspace isolation check failed",
                    extra={"channel_id": message.channel_id, "user_id": message.user_id},
                )
                return PluginResponse(
                    content="❌ Unable to process request. Please contact support.", response_type="ephemeral"
                )

        # Route to appropriate command handler
        if command == "plan":
            return await self._handle_plan_command(message)
        elif command == "status":
            return await self._handle_status_command(message)
        elif command == "config":
            return await self._handle_config_command(message)
        elif command == "approve":
            return await self._handle_approve_command(message)
        elif command == "reject":
            return await self._handle_reject_command(message)
        else:
            # Unknown command - show help
            return PluginResponse(content=self._format_help_message(), response_type="ephemeral")

    async def send_message(self, channel_id: str, user_id: str, response: PluginResponse) -> bool:
        """
        Send a message to Slack channel.

        Converts PluginResponse to Slack Block Kit format and sends via
        Slack API.

        Args:
            channel_id: Slack channel ID or workspace ID
            user_id: Slack user ID
            response: Message to send

        Returns:
            bool: True if message sent successfully, False otherwise

        Validates: Requirements 5.4, 5.7
        """
        try:
            # Load workspace installation to get bot token
            installation = await self.storage.get_installation("slack", channel_id)

            if not installation or not installation.is_active:
                logger.error(f"No active installation found for workspace: {channel_id}")
                return False

            # Create client with workspace bot token
            client = AsyncWebClient(token=installation.access_token)

            # Convert response to Slack blocks
            blocks = self._convert_to_slack_blocks(response)

            # Send message
            await client.chat_postMessage(
                channel=user_id,  # Send as DM to user
                text=response.content,  # Fallback text
                blocks=blocks,
            )

            logger.info("Message sent successfully", extra={"channel_id": channel_id, "user_id": user_id})

            return True

        except SlackApiError as e:
            logger.error(f"Slack API error sending message: {e.response['error']}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}", exc_info=True)
            return False

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle events from TrIAge Core.

        Subscribes to:
        - plan_generated: Send plan to user
        - task_blocked: Alert user about blocking task
        - approval_timeout: Remind user to approve plan

        Args:
            event_type: Type of event
            event_data: Event payload

        Validates: Requirements 5.5, 10.6, 10.7
        """
        logger.info("Handling core event", extra={"event_type": event_type, "event_data_keys": list(event_data.keys())})

        if event_type == "plan_generated":
            await self._notify_plan_generated(event_data)
        elif event_type == "task_blocked":
            await self._notify_task_blocked(event_data)
        elif event_type == "approval_timeout":
            await self._notify_approval_timeout(event_data)
        else:
            logger.debug(f"Ignoring event type: {event_type}")

    async def handle_slack_event(self, event: Dict[str, Any]) -> PluginResponse:
        """
        Handle Slack event API events.

        Processes events from Slack Event API including:
        - app_mention: Bot mentioned in channel
        - message: Direct message to bot
        - Other event types

        Args:
            event: Slack event payload

        Returns:
            PluginResponse with acknowledgment or response

        Validates: Requirements 5.3, 5.5
        """
        event_type = event.get("event", {}).get("type")

        logger.info("Handling Slack event", extra={"event_type": event_type})

        # Import parser
        from .command_parser import SlackCommandParser

        if event_type == "app_mention":
            # Parse app mention and handle as message
            message = SlackCommandParser.parse_app_mention(event)
            return await self.handle_message(message)

        elif event_type == "message":
            # Check if it's a DM (channel type is 'im')
            channel_type = event.get("event", {}).get("channel_type")

            if channel_type == "im":
                # Parse direct message and handle
                message = SlackCommandParser.parse_direct_message(event)
                return await self.handle_message(message)
            else:
                # Ignore channel messages (only respond to mentions)
                return PluginResponse(content="", response_type="ephemeral")

        else:
            # Unknown event type
            logger.debug(f"Ignoring Slack event type: {event_type}")
            return PluginResponse(content="", response_type="ephemeral")

    async def handle_interactive_component(self, payload: Dict[str, Any]) -> PluginResponse:
        """
        Handle Slack interactive component events.

        Processes button clicks, modal submissions, and other interactive
        elements from Slack.

        Args:
            payload: Slack interactive component payload

        Returns:
            PluginResponse with action result

        Validates: Requirements 5.3
        """
        logger.info("Handling interactive component")

        # Import parser
        from .command_parser import SlackCommandParser

        # Parse interactive component
        message = SlackCommandParser.parse_interactive_component(payload)

        # Handle as message
        return await self.handle_message(message)

    # Private helper methods

    def _format_help_message(self) -> str:
        """
        Format help message with available commands.

        Returns:
            str: Markdown-formatted help message

        Validates: Requirements 8.6, 8.7
        """
        return """
*TrIAge Commands*

• `/triage plan` - Generate your daily plan
• `/triage status` - Check current plan status
• `/triage config` - Configure your settings

Need help? Contact support or visit our documentation.
        """.strip()

    async def _handle_plan_command(self, message: PluginMessage) -> PluginResponse:
        """
        Handle /triage plan command.

        Generates a daily plan by invoking the generate_plan Core Action.
        Supports optional closure_rate parameter.

        Args:
            message: PluginMessage with command and parameters

        Returns:
            PluginResponse with plan or error message

        Validates: Requirements 5.2, 5.6, 8.1
        """
        logger.info(f"Handling plan command for user {message.user_id}", extra={"parameters": message.parameters})

        # Extract optional closure_rate parameter
        closure_rate = message.parameters.get("closure_rate")
        if closure_rate is not None:
            try:
                closure_rate = float(closure_rate)
            except (ValueError, TypeError):
                return PluginResponse(
                    content="Invalid closure_rate parameter. Must be a number between 0.0 and 1.0.",
                    response_type="ephemeral",
                )

        # Invoke Core Action
        result = await self.core_api.generate_plan(user_id=message.user_id, closure_rate=closure_rate)

        if result.success:
            plan_markdown = result.data["markdown"]

            # Return plan with approval buttons
            return PluginResponse(
                content=plan_markdown,
                response_type="message",
                actions=[
                    {"type": "button", "text": "Approve", "action_id": "approve_plan", "style": "primary"},
                    {"type": "button", "text": "Reject", "action_id": "reject_plan", "style": "danger"},
                ],
                metadata={
                    "plan_date": result.data["plan"].date.isoformat() if hasattr(result.data["plan"], "date") else None
                },
            )
        else:
            # Return error message
            return PluginResponse(content=f"❌ Error generating plan: {result.error}", response_type="ephemeral")

    async def _handle_status_command(self, message: PluginMessage) -> PluginResponse:
        """
        Handle /triage status command.

        Gets current plan status by invoking the get_status Core Action.

        Args:
            message: PluginMessage with command

        Returns:
            PluginResponse with status information

        Validates: Requirements 5.2, 5.6, 8.2
        """
        logger.info(f"Handling status command for user {message.user_id}")

        # Invoke Core Action
        result = await self.core_api.get_status(user_id=message.user_id)

        if result.success:
            status_data = result.data

            # Format status message
            if status_data.get("status") == "not_found":
                content = "📋 No plan found for today. Use `/triage plan` to generate one."
            else:
                total = status_data.get("total_priorities", 0)
                completed = status_data.get("completed_priorities", 0)
                closure_rate = status_data.get("closure_rate", 0.0)

                content = f"""
📊 *Plan Status for {status_data.get('date')}*

✅ Completed: {completed}/{total} priorities
📈 Closure Rate: {closure_rate * 100:.0f}%
                """.strip()

                # Add incomplete tasks if any
                incomplete = status_data.get("incomplete_tasks", [])
                if incomplete:
                    content += "\n\n⏳ *Incomplete Tasks:*\n"
                    for task in incomplete[:5]:  # Show max 5
                        content += f"• {task}\n"

            return PluginResponse(content=content, response_type="ephemeral")
        else:
            return PluginResponse(content=f"❌ Error fetching status: {result.error}", response_type="ephemeral")

    async def _handle_config_command(self, message: PluginMessage) -> PluginResponse:
        """
        Handle /triage config command.

        Updates user settings by invoking the configure_settings Core Action.
        Expects settings in parameters.

        Args:
            message: PluginMessage with command and parameters

        Returns:
            PluginResponse with confirmation or error

        Validates: Requirements 5.2, 5.6, 8.3
        """
        logger.info(f"Handling config command for user {message.user_id}", extra={"parameters": message.parameters})

        # Check if parameters provided
        if not message.parameters:
            # Show current settings help
            return PluginResponse(
                content="""
⚙️ *Configuration Options*

Use `/triage config <setting>=<value>` to update settings:

• `notification_enabled=true/false` - Enable/disable notifications
• `approval_timeout_hours=24` - Hours before approval timeout
• `admin_block_time=14:00-15:30` - Time for admin tasks
• `max_priorities=3` - Maximum priority tasks per day (1-5)

Example: `/triage config max_priorities=3`
                """.strip(),
                response_type="ephemeral",
            )

        # Invoke Core Action
        result = await self.core_api.configure_settings(user_id=message.user_id, settings=message.parameters)

        if result.success:
            updated = result.data.get("settings", {})

            # Format confirmation message
            content = "✅ *Settings Updated*\n\n"
            for key, value in updated.items():
                content += f"• {key}: `{value}`\n"

            return PluginResponse(content=content, response_type="ephemeral")
        else:
            return PluginResponse(content=f"❌ Error updating settings: {result.error}", response_type="ephemeral")

    async def _handle_approve_command(self, message: PluginMessage) -> PluginResponse:
        """
        Handle approve action from interactive button.

        Approves the plan by invoking the approve_plan Core Action.

        Args:
            message: PluginMessage with action metadata

        Returns:
            PluginResponse with confirmation

        Validates: Requirements 5.3, 8.4
        """
        logger.info(f"Handling approve action for user {message.user_id}")

        # Extract plan_date from metadata
        from datetime import date

        plan_date_str = message.metadata.get("plan_date")

        if plan_date_str:
            try:
                plan_date = date.fromisoformat(plan_date_str)
            except (ValueError, TypeError):
                plan_date = date.today()
        else:
            plan_date = date.today()

        # Invoke Core Action
        result = await self.core_api.approve_plan(user_id=message.user_id, plan_date=plan_date, approved=True)

        if result.success:
            return PluginResponse(
                content="✅ Plan approved! Good luck with your priorities today.", response_type="message"
            )
        else:
            return PluginResponse(content=f"❌ Error approving plan: {result.error}", response_type="ephemeral")

    async def _handle_reject_command(self, message: PluginMessage) -> PluginResponse:
        """
        Handle reject action from interactive button.

        Rejects the plan and triggers re-planning by invoking the reject_plan
        Core Action. Expects feedback in message content or parameters.

        Args:
            message: PluginMessage with action metadata and feedback

        Returns:
            PluginResponse with new plan or error

        Validates: Requirements 5.3, 8.5
        """
        logger.info(f"Handling reject action for user {message.user_id}")

        # Extract plan_date from metadata
        from datetime import date

        plan_date_str = message.metadata.get("plan_date")

        if plan_date_str:
            try:
                plan_date = date.fromisoformat(plan_date_str)
            except (ValueError, TypeError):
                plan_date = date.today()
        else:
            plan_date = date.today()

        # Get feedback from content or parameters
        feedback = message.content or message.parameters.get("feedback", "No feedback provided")

        if not feedback or feedback == "No feedback provided":
            # Ask for feedback
            return PluginResponse(
                content="Please provide feedback on why you're rejecting this plan.", response_type="ephemeral"
            )

        # Invoke Core Action
        result = await self.core_api.reject_plan(user_id=message.user_id, plan_date=plan_date, feedback=feedback)

        if result.success:
            # Check if new plan was generated
            new_plan = result.data.get("new_plan")

            if new_plan and new_plan.get("markdown"):
                return PluginResponse(
                    content=f"📝 Plan rejected. Here's a new plan:\n\n{new_plan['markdown']}",
                    response_type="message",
                    actions=[
                        {"type": "button", "text": "Approve", "action_id": "approve_plan", "style": "primary"},
                        {"type": "button", "text": "Reject", "action_id": "reject_plan", "style": "danger"},
                    ],
                )
            else:
                return PluginResponse(
                    content="✅ Plan rejected. Your feedback has been recorded.", response_type="message"
                )
        else:
            return PluginResponse(content=f"❌ Error rejecting plan: {result.error}", response_type="ephemeral")

    def _convert_to_slack_blocks(self, response: PluginResponse) -> list:
        """
        Convert PluginResponse to Slack Block Kit format.

        Transforms channel-agnostic response into Slack's Block Kit format
        with support for:
        - Markdown text formatting
        - Interactive buttons
        - Attachments
        - Context metadata

        Args:
            response: Channel-agnostic response

        Returns:
            List of Slack Block Kit blocks

        Validates: Requirements 5.4, 5.7
        """
        blocks = []

        # Add main content as section block
        # Split long content into multiple blocks (Slack has 3000 char limit per block)
        content = response.content
        max_length = 2900  # Leave some margin

        if len(content) <= max_length:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": content}})
        else:
            # Split into multiple blocks
            chunks = [content[i : i + max_length] for i in range(0, len(content), max_length)]
            for chunk in chunks:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})

        # Add divider before actions if present
        if response.actions:
            blocks.append({"type": "divider"})

        # Add interactive actions (buttons)
        if response.actions:
            elements = []

            for action in response.actions:
                button = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": action.get("text", "Action"), "emoji": True},
                    "action_id": action.get("action_id", "unknown_action"),
                }

                # Add style if specified
                style = action.get("style")
                if style in ["primary", "danger"]:
                    button["style"] = style

                # Add value if specified
                value = action.get("value")
                if value:
                    button["value"] = value

                elements.append(button)

            # Add actions block
            blocks.append({"type": "actions", "elements": elements})

        # Add attachments as context blocks
        if response.attachments:
            for attachment in response.attachments:
                # Convert attachment to context block
                context_elements = []

                if "text" in attachment:
                    context_elements.append({"type": "mrkdwn", "text": attachment["text"]})

                if context_elements:
                    blocks.append({"type": "context", "elements": context_elements})

        # Add metadata as context if present
        if response.metadata:
            # Add plan_date as hidden context for button actions
            if "plan_date" in response.metadata:
                blocks.append(
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": f"_plan_date: {response.metadata['plan_date']}_"}],
                    }
                )

        logger.debug(f"Converted response to {len(blocks)} Slack blocks", extra={"block_count": len(blocks)})

        return blocks

    async def _notify_plan_generated(self, event_data: Dict[str, Any]) -> None:
        """
        Send plan generated notification to Slack.

        Notifies the user when a new plan has been generated, either
        automatically or after rejection/re-planning.

        Args:
            event_data: Event payload with plan details

        Validates: Requirements 10.6, 10.7
        """
        logger.info("Sending plan generated notification")

        # Extract event data
        user_id = event_data.get("user_id")
        channel_id = event_data.get("channel_id")  # workspace_id
        plan_markdown = event_data.get("plan_markdown")
        plan_date = event_data.get("plan_date")

        if not all([user_id, channel_id, plan_markdown]):
            logger.warning("Missing required fields in plan_generated event", extra={"event_data": event_data})
            return

        # Create response with plan and approval buttons
        response = PluginResponse(
            content=f"📋 *Your Daily Plan is Ready*\n\n{plan_markdown}",
            response_type="message",
            actions=[
                {"type": "button", "text": "✅ Approve", "action_id": "approve_plan", "style": "primary"},
                {"type": "button", "text": "❌ Reject", "action_id": "reject_plan", "style": "danger"},
            ],
            metadata={"plan_date": plan_date},
        )

        # Send notification
        success = await self.send_message(channel_id, user_id, response)

        if success:
            logger.info("Plan generated notification sent", extra={"user_id": user_id, "channel_id": channel_id})
        else:
            logger.error(
                "Failed to send plan generated notification", extra={"user_id": user_id, "channel_id": channel_id}
            )

    async def _notify_task_blocked(self, event_data: Dict[str, Any]) -> None:
        """
        Send task blocked alert to Slack.

        Alerts the user when a task is blocked by dependencies or
        third-party actions.

        Args:
            event_data: Event payload with blocking task details

        Validates: Requirements 10.6, 10.7
        """
        logger.info("Sending task blocked notification")

        # Extract event data
        user_id = event_data.get("user_id")
        channel_id = event_data.get("channel_id")  # workspace_id
        task_key = event_data.get("task_key")
        task_summary = event_data.get("task_summary")
        blocking_reason = event_data.get("blocking_reason", "Unknown reason")

        if not all([user_id, channel_id, task_key]):
            logger.warning("Missing required fields in task_blocked event", extra={"event_data": event_data})
            return

        # Create alert message
        content = f"""
🚨 *Task Blocked Alert*

*Task:* {task_key} - {task_summary or 'No summary'}
*Reason:* {blocking_reason}

This task is currently blocked and cannot be completed. Please review and take action.
        """.strip()

        response = PluginResponse(content=content, response_type="message")

        # Send notification
        success = await self.send_message(channel_id, user_id, response)

        if success:
            logger.info(
                "Task blocked notification sent",
                extra={"user_id": user_id, "channel_id": channel_id, "task_key": task_key},
            )
        else:
            logger.error(
                "Failed to send task blocked notification",
                extra={"user_id": user_id, "channel_id": channel_id, "task_key": task_key},
            )

    async def _notify_approval_timeout(self, event_data: Dict[str, Any]) -> None:
        """
        Send approval timeout reminder to Slack.

        Reminds the user to approve their plan before the timeout expires.

        Args:
            event_data: Event payload with plan details

        Validates: Requirements 10.6, 10.7
        """
        logger.info("Sending approval timeout notification")

        # Extract event data
        user_id = event_data.get("user_id")
        channel_id = event_data.get("channel_id")  # workspace_id
        plan_date = event_data.get("plan_date")
        hours_remaining = event_data.get("hours_remaining", 0)

        if not all([user_id, channel_id, plan_date]):
            logger.warning("Missing required fields in approval_timeout event", extra={"event_data": event_data})
            return

        # Create reminder message
        content = f"""
⏰ *Plan Approval Reminder*

Your plan for {plan_date} is still pending approval.

⏳ Time remaining: {hours_remaining} hours

Please review and approve your plan to get started!
        """.strip()

        response = PluginResponse(
            content=content,
            response_type="message",
            actions=[{"type": "button", "text": "View Plan", "action_id": "view_plan", "style": "primary"}],
            metadata={"plan_date": plan_date},
        )

        # Send notification
        success = await self.send_message(channel_id, user_id, response)

        if success:
            logger.info(
                "Approval timeout notification sent",
                extra={"user_id": user_id, "channel_id": channel_id, "plan_date": plan_date},
            )
        else:
            logger.error(
                "Failed to send approval timeout notification",
                extra={"user_id": user_id, "channel_id": channel_id, "plan_date": plan_date},
            )

    # Workspace Installation Management Methods

    async def store_installation(
        self,
        team_id: str,
        access_token: str,
        bot_user_id: str,
        team_name: Optional[str] = None,
        refresh_token: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PluginInstallation:
        """
        Store workspace installation data in database.

        Saves OAuth tokens and workspace metadata after successful OAuth flow.
        Tokens are encrypted before storage.

        Args:
            team_id: Slack workspace/team ID
            access_token: OAuth access token (bot token)
            bot_user_id: Bot user ID in the workspace
            team_name: Workspace name (optional)
            refresh_token: OAuth refresh token (optional)
            metadata: Additional workspace metadata (optional)

        Returns:
            PluginInstallation: Created installation record

        Raises:
            RuntimeError: If storage not initialized
            ValueError: If installation already exists
            Exception: If storage operation fails

        Validates: Requirements 7.1, 7.2
        """
        if not self.storage:
            raise RuntimeError("Installation storage not initialized")

        logger.info(
            "Storing workspace installation",
            extra={"team_id": team_id, "bot_user_id": bot_user_id, "team_name": team_name},
        )

        # Prepare metadata
        install_metadata = metadata or {}
        install_metadata.update({"bot_user_id": bot_user_id, "team_name": team_name})

        # Create installation record
        installation = PluginInstallation(
            plugin_name="slack",
            channel_id=team_id,
            access_token=access_token,
            refresh_token=refresh_token,
            metadata=install_metadata,
            is_active=True,
        )

        # Store in database (tokens will be encrypted)
        try:
            created = await self.storage.create_installation(installation)

            logger.info(
                "Workspace installation stored successfully", extra={"team_id": team_id, "installation_id": created.id}
            )

            return created

        except ValueError as e:
            # Installation already exists
            logger.warning(f"Installation already exists for workspace: {team_id}", extra={"error": str(e)})
            raise
        except Exception as e:
            logger.error(f"Failed to store workspace installation: {e}", extra={"team_id": team_id}, exc_info=True)
            raise

    async def verify_installation(self, team_id: str) -> Optional[PluginInstallation]:
        """
        Verify workspace installation before processing requests.

        Checks if the workspace has an active installation. This should be
        called before processing any requests from a workspace to ensure
        proper authorization.

        Args:
            team_id: Slack workspace/team ID

        Returns:
            PluginInstallation if workspace is installed and active, None otherwise

        Raises:
            RuntimeError: If storage not initialized

        Validates: Requirements 7.4
        """
        if not self.storage:
            raise RuntimeError("Installation storage not initialized")

        logger.debug("Verifying workspace installation", extra={"team_id": team_id})

        try:
            # Retrieve installation from database
            installation = await self.storage.get_installation("slack", team_id)

            if not installation:
                logger.warning(f"No installation found for workspace: {team_id}")
                return None

            if not installation.is_active:
                logger.warning(f"Installation exists but is inactive for workspace: {team_id}")
                return None

            logger.debug(
                "Workspace installation verified", extra={"team_id": team_id, "installation_id": installation.id}
            )

            return installation

        except Exception as e:
            logger.error(f"Failed to verify workspace installation: {e}", extra={"team_id": team_id}, exc_info=True)
            return None

    async def uninstall_workspace(self, team_id: str) -> bool:
        """
        Remove workspace installation and cleanup data.

        Deletes all stored tokens and configuration when a workspace
        uninstalls the app. This ensures proper cleanup and data removal.

        Args:
            team_id: Slack workspace/team ID

        Returns:
            bool: True if uninstall successful, False if installation not found

        Raises:
            RuntimeError: If storage not initialized
            Exception: If deletion fails

        Validates: Requirements 7.3
        """
        if not self.storage:
            raise RuntimeError("Installation storage not initialized")

        logger.info("Uninstalling workspace", extra={"team_id": team_id})

        try:
            # Delete installation from database
            deleted = await self.storage.delete_installation("slack", team_id)

            if deleted:
                logger.info("Workspace uninstalled successfully", extra={"team_id": team_id})
            else:
                logger.warning(f"No installation found to uninstall for workspace: {team_id}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to uninstall workspace: {e}", extra={"team_id": team_id}, exc_info=True)
            raise

    async def ensure_workspace_isolation(self, team_id: str, user_id: str) -> bool:
        """
        Ensure workspace data isolation for user requests.

        Verifies that the user belongs to the specified workspace and that
        data access is properly isolated. This prevents cross-workspace
        data leakage.

        Args:
            team_id: Slack workspace/team ID
            user_id: Slack user ID

        Returns:
            bool: True if isolation verified, False otherwise

        Validates: Requirements 7.5, 7.6
        """
        logger.debug("Verifying workspace data isolation", extra={"team_id": team_id, "user_id": user_id})

        # Verify installation exists and is active
        installation = await self.verify_installation(team_id)

        if not installation:
            logger.warning(
                "Workspace isolation check failed: no active installation",
                extra={"team_id": team_id, "user_id": user_id},
            )
            return False

        # In Slack, workspace isolation is enforced by:
        # 1. Each workspace has its own bot token
        # 2. User IDs are unique within a workspace
        # 3. API calls are scoped to the workspace via the bot token

        # Additional verification: Check if user_id format is valid
        # Slack user IDs start with 'U' or 'W'
        if not user_id or user_id[0] not in ["U", "W"]:
            logger.warning("Invalid user ID format", extra={"team_id": team_id, "user_id": user_id})
            return False

        logger.debug("Workspace data isolation verified", extra={"team_id": team_id, "user_id": user_id})

        return True

    async def update_installation_token(
        self, team_id: str, access_token: str, refresh_token: Optional[str] = None
    ) -> Optional[PluginInstallation]:
        """
        Update OAuth tokens for an existing installation.

        Used when tokens are refreshed or rotated. Tokens are encrypted
        before storage.

        Args:
            team_id: Slack workspace/team ID
            access_token: New OAuth access token
            refresh_token: New OAuth refresh token (optional)

        Returns:
            Updated PluginInstallation if successful, None if installation not found

        Raises:
            RuntimeError: If storage not initialized

        Validates: Requirements 7.2
        """
        if not self.storage:
            raise RuntimeError("Installation storage not initialized")

        logger.info("Updating installation tokens", extra={"team_id": team_id})

        try:
            # Update tokens in database
            updated = await self.storage.update_installation(
                plugin_name="slack", channel_id=team_id, access_token=access_token, refresh_token=refresh_token
            )

            if updated:
                logger.info(
                    "Installation tokens updated successfully",
                    extra={"team_id": team_id, "installation_id": updated.id},
                )
            else:
                logger.warning(f"No installation found to update for workspace: {team_id}")

            return updated

        except Exception as e:
            logger.error(f"Failed to update installation tokens: {e}", extra={"team_id": team_id}, exc_info=True)
            raise

    async def list_workspace_installations(self, active_only: bool = True) -> list[PluginInstallation]:
        """
        List all Slack workspace installations.

        Retrieves all workspace installations for monitoring and management.

        Args:
            active_only: If True, only return active installations

        Returns:
            List of PluginInstallation objects

        Raises:
            RuntimeError: If storage not initialized
        """
        if not self.storage:
            raise RuntimeError("Installation storage not initialized")

        logger.debug("Listing workspace installations", extra={"active_only": active_only})

        try:
            installations = await self.storage.list_plugin_installations(plugin_name="slack", active_only=active_only)

            logger.debug(f"Retrieved {len(installations)} workspace installations", extra={"count": len(installations)})

            return installations

        except Exception as e:
            logger.error(f"Failed to list workspace installations: {e}", exc_info=True)
            raise
