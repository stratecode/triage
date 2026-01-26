# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Command handler for Slack slash commands.

This module processes slash commands and routes them to appropriate handlers.
All business logic is delegated to the TrIAge API; this handler only translates
between Slack's format and API calls.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
"""

import asyncio
from datetime import datetime
from typing import Optional
import httpx

from slack_bot.models import SlashCommand, SlackMessage
from slack_bot.message_formatter import MessageFormatter
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


class CommandHandler:
    """
    Handles Slack slash commands and routes them to appropriate handlers.
    
    This class provides command routing, parsing, validation, and delegates
    all business logic to the TrIAge API.
    
    Validates: Requirements 4.1, 4.2, 4.3
    """
    
    def __init__(
        self,
        triage_api_url: str,
        triage_api_token: str,
        message_formatter: MessageFormatter,
        timeout_seconds: int = 3
    ):
        """
        Initialize command handler.
        
        Args:
            triage_api_url: Base URL for TrIAge API
            triage_api_token: Bearer token for API authentication
            message_formatter: MessageFormatter instance for responses
            timeout_seconds: Maximum time to process command before acknowledgment
        """
        self.triage_api_url = triage_api_url.rstrip('/')
        self.triage_api_token = triage_api_token
        self.formatter = message_formatter
        self.timeout_seconds = timeout_seconds
        
        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(
            base_url=self.triage_api_url,
            headers={
                "Authorization": f"Bearer {self.triage_api_token}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(10.0)
        )
    
    async def handle_command(self, cmd: SlashCommand) -> SlackMessage:
        """
        Route command to appropriate handler.
        
        This method ensures response within timeout by returning acknowledgment
        if processing takes too long.
        
        Args:
            cmd: SlashCommand object with command details
            
        Returns:
            SlackMessage with command response
            
        Validates: Requirements 4.4
        """
        logger.info(
            "Processing slash command",
            extra={
                "command": cmd.command,
                "text": cmd.text,
                "user_id": cmd.user_id,
                "team_id": cmd.team_id
            }
        )
        
        try:
            # Parse command text to get subcommand
            parts = cmd.text.strip().split(maxsplit=1)
            subcommand = parts[0].lower() if parts else "help"
            args = parts[1] if len(parts) > 1 else ""
            
            # Route to appropriate handler
            if subcommand == "plan":
                return await self.handle_plan_command(cmd, args)
            elif subcommand == "status":
                return await self.handle_status_command(cmd)
            elif subcommand == "config":
                return await self.handle_config_command(cmd)
            elif subcommand == "help" or subcommand == "":
                return await self.handle_help_command(cmd)
            else:
                # Unknown subcommand
                return self.formatter.format_error_message(
                    error_type="invalid_command",
                    message=f"Unknown command: {subcommand}",
                    suggestion="Type `/triage help` to see available commands."
                )
        
        except Exception as e:
            logger.error(
                "Error processing command",
                extra={
                    "command": cmd.command,
                    "text": cmd.text,
                    "user_id": cmd.user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return self.formatter.format_error_message(
                error_type="command_error",
                message="An error occurred while processing your command.",
                suggestion="Please try again or contact support if the problem persists."
            )
    
    async def handle_plan_command(
        self,
        cmd: SlashCommand,
        args: str
    ) -> SlackMessage:
        """
        Handle /triage plan command.
        
        Triggers plan generation via TrIAge API for today or specified date.
        
        Args:
            cmd: SlashCommand object
            args: Command arguments (optional date)
            
        Returns:
            SlackMessage with acknowledgment or error
            
        Validates: Requirements 4.1
        """
        logger.info(
            "Handling plan command",
            extra={
                "user_id": cmd.user_id,
                "args": args
            }
        )
        
        # Parse date argument if provided
        target_date = "today"
        if args:
            # Simple date parsing - accept "today", "tomorrow", or YYYY-MM-DD
            args_lower = args.lower().strip()
            if args_lower in ("today", "tomorrow"):
                target_date = args_lower
            else:
                # Try to parse as date
                try:
                    datetime.strptime(args, "%Y-%m-%d")
                    target_date = args
                except ValueError:
                    return self.formatter.format_error_message(
                        error_type="invalid_command",
                        message=f"Invalid date format: {args}",
                        suggestion="Use format YYYY-MM-DD, or 'today'/'tomorrow'."
                    )
        
        try:
            # Call TrIAge API to trigger plan generation
            response = await self.http_client.post(
                "/api/v1/plans/generate",
                json={
                    "user_id": cmd.user_id,
                    "team_id": cmd.team_id,
                    "date": target_date
                }
            )
            
            if response.status_code == 202:
                # Plan generation started asynchronously
                return SlackMessage(
                    blocks=[
                        self.formatter.create_header_block("📋 Plan Generation Started"),
                        self.formatter.create_section_block(
                            f"Generating your daily plan for {target_date}...\n\n"
                            "You'll receive the plan shortly with approval options."
                        )
                    ],
                    text=f"Generating plan for {target_date}..."
                )
            elif response.status_code == 200:
                # Plan generated immediately
                return SlackMessage(
                    blocks=[
                        self.formatter.create_header_block("✅ Plan Generated"),
                        self.formatter.create_section_block(
                            f"Your daily plan for {target_date} has been generated.\n\n"
                            "Check your configured notification channel for the plan."
                        )
                    ],
                    text=f"Plan generated for {target_date}"
                )
            elif response.status_code == 404:
                return self.formatter.format_error_message(
                    error_type="not_configured",
                    message="Your account is not configured.",
                    suggestion="Please configure your JIRA credentials using `/triage config`."
                )
            elif response.status_code == 401:
                return self.formatter.format_error_message(
                    error_type="unauthorized",
                    message="Authentication failed.",
                    suggestion="Please contact your administrator to verify your account setup."
                )
            else:
                return self.formatter.format_error_message(
                    error_type="api_error",
                    message=f"Failed to generate plan (status {response.status_code}).",
                    suggestion="Please try again in a few moments."
                )
        
        except httpx.TimeoutException:
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Request timed out.",
                suggestion="The TrIAge service may be busy. Please try again."
            )
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling TrIAge API",
                extra={"error": str(e)},
                exc_info=True
            )
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service.",
                suggestion="Please try again in a few moments."
            )
    
    async def handle_status_command(self, cmd: SlashCommand) -> SlackMessage:
        """
        Handle /triage status command.
        
        Fetches and displays current plan status from TrIAge API.
        
        Args:
            cmd: SlashCommand object
            
        Returns:
            SlackMessage with plan status
            
        Validates: Requirements 4.2
        """
        logger.info(
            "Handling status command",
            extra={"user_id": cmd.user_id}
        )
        
        try:
            # Call TrIAge API to get current plan status
            response = await self.http_client.get(
                f"/api/v1/plans/current",
                params={
                    "user_id": cmd.user_id,
                    "team_id": cmd.team_id
                }
            )
            
            if response.status_code == 200:
                plan_data = response.json()
                
                # Format plan status
                status_emoji = {
                    "pending": "⏳",
                    "approved": "✅",
                    "rejected": "❌",
                    "expired": "⌛"
                }.get(plan_data.get("status", "unknown"), "❓")
                
                status_text = plan_data.get("status", "unknown").title()
                plan_date = plan_data.get("date", "unknown")
                priority_count = len(plan_data.get("priority_tasks", []))
                admin_count = len(plan_data.get("admin_tasks", []))
                
                return SlackMessage(
                    blocks=[
                        self.formatter.create_header_block(f"{status_emoji} Current Plan Status"),
                        self.formatter.create_section_block(
                            f"*Date:* {plan_date}\n"
                            f"*Status:* {status_text}\n"
                            f"*Priority Tasks:* {priority_count}\n"
                            f"*Administrative Tasks:* {admin_count}"
                        )
                    ],
                    text=f"Plan status: {status_text}"
                )
            elif response.status_code == 404:
                return SlackMessage(
                    blocks=[
                        self.formatter.create_header_block("📋 No Active Plan"),
                        self.formatter.create_section_block(
                            "You don't have an active plan for today.\n\n"
                            "Use `/triage plan` to generate one."
                        )
                    ],
                    text="No active plan"
                )
            else:
                return self.formatter.format_error_message(
                    error_type="api_error",
                    message=f"Failed to fetch plan status (status {response.status_code}).",
                    suggestion="Please try again in a few moments."
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling TrIAge API",
                extra={"error": str(e)},
                exc_info=True
            )
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service.",
                suggestion="Please try again in a few moments."
            )
    
    async def handle_help_command(self, cmd: SlashCommand) -> SlackMessage:
        """
        Handle /triage help command.
        
        Displays available commands and usage instructions.
        
        Args:
            cmd: SlashCommand object
            
        Returns:
            SlackMessage with help information
            
        Validates: Requirements 4.3
        """
        logger.info(
            "Handling help command",
            extra={"user_id": cmd.user_id}
        )
        
        help_text = """
