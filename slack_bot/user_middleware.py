# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
User identification middleware for Slack integration.

This module extracts Slack user IDs from all events and maps them to
TrIAge users. It ensures every request is properly attributed to a user
for data isolation and authorization.

Validates: Requirements 8.1
"""

from typing import Optional, Dict, Any
from slack_bot.models import SlackUser, WebhookEvent, SlashCommand, BlockAction
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


class UserIdentificationMiddleware:
    """
    Middleware for extracting and validating user identification from Slack events.
    
    This class ensures that every Slack event is properly attributed to a user
    and provides user mapping functionality.
    
    Validates: Requirements 8.1
    """
    
    def __init__(self, user_mapper: 'UserMapper'):
        """
        Initialize user identification middleware.
        
        Args:
            user_mapper: UserMapper instance for Slack-to-TrIAge user mapping
        """
        self.user_mapper = user_mapper
        logger.info("User identification middleware initialized")
    
    def extract_user_id(self, event: Any) -> Optional[str]:
        """
        Extract Slack user ID from any event type.
        
        Handles WebhookEvent, SlashCommand, BlockAction, and raw payloads.
        
        Args:
            event: Event object or raw payload dict
            
        Returns:
            Slack user ID if found, None otherwise
            
        Validates: Requirements 8.1
        """
        # Handle different event types
        if isinstance(event, WebhookEvent):
            user_id = event.user_id
        elif isinstance(event, SlashCommand):
            user_id = event.user_id
        elif isinstance(event, BlockAction):
            user_id = event.user_id
        elif isinstance(event, dict):
            # Raw payload - try multiple extraction paths
            user_id = (
                event.get('user_id') or
                event.get('user', {}).get('id') if isinstance(event.get('user'), dict) else event.get('user') or
                event.get('event', {}).get('user') or
                event.get('message', {}).get('user')
            )
        else:
            logger.warning(
                "Unknown event type for user extraction",
                extra={"event_type": type(event).__name__}
            )
            return None
        
        if not user_id or user_id == 'UNKNOWN':
            logger.warning(
                "Failed to extract user ID from event",
                extra={"event_type": type(event).__name__}
            )
            return None
        
        logger.debug(
            "Extracted user ID from event",
            extra={
                "user_id": user_id,
                "event_type": type(event).__name__
            }
        )
        
        return user_id
    
    def extract_team_id(self, event: Any) -> Optional[str]:
        """
        Extract Slack team/workspace ID from any event type.
        
        Args:
            event: Event object or raw payload dict
            
        Returns:
            Slack team ID if found, None otherwise
            
        Validates: Requirements 8.1
        """
        # Handle different event types
        if isinstance(event, WebhookEvent):
            team_id = event.team_id
        elif isinstance(event, SlashCommand):
            team_id = event.team_id
        elif isinstance(event, BlockAction):
            team_id = event.team_id
        elif isinstance(event, dict):
            # Raw payload - try multiple extraction paths
            team_id = (
                event.get('team_id') or
                event.get('team', {}).get('id') if isinstance(event.get('team'), dict) else event.get('team') or
                event.get('event', {}).get('team')
            )
        else:
            logger.warning(
                "Unknown event type for team extraction",
                extra={"event_type": type(event).__name__}
            )
            return None
        
        if not team_id or team_id == 'UNKNOWN':
            logger.warning(
                "Failed to extract team ID from event",
                extra={"event_type": type(event).__name__}
            )
            return None
        
        logger.debug(
            "Extracted team ID from event",
            extra={
                "team_id": team_id,
                "event_type": type(event).__name__
            }
        )
        
        return team_id
    
    async def identify_user(self, event: Any) -> Optional[SlackUser]:
        """
        Extract user ID from event and map to TrIAge user.
        
        This is the main entry point for user identification. It extracts
        the Slack user ID and team ID, then looks up the corresponding
        TrIAge user mapping.
        
        Args:
            event: Event object or raw payload dict
            
        Returns:
            SlackUser if mapping exists, None otherwise
            
        Validates: Requirements 8.1
        """
        slack_user_id = self.extract_user_id(event)
        slack_team_id = self.extract_team_id(event)
        
        if not slack_user_id or not slack_team_id:
            logger.warning(
                "Cannot identify user - missing user_id or team_id",
                extra={
                    "has_user_id": bool(slack_user_id),
                    "has_team_id": bool(slack_team_id)
                }
            )
            return None
        
        # Look up user mapping
        slack_user = await self.user_mapper.get_user_mapping(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id
        )
        
        if slack_user:
            logger.info(
                "User identified successfully",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id,
                    "triage_user_id": slack_user.triage_user_id
                }
            )
        else:
            logger.warning(
                "No user mapping found",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id
                }
            )
        
        return slack_user
    
    async def require_user(self, event: Any) -> SlackUser:
        """
        Extract and validate user identification, raising error if not found.
        
        Use this method when user identification is required for the operation.
        
        Args:
            event: Event object or raw payload dict
            
        Returns:
            SlackUser mapping
            
        Raises:
            ValueError: If user cannot be identified or mapping doesn't exist
            
        Validates: Requirements 8.1
        """
        slack_user = await self.identify_user(event)
        
        if not slack_user:
            slack_user_id = self.extract_user_id(event)
            slack_team_id = self.extract_team_id(event)
            
            error_msg = "User identification required but not found"
            logger.error(
                error_msg,
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id
                }
            )
            raise ValueError(error_msg)
        
        return slack_user


class UserMapper:
    """
    Maps Slack users to TrIAge users.
    
    This class provides user mapping storage and retrieval functionality,
    ensuring proper user identification across the system.
    
    Validates: Requirements 8.1
    """
    
    def __init__(self, user_storage: 'UserMappingStorage'):
        """
        Initialize user mapper.
        
        Args:
            user_storage: UserMappingStorage instance for persistence
        """
        self.storage = user_storage
        logger.info("User mapper initialized")
    
    async def get_user_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str
    ) -> Optional[SlackUser]:
        """
        Retrieve user mapping by Slack user ID and team ID.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            
        Returns:
            SlackUser if mapping exists, None otherwise
            
        Validates: Requirements 8.1
        """
        logger.debug(
            "Looking up user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id
            }
        )
        
        return await self.storage.get_mapping(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id
        )
    
    async def create_user_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str,
        triage_user_id: str,
        jira_email: str,
        display_name: str
    ) -> SlackUser:
        """
        Create a new user mapping.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            triage_user_id: TrIAge internal user ID
            jira_email: User's JIRA account email
            display_name: User's display name
            
        Returns:
            Created SlackUser mapping
            
        Raises:
            ValueError: If mapping already exists
            
        Validates: Requirements 8.1
        """
        logger.info(
            "Creating user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id,
                "triage_user_id": triage_user_id
            }
        )
        
        slack_user = SlackUser(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            triage_user_id=triage_user_id,
            jira_email=jira_email,
            display_name=display_name
        )
        
        return await self.storage.create_mapping(slack_user)
    
    async def update_user_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str,
        jira_email: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> Optional[SlackUser]:
        """
        Update an existing user mapping.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            jira_email: New JIRA email (optional)
            display_name: New display name (optional)
            
        Returns:
            Updated SlackUser if mapping exists, None otherwise
            
        Validates: Requirements 8.1
        """
        logger.info(
            "Updating user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id
            }
        )
        
        return await self.storage.update_mapping(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            jira_email=jira_email,
            display_name=display_name
        )
    
    async def delete_user_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str
    ) -> bool:
        """
        Delete a user mapping.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            
        Returns:
            True if mapping was deleted, False if not found
            
        Validates: Requirements 8.1
        """
        logger.info(
            "Deleting user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id
            }
        )
        
        return await self.storage.delete_mapping(
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id
        )
    
    async def list_workspace_users(self, slack_team_id: str) -> list[SlackUser]:
        """
        List all user mappings for a workspace.
        
        Args:
            slack_team_id: Slack workspace/team ID
            
        Returns:
            List of SlackUser mappings for the workspace
            
        Validates: Requirements 8.1
        """
        logger.debug(
            "Listing workspace users",
            extra={"slack_team_id": slack_team_id}
        )
        
        return await self.storage.list_workspace_mappings(slack_team_id)
