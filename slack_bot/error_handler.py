# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Error handling utilities for Slack bot.

This module provides centralized error handling with user-friendly messages
and troubleshooting suggestions.

Validates: Requirements 11.3
"""

import logging
from typing import Optional, Dict, Any
from slack_bot.templates import ErrorTemplate
from slack_bot.models import SlackMessage
from slack_bot.triage_api_client import TriageAPIError
from slack_bot.slack_api_client import SlackAPIRetryError
from slack_sdk.errors import SlackApiError


logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Centralized error handler for Slack bot.
    
    Converts exceptions into user-friendly Slack messages with
    troubleshooting suggestions.
    
    Validates: Requirements 11.3
    """
    
    def __init__(self, jira_base_url: str = "https://jira.example.com"):
        """
        Initialize error handler.
        
        Args:
            jira_base_url: Base URL for JIRA instance
        """
        self.template = ErrorTemplate()
        self.jira_base_url = jira_base_url
    
    def handle_triage_api_error(
        self,
        error: TriageAPIError,
        context: Optional[Dict[str, Any]] = None
    ) -> SlackMessage:
        """
        Handle TrIAge API errors.
        
        Args:
            error: TrIAge API error
            context: Optional context for debugging
            
        Returns:
            SlackMessage with error details and suggestions
            
        Validates: Requirements 11.3
        """
        logger.error(
            "TrIAge API error",
            extra={
                "error": str(error),
                "status_code": error.status_code,
                "context": context
            },
            exc_info=True
        )
        
        # Determine error type based on status code
        if error.status_code == 401:
            return self.template.render(
                error_type="unauthorized",
                message="Authentication failed with TrIAge API.",
                suggestion="Please check your API credentials and try again. Contact your administrator if the problem persists."
            )
        
        elif error.status_code == 403:
            return self.template.render(
                error_type="unauthorized",
                message="You don't have permission to perform this action.",
                suggestion="Contact your workspace administrator to verify your permissions."
            )
        
        elif error.status_code == 404:
            return self.template.render(
                error_type="invalid_command",
                message="The requested resource was not found.",
                suggestion="The plan or resource you're looking for may have been deleted or doesn't exist."
            )
        
        elif error.status_code == 429:
            return self.template.render(
                error_type="rate_limited",
                message="Too many requests to TrIAge API.",
                suggestion="Please wait a moment and try again. The system will automatically retry your request."
            )
        
        elif error.status_code in {500, 502, 503, 504}:
            return self.template.render(
                error_type="api_unavailable",
                message="TrIAge service is temporarily unavailable.",
                suggestion="Please try again in a few minutes. If the problem persists, contact support."
            )
        
        else:
            return self.template.render(
                error_type="unknown",
                message=f"An error occurred: {error.message}",
                suggestion="Please try again. If the problem persists, contact support with the error details."
            )
    
    def handle_slack_api_error(
        self,
        error: SlackAPIRetryError,
        context: Optional[Dict[str, Any]] = None
    ) -> SlackMessage:
        """
        Handle Slack API errors.
        
        Args:
            error: Slack API retry error
            context: Optional context for debugging
            
        Returns:
            SlackMessage with error details and suggestions
            
        Validates: Requirements 11.3
        """
        logger.error(
            "Slack API error",
            extra={
                "error": str(error),
                "attempts": error.attempts,
                "context": context
            },
            exc_info=True
        )
        
        # Check if original error is a SlackApiError
        if isinstance(error.original_error, SlackApiError):
            slack_error = error.original_error
            error_code = slack_error.response.get('error', 'unknown')
            
            if error_code == 'invalid_auth':
                return self.template.render(
                    error_type="unauthorized",
                    message="Slack authentication token is invalid or expired.",
                    suggestion="Please reinstall the TrIAge bot or contact your administrator."
                )
            
            elif error_code == 'not_in_channel':
                return self.template.render(
                    error_type="unauthorized",
                    message="The bot is not a member of the requested channel.",
                    suggestion="Please invite the TrIAge bot to the channel and try again."
                )
            
            elif error_code == 'channel_not_found':
                return self.template.render(
                    error_type="invalid_command",
                    message="The specified channel was not found.",
                    suggestion="Please check the channel name and try again."
                )
            
            elif error_code == 'rate_limited':
                return self.template.render(
                    error_type="rate_limited",
                    message="Slack rate limit exceeded.",
                    suggestion="Your message will be delivered shortly. No action needed."
                )
        
        # Generic Slack API error
        return self.template.render(
            error_type="network_error",
            message="Failed to communicate with Slack after multiple attempts.",
            suggestion="Please check your connection and try again. If the problem persists, contact support."
        )
    
    def handle_validation_error(
        self,
        message: str,
        suggestion: Optional[str] = None
    ) -> SlackMessage:
        """
        Handle validation errors (invalid input, missing configuration, etc.).
        
        Args:
            message: Error message
            suggestion: Optional custom suggestion
            
        Returns:
            SlackMessage with error details and suggestions
            
        Validates: Requirements 11.3
        """
        logger.warning(
            "Validation error",
            extra={"error_message": message}
        )
        
        return self.template.render(
            error_type="invalid_command",
            message=message,
            suggestion=suggestion
        )
    
    def handle_configuration_error(
        self,
        message: str,
        suggestion: Optional[str] = None
    ) -> SlackMessage:
        """
        Handle configuration errors (missing JIRA credentials, etc.).
        
        Args:
            message: Error message
            suggestion: Optional custom suggestion
            
        Returns:
            SlackMessage with error details and suggestions
            
        Validates: Requirements 11.3
        """
        logger.warning(
            "Configuration error",
            extra={"error_message": message}
        )
        
        return self.template.render(
            error_type="not_configured",
            message=message,
            suggestion=suggestion or "Please configure your settings using `/triage config`."
        )
    
    def handle_generic_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> SlackMessage:
        """
        Handle generic/unexpected errors.
        
        Args:
            error: Exception that occurred
            context: Optional context for debugging
            
        Returns:
            SlackMessage with error details and suggestions
            
        Validates: Requirements 11.3
        """
        logger.error(
            "Unexpected error",
            extra={
                "error": str(error),
                "error_type": type(error).__name__,
                "context": context
            },
            exc_info=True
        )
        
        return self.template.render(
            error_type="unknown",
            message="An unexpected error occurred while processing your request.",
            suggestion="Please try again. If the problem persists, contact support."
        )
    
    def get_command_help_message(self, invalid_command: Optional[str] = None) -> SlackMessage:
        """
        Generate help message for invalid commands.
        
        Args:
            invalid_command: The invalid command that was entered
            
        Returns:
            SlackMessage with command help
            
        Validates: Requirements 11.3
        """
        if invalid_command:
            message = f"Unknown command: `{invalid_command}`"
        else:
            message = "Invalid command syntax."
        
        suggestion = (
            "Available commands:\n"
            "• `/triage plan [date]` - Generate a daily plan\n"
            "• `/triage status` - Check current plan status\n"
            "• `/triage config` - View or update configuration\n"
            "• `/triage help` - Show this help message\n\n"
            "Type `/triage help` for more details."
        )
        
        return self.template.render(
            error_type="invalid_command",
            message=message,
            suggestion=suggestion
        )


def create_error_handler(jira_base_url: str = "https://jira.example.com") -> ErrorHandler:
    """
    Factory function to create an ErrorHandler instance.
    
    Args:
        jira_base_url: Base URL for JIRA instance
        
    Returns:
        Configured ErrorHandler instance
    """
    return ErrorHandler(jira_base_url=jira_base_url)