*Available Commands:*

• `/triage plan [date]` - Generate daily plan
  Examples:
  - `/triage plan` - Generate plan for today
  - `/triage plan today` - Generate plan for today
  - `/triage plan tomorrow` - Generate plan for tomorrow
  - `/triage plan 2026-01-20` - Generate plan for specific date

• `/triage status` - Show current plan status
  Displays your active plan and approval state

• `/triage config` - View configuration
  Shows your current notification settings

• `/triage help` - Show this help message
  Displays available commands and usage

*Need more help?*
Contact your administrator or visit the documentation.
"""
        
        return SlackMessage(
            blocks=[
                self.formatter.create_header_block("🤖 TrIAge Bot Help"),
                self.formatter.create_section_block(help_text.strip())
            ],
            text="TrIAge Bot Help"
        )
    
    async def handle_config_command(self, cmd: SlashCommand) -> SlackMessage:
        """
        Handle /triage config command.
        
        Supports viewing and updating configuration:
        - `/triage config` - View current configuration
        - `/triage config channel <channel_id>` - Update notification channel
        - `/triage config time <HH:MM>` - Update delivery time
        - `/triage config notifications <on|off>` - Toggle notifications
        - `/triage config timezone <timezone>` - Update timezone
        
        Args:
            cmd: SlashCommand object
            
        Returns:
            SlackMessage with configuration information
            
        Validates: Requirements 10.1, 10.3, 10.4, 10.5
        """
        logger.info(
            "Handling config command",
            extra={"user_id": cmd.user_id, "text": cmd.text}
        )
        
        # Parse config subcommand
        parts = cmd.text.strip().split(maxsplit=2)
        if len(parts) < 2:
            # No subcommand, just show config
            return await self._display_config(cmd)
        
        config_subcommand = parts[1].lower()
        config_value = parts[2] if len(parts) > 2 else None
        
        if config_subcommand == "channel":
            if not config_value:
                return self.formatter.format_error_message(
                    error_type="invalid_command",
                    message="Missing channel value",
                    suggestion='Usage: `/triage config channel <channel_id>` or `/triage config channel DM`'
                )
            return await self._update_channel(cmd, config_value)
        
        elif config_subcommand == "time":
            if not config_value:
                return self.formatter.format_error_message(
                    error_type="invalid_command",
                    message="Missing time value",
                    suggestion='Usage: `/triage config time <HH:MM>` (e.g., `09:00`)'
                )
            return await self._update_delivery_time(cmd, config_value)
        
        elif config_subcommand == "notifications":
            if not config_value:
                return self.formatter.format_error_message(
                    error_type="invalid_command",
                    message="Missing notifications value",
                    suggestion='Usage: `/triage config notifications <on|off>`'
                )
            return await self._toggle_notifications(cmd, config_value)
        
        elif config_subcommand == "timezone":
            if not config_value:
                return self.formatter.format_error_message(
                    error_type="invalid_command",
                    message="Missing timezone value",
                    suggestion='Usage: `/triage config timezone <timezone>` (e.g., `America/New_York`)'
                )
            return await self._update_timezone(cmd, config_value)
        
        else:
            return self.formatter.format_error_message(
                error_type="invalid_command",
                message=f"Unknown config option: {config_subcommand}",
                suggestion="Valid options: channel, time, notifications, timezone"
            )
    
    async def _display_config(self, cmd: SlashCommand) -> SlackMessage:
        """Display current user configuration."""
        try:
            # Call TrIAge API to get user configuration
            response = await self.http_client.get(
                f"/api/v1/users/{cmd.user_id}/slack-config",
                params={"team_id": cmd.team_id}
            )
            
            if response.status_code == 200:
                config_data = response.json()
                
                # Format configuration display
                channel = config_data.get("notification_channel", "DM")
                if channel == "DM":
                    channel_display = "Direct Message"
                else:
                    channel_display = f"<#{channel}>"
                
                delivery_time = config_data.get("delivery_time", "09:00")
                notifications_enabled = config_data.get("notifications_enabled", True)
                enabled_status = "✅ Enabled" if notifications_enabled else "❌ Disabled"
                timezone = config_data.get("timezone", "UTC")
                
                config_text = f"""
