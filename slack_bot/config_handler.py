# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Configuration update handlers for Slack integration.

This module provides handlers for user configuration updates including
notification channel selection, delivery time configuration, and
notification enable/disable toggle.

Validates: Requirements 10.3, 10.4, 10.5
"""

import logging
import re
from typing import Optional

from slack_bot.models import SlackConfig, SlackMessage
from slack_bot.config_storage import ConfigStorage
from slack_bot.message_formatter import MessageFormatter


logger = logging.getLogger(__name__)


class ConfigHandler:
    """
    Handles user configuration updates and display.
    
    Provides methods for updating notification preferences, delivery times,
    and notification enable/disable toggles.
    
    Validates: Requirements 10.3, 10.4, 10.5
    """
    
    def __init__(
        self,
        config_storage: ConfigStorage,
        message_formatter: MessageFormatter
    ):
        """
        Initialize configuration handler.
        
        Args:
            config_storage: Database storage for configurations
            message_formatter: Message formatter for responses
        """
        self.config_storage = config_storage
        self.message_formatter = message_formatter
        
        logger.info("Initialized ConfigHandler")
    
    async def display_config(
        self,
        user_id: str
    ) -> SlackMessage:
        """
        Display current user configuration.
        
        Args:
            user_id: TrIAge user ID
            
        Returns:
            Formatted message with current configuration
            
        Validates: Requirements 10.1
        """
        logger.info(
            "Displaying user config",
            extra={"user_id": user_id}
        )
        
        try:
            config = await self.config_storage.get_config(user_id)
            
            if config is None:
                # User has no configuration yet, show defaults
                logger.info(
                    "No config found, showing defaults",
                    extra={"user_id": user_id}
                )
                return self._format_no_config_message()
            
            return self._format_config_display(config)
            
        except Exception as e:
            logger.error(
                "Failed to display config",
                extra={"user_id": user_id, "error": str(e)}
            )
            return self.message_formatter.format_error_message(
                error_type="config_retrieval_failed",
                message="Failed to retrieve your configuration",
                suggestion="Please try again or contact support if the problem persists"
            )
    
    async def update_notification_channel(
        self,
        user_id: str,
        channel: str
    ) -> SlackMessage:
        """
        Update notification channel for user.
        
        Args:
            user_id: TrIAge user ID
            channel: Channel ID (e.g., 'C12345') or 'DM'
            
        Returns:
            Confirmation message
            
        Validates: Requirements 10.3
        """
        logger.info(
            "Updating notification channel",
            extra={"user_id": user_id, "channel": channel}
        )
        
        # Validate channel format
        if channel != "DM" and not channel.startswith('C'):
            logger.warning(
                "Invalid channel format",
                extra={"user_id": user_id, "channel": channel}
            )
            return self.message_formatter.format_error_message(
                error_type="invalid_channel",
                message="Invalid channel format",
                suggestion='Channel must be "DM" or a channel ID starting with "C"'
            )
        
        try:
            # Check if config exists
            existing_config = await self.config_storage.get_config(user_id)
            
            if existing_config is None:
                # Create new config with default values
                config = SlackConfig(
                    user_id=user_id,
                    notification_channel=channel,
                    delivery_time="09:00",
                    notifications_enabled=True,
                    timezone="UTC"
                )
                updated_config = await self.config_storage.create_config(config)
            else:
                # Update existing config
                updated_config = await self.config_storage.update_config(
                    user_id=user_id,
                    notification_channel=channel
                )
            
            if updated_config is None:
                raise ValueError("Failed to update configuration")
            
            logger.info(
                "Notification channel updated",
                extra={"user_id": user_id, "channel": channel}
            )
            
            return self._format_update_confirmation(
                field="notification channel",
                value=channel,
                config=updated_config
            )
            
        except Exception as e:
            logger.error(
                "Failed to update notification channel",
                extra={"user_id": user_id, "error": str(e)}
            )
            return self.message_formatter.format_error_message(
                error_type="config_update_failed",
                message="Failed to update notification channel",
                suggestion="Please try again or contact support if the problem persists"
            )
    
    async def update_delivery_time(
        self,
        user_id: str,
        delivery_time: str
    ) -> SlackMessage:
        """
        Update daily plan delivery time.
        
        Args:
            user_id: TrIAge user ID
            delivery_time: Time in HH:MM format (24-hour)
            
        Returns:
            Confirmation message
            
        Validates: Requirements 10.4
        """
        logger.info(
            "Updating delivery time",
            extra={"user_id": user_id, "delivery_time": delivery_time}
        )
        
        # Validate time format
        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', delivery_time):
            logger.warning(
                "Invalid time format",
                extra={"user_id": user_id, "delivery_time": delivery_time}
            )
            return self.message_formatter.format_error_message(
                error_type="invalid_time_format",
                message="Invalid time format",
                suggestion='Time must be in HH:MM format (24-hour), e.g., "09:00" or "14:30"'
            )
        
        try:
            # Check if config exists
            existing_config = await self.config_storage.get_config(user_id)
            
            if existing_config is None:
                # Create new config with default values
                config = SlackConfig(
                    user_id=user_id,
                    notification_channel="DM",
                    delivery_time=delivery_time,
                    notifications_enabled=True,
                    timezone="UTC"
                )
                updated_config = await self.config_storage.create_config(config)
            else:
                # Update existing config
                updated_config = await self.config_storage.update_config(
                    user_id=user_id,
                    delivery_time=delivery_time
                )
            
            if updated_config is None:
                raise ValueError("Failed to update configuration")
            
            logger.info(
                "Delivery time updated",
                extra={"user_id": user_id, "delivery_time": delivery_time}
            )
            
            return self._format_update_confirmation(
                field="delivery time",
                value=delivery_time,
                config=updated_config
            )
            
        except Exception as e:
            logger.error(
                "Failed to update delivery time",
                extra={"user_id": user_id, "error": str(e)}
            )
            return self.message_formatter.format_error_message(
                error_type="config_update_failed",
                message="Failed to update delivery time",
                suggestion="Please try again or contact support if the problem persists"
            )
    
    async def toggle_notifications(
        self,
        user_id: str,
        enabled: bool
    ) -> SlackMessage:
        """
        Enable or disable proactive notifications.
        
        Args:
            user_id: TrIAge user ID
            enabled: True to enable, False to disable
            
        Returns:
            Confirmation message
            
        Validates: Requirements 10.5
        """
        logger.info(
            "Toggling notifications",
            extra={"user_id": user_id, "enabled": enabled}
        )
        
        try:
            # Check if config exists
            existing_config = await self.config_storage.get_config(user_id)
            
            if existing_config is None:
                # Create new config with default values
                config = SlackConfig(
                    user_id=user_id,
                    notification_channel="DM",
                    delivery_time="09:00",
                    notifications_enabled=enabled,
                    timezone="UTC"
                )
                updated_config = await self.config_storage.create_config(config)
            else:
                # Update existing config
                updated_config = await self.config_storage.update_config(
                    user_id=user_id,
                    notifications_enabled=enabled
                )
            
            if updated_config is None:
                raise ValueError("Failed to update configuration")
            
            logger.info(
                "Notifications toggled",
                extra={"user_id": user_id, "enabled": enabled}
            )
            
            status = "enabled" if enabled else "disabled"
            return self._format_update_confirmation(
                field="notifications",
                value=status,
                config=updated_config
            )
            
        except Exception as e:
            logger.error(
                "Failed to toggle notifications",
                extra={"user_id": user_id, "error": str(e)}
            )
            return self.message_formatter.format_error_message(
                error_type="config_update_failed",
                message="Failed to toggle notifications",
                suggestion="Please try again or contact support if the problem persists"
            )
    
    async def update_timezone(
        self,
        user_id: str,
        timezone: str
    ) -> SlackMessage:
        """
        Update user timezone.
        
        Args:
            user_id: TrIAge user ID
            timezone: Timezone string (e.g., 'America/New_York', 'UTC')
            
        Returns:
            Confirmation message
        """
        logger.info(
            "Updating timezone",
            extra={"user_id": user_id, "timezone": timezone}
        )
        
        try:
            # Check if config exists
            existing_config = await self.config_storage.get_config(user_id)
            
            if existing_config is None:
                # Create new config with default values
                config = SlackConfig(
                    user_id=user_id,
                    notification_channel="DM",
                    delivery_time="09:00",
                    notifications_enabled=True,
                    timezone=timezone
                )
                updated_config = await self.config_storage.create_config(config)
            else:
                # Update existing config
                updated_config = await self.config_storage.update_config(
                    user_id=user_id,
                    timezone=timezone
                )
            
            if updated_config is None:
                raise ValueError("Failed to update configuration")
            
            logger.info(
                "Timezone updated",
                extra={"user_id": user_id, "timezone": timezone}
            )
            
            return self._format_update_confirmation(
                field="timezone",
                value=timezone,
                config=updated_config
            )
            
        except Exception as e:
            logger.error(
                "Failed to update timezone",
                extra={"user_id": user_id, "error": str(e)}
            )
            return self.message_formatter.format_error_message(
                error_type="config_update_failed",
                message="Failed to update timezone",
                suggestion="Please try again or contact support if the problem persists"
            )
    
    def _format_no_config_message(self) -> SlackMessage:
        """
        Format message for user with no configuration.
        
        Returns:
            SlackMessage with default configuration info
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚙️ Your Configuration"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*No configuration found. Using defaults:*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*Notification Channel:*\nDirect Message"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Delivery Time:*\n09:00 UTC"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Notifications:*\nEnabled ✅"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Timezone:*\nUTC"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*To update your configuration, use:*\n"
                           "• `/triage config channel <channel_id>` - Set notification channel\n"
                           "• `/triage config time <HH:MM>` - Set delivery time\n"
                           "• `/triage config notifications <on|off>` - Toggle notifications\n"
                           "• `/triage config timezone <timezone>` - Set timezone"
                }
            }
        ]
        
        return SlackMessage(
            blocks=blocks,
            text="Your Configuration (using defaults)"
        )
    
    def _format_config_display(self, config: SlackConfig) -> SlackMessage:
        """
        Format current configuration for display.
        
        Args:
            config: User's SlackConfig
            
        Returns:
            Formatted SlackMessage
        """
        notification_status = "Enabled ✅" if config.notifications_enabled else "Disabled ❌"
        channel_display = "Direct Message" if config.notification_channel == "DM" else f"<#{config.notification_channel}>"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚙️ Your Configuration"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Notification Channel:*\n{channel_display}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Delivery Time:*\n{config.delivery_time} {config.timezone}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Notifications:*\n{notification_status}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Timezone:*\n{config.timezone}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*To update your configuration, use:*\n"
                           "• `/triage config channel <channel_id>` - Set notification channel\n"
                           "• `/triage config time <HH:MM>` - Set delivery time\n"
                           "• `/triage config notifications <on|off>` - Toggle notifications\n"
                           "• `/triage config timezone <timezone>` - Set timezone"
                }
            }
        ]
        
        return SlackMessage(
            blocks=blocks,
            text="Your Configuration"
        )
    
    def _format_update_confirmation(
        self,
        field: str,
        value: str,
        config: SlackConfig
    ) -> SlackMessage:
        """
        Format confirmation message for configuration update.
        
        Args:
            field: Field that was updated
            value: New value
            config: Updated configuration
            
        Returns:
            Formatted confirmation message
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Configuration updated successfully*\n\n"
                           f"Updated {field} to: `{value}`"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Use `/triage config` to view your full configuration"
                    }
                ]
            }
        ]
        
        return SlackMessage(
            blocks=blocks,
            text=f"Configuration updated: {field} = {value}"
        )