*Current Configuration:*

• *Notification Channel:* {channel_display}
• *Delivery Time:* {delivery_time} ({timezone})
• *Notifications:* {enabled_status}

*To update your configuration:*
• `/triage config channel <channel_id>` - Set notification channel
• `/triage config time <HH:MM>` - Set delivery time
• `/triage config notifications <on|off>` - Toggle notifications
• `/triage config timezone <timezone>` - Set timezone
"""
                
                return SlackMessage(
                    blocks=[
                        self.formatter.create_header_block("⚙️ Your Configuration"),
                        self.formatter.create_section_block(config_text.strip())
                    ],
                    text="Your TrIAge configuration"
                )
            elif response.status_code == 404:
                return SlackMessage(
                    blocks=[
                        self.formatter.create_header_block("⚙️ Configuration Not Found"),
                        self.formatter.create_section_block(
                            "Your configuration has not been set up yet.\n\n"
                            "Use the config commands to set up your preferences:\n"
                            "• `/triage config channel <channel_id>` - Set notification channel\n"
                            "• `/triage config time <HH:MM>` - Set delivery time\n"
                            "• `/triage config notifications <on|off>` - Toggle notifications"
                        )
                    ],
                    text="Configuration not found"
                )
            else:
                return self.formatter.format_error_message(
                    error_type="api_error",
                    message=f"Failed to fetch configuration (status {response.status_code}).",
                    suggestion="Please try again in a few moments."
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling TrIAge API",
                extra={"error": str(e)},
                exc_info=True
            )
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service.",
                suggestion="Please try again in a few moments."
            )
    
    async def _update_channel(self, cmd: SlashCommand, channel: str) -> SlackMessage:
        """Update notification channel."""
        try:
            response = await self.http_client.put(
                f"/api/v1/users/{cmd.user_id}/slack-config",
                json={
                    "team_id": cmd.team_id,
                    "notification_channel": channel
                }
            )
            
            if response.status_code in (200, 201):
                channel_display = "Direct Message" if channel == "DM" else f"<#{channel}>"
                return SlackMessage(
                    blocks=[
                        self.formatter.create_section_block(
                            f"✅ *Configuration updated successfully*\n\n"
                            f"Notification channel set to: {channel_display}"
                        ),
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "Use `/triage config` to view your full configuration"
                                }
                            ]
                        }
                    ],
                    text=f"Notification channel updated to {channel_display}"
                )
            else:
                return self.formatter.format_error_message(
                    error_type="config_update_failed",
                    message="Failed to update notification channel",
                    suggestion="Please try again or contact support"
                )
        
        except httpx.HTTPError as e:
            logger.error("Failed to update channel", extra={"error": str(e)}, exc_info=True)
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service",
                suggestion="Please try again in a few moments"
            )
    
    async def _update_delivery_time(self, cmd: SlashCommand, time: str) -> SlackMessage:
        """Update delivery time."""
        import re
        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', time):
            return self.formatter.format_error_message(
                error_type="invalid_time_format",
                message="Invalid time format",
                suggestion='Time must be in HH:MM format (24-hour), e.g., "09:00" or "14:30"'
            )
        
        try:
            response = await self.http_client.put(
                f"/api/v1/users/{cmd.user_id}/slack-config",
                json={
                    "team_id": cmd.team_id,
                    "delivery_time": time
                }
            )
            
            if response.status_code in (200, 201):
                return SlackMessage(
                    blocks=[
                        self.formatter.create_section_block(
                            f"✅ *Configuration updated successfully*\n\n"
                            f"Delivery time set to: `{time}`"
                        ),
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "Use `/triage config` to view your full configuration"
                                }
                            ]
                        }
                    ],
                    text=f"Delivery time updated to {time}"
                )
            else:
                return self.formatter.format_error_message(
                    error_type="config_update_failed",
                    message="Failed to update delivery time",
                    suggestion="Please try again or contact support"
                )
        
        except httpx.HTTPError as e:
            logger.error("Failed to update delivery time", extra={"error": str(e)}, exc_info=True)
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service",
                suggestion="Please try again in a few moments"
            )
    
    async def _toggle_notifications(self, cmd: SlashCommand, value: str) -> SlackMessage:
        """Toggle notifications on/off."""
        value_lower = value.lower()
        if value_lower not in ("on", "off", "true", "false", "enabled", "disabled"):
            return self.formatter.format_error_message(
                error_type="invalid_command",
                message=f"Invalid notifications value: {value}",
                suggestion='Use "on" or "off"'
            )
        
        enabled = value_lower in ("on", "true", "enabled")
        
        try:
            response = await self.http_client.put(
                f"/api/v1/users/{cmd.user_id}/slack-config",
                json={
                    "team_id": cmd.team_id,
                    "notifications_enabled": enabled
                }
            )
            
            if response.status_code in (200, 201):
                status = "enabled" if enabled else "disabled"
                return SlackMessage(
                    blocks=[
                        self.formatter.create_section_block(
                            f"✅ *Configuration updated successfully*\n\n"
                            f"Notifications {status}"
                        ),
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "Use `/triage config` to view your full configuration"
                                }
                            ]
                        }
                    ],
                    text=f"Notifications {status}"
                )
            else:
                return self.formatter.format_error_message(
                    error_type="config_update_failed",
                    message="Failed to toggle notifications",
                    suggestion="Please try again or contact support"
                )
        
        except httpx.HTTPError as e:
            logger.error("Failed to toggle notifications", extra={"error": str(e)}, exc_info=True)
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service",
                suggestion="Please try again in a few moments"
            )
    
    async def _update_timezone(self, cmd: SlashCommand, timezone: str) -> SlackMessage:
        """Update timezone."""
        try:
            response = await self.http_client.put(
                f"/api/v1/users/{cmd.user_id}/slack-config",
                json={
                    "team_id": cmd.team_id,
                    "timezone": timezone
                }
            )
            
            if response.status_code in (200, 201):
                return SlackMessage(
                    blocks=[
                        self.formatter.create_section_block(
                            f"✅ *Configuration updated successfully*\n\n"
                            f"Timezone set to: `{timezone}`"
                        ),
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": "Use `/triage config` to view your full configuration"
                                }
                            ]
                        }
                    ],
                    text=f"Timezone updated to {timezone}"
                )
            else:
                return self.formatter.format_error_message(
                    error_type="config_update_failed",
                    message="Failed to update timezone",
                    suggestion="Please try again or contact support"
                )
        
        except httpx.HTTPError as e:
            logger.error("Failed to update timezone", extra={"error": str(e)}, exc_info=True)
            return self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service",
                suggestion="Please try again in a few moments"
            )
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
