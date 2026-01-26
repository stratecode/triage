# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Data isolation checks for multi-user Slack integration.

This module provides authorization checks and data isolation enforcement
to ensure users can only access their own data and cannot view or modify
other users' information.

Validates: Requirements 8.2, 8.5
"""

from typing import Optional, Any, Dict
from slack_bot.models import SlackUser
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


class DataIsolationError(Exception):
    """
    Exception raised when data isolation is violated.
    
    This exception indicates an attempt to access data belonging to
    another user, which is a security violation.
    """
    pass


class DataIsolationChecker:
    """
    Enforces data isolation between users.
    
    This class provides authorization checks to ensure users can only
    access their own data and prevents cross-user data access.
    
    Validates: Requirements 8.2, 8.5
    """
    
    def __init__(self):
        """Initialize data isolation checker."""
        logger.info("Data isolation checker initialized")
    
    def verify_user_access(
        self,
        requesting_user: SlackUser,
        resource_user_id: str,
        resource_type: str = "resource"
    ) -> None:
        """
        Verify that requesting user has access to resource owned by resource_user_id.
        
        This method enforces the rule that users can only access their own data.
        
        Args:
            requesting_user: SlackUser making the request
            resource_user_id: TrIAge user ID that owns the resource
            resource_type: Type of resource being accessed (for logging)
            
        Raises:
            DataIsolationError: If user attempts to access another user's data
            
        Validates: Requirements 8.2, 8.5
        """
        if requesting_user.triage_user_id != resource_user_id:
            logger.error(
                "Data isolation violation detected",
                extra={
                    "requesting_user": requesting_user.triage_user_id,
                    "resource_owner": resource_user_id,
                    "resource_type": resource_type,
                    "slack_user_id": requesting_user.slack_user_id,
                    "slack_team_id": requesting_user.slack_team_id
                }
            )
            raise DataIsolationError(
                f"User {requesting_user.triage_user_id} cannot access "
                f"{resource_type} owned by {resource_user_id}"
            )
        
        logger.debug(
            "User access verified",
            extra={
                "user_id": requesting_user.triage_user_id,
                "resource_type": resource_type
            }
        )
    
    def verify_workspace_isolation(
        self,
        requesting_user: SlackUser,
        resource_team_id: str
    ) -> None:
        """
        Verify that requesting user belongs to the same workspace as the resource.
        
        This prevents cross-workspace data access.
        
        Args:
            requesting_user: SlackUser making the request
            resource_team_id: Slack team ID that owns the resource
            
        Raises:
            DataIsolationError: If user attempts to access resource from different workspace
            
        Validates: Requirements 8.2, 8.5
        """
        if requesting_user.slack_team_id != resource_team_id:
            logger.error(
                "Workspace isolation violation detected",
                extra={
                    "requesting_team": requesting_user.slack_team_id,
                    "resource_team": resource_team_id,
                    "user_id": requesting_user.triage_user_id
                }
            )
            raise DataIsolationError(
                f"User from workspace {requesting_user.slack_team_id} cannot access "
                f"resource from workspace {resource_team_id}"
            )
        
        logger.debug(
            "Workspace isolation verified",
            extra={
                "team_id": requesting_user.slack_team_id,
                "user_id": requesting_user.triage_user_id
            }
        )
    
    def filter_user_data(
        self,
        requesting_user: SlackUser,
        data_items: list[Dict[str, Any]],
        user_id_field: str = "user_id"
    ) -> list[Dict[str, Any]]:
        """
        Filter a list of data items to only include those owned by requesting user.
        
        This method ensures query results only contain data belonging to the
        requesting user, preventing data leakage.
        
        Args:
            requesting_user: SlackUser making the request
            data_items: List of data items to filter
            user_id_field: Name of field containing user ID (default: "user_id")
            
        Returns:
            Filtered list containing only items owned by requesting user
            
        Validates: Requirements 8.2, 8.5
        """
        filtered = [
            item for item in data_items
            if item.get(user_id_field) == requesting_user.triage_user_id
        ]
        
        if len(filtered) < len(data_items):
            logger.warning(
                "Data items filtered for isolation",
                extra={
                    "user_id": requesting_user.triage_user_id,
                    "original_count": len(data_items),
                    "filtered_count": len(filtered),
                    "removed_count": len(data_items) - len(filtered)
                }
            )
        
        logger.debug(
            "Data filtered for user",
            extra={
                "user_id": requesting_user.triage_user_id,
                "item_count": len(filtered)
            }
        )
        
        return filtered
    
    def verify_plan_access(
        self,
        requesting_user: SlackUser,
        plan_data: Dict[str, Any]
    ) -> None:
        """
        Verify user has access to a specific plan.
        
        Args:
            requesting_user: SlackUser making the request
            plan_data: Plan data dict with user_id field
            
        Raises:
            DataIsolationError: If plan belongs to different user
            
        Validates: Requirements 8.2, 8.5
        """
        plan_user_id = plan_data.get("user_id")
        if not plan_user_id:
            logger.error(
                "Plan data missing user_id field",
                extra={"plan_id": plan_data.get("id")}
            )
            raise ValueError("Plan data must include user_id field")
        
        self.verify_user_access(
            requesting_user=requesting_user,
            resource_user_id=plan_user_id,
            resource_type="plan"
        )
    
    def verify_config_access(
        self,
        requesting_user: SlackUser,
        config_user_id: str
    ) -> None:
        """
        Verify user has access to a specific configuration.
        
        Args:
            requesting_user: SlackUser making the request
            config_user_id: User ID that owns the configuration
            
        Raises:
            DataIsolationError: If configuration belongs to different user
            
        Validates: Requirements 8.2, 8.5
        """
        self.verify_user_access(
            requesting_user=requesting_user,
            resource_user_id=config_user_id,
            resource_type="configuration"
        )
    
    def verify_task_access(
        self,
        requesting_user: SlackUser,
        task_data: Dict[str, Any]
    ) -> None:
        """
        Verify user has access to a specific task.
        
        Args:
            requesting_user: SlackUser making the request
            task_data: Task data dict with user_id field
            
        Raises:
            DataIsolationError: If task belongs to different user
            
        Validates: Requirements 8.2, 8.5
        """
        task_user_id = task_data.get("user_id")
        if not task_user_id:
            logger.error(
                "Task data missing user_id field",
                extra={"task_id": task_data.get("id")}
            )
            raise ValueError("Task data must include user_id field")
        
        self.verify_user_access(
            requesting_user=requesting_user,
            resource_user_id=task_user_id,
            resource_type="task"
        )
    
    def create_user_filter(self, requesting_user: SlackUser) -> Dict[str, str]:
        """
        Create a filter dict for database queries to enforce user isolation.
        
        This method returns a filter that should be applied to all queries
        to ensure only the requesting user's data is returned.
        
        Args:
            requesting_user: SlackUser making the request
            
        Returns:
            Dict with user_id filter
            
        Validates: Requirements 8.2, 8.5
        """
        return {"user_id": requesting_user.triage_user_id}
    
    def create_workspace_filter(self, requesting_user: SlackUser) -> Dict[str, str]:
        """
        Create a filter dict for workspace-level queries.
        
        Args:
            requesting_user: SlackUser making the request
            
        Returns:
            Dict with team_id filter
            
        Validates: Requirements 8.2, 8.5
        """
        return {"team_id": requesting_user.slack_team_id}
    
    def audit_access(
        self,
        requesting_user: SlackUser,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        success: bool = True
    ) -> None:
        """
        Log access attempt for audit trail.
        
        This method creates an audit log entry for data access attempts,
        which is useful for security monitoring and compliance.
        
        Args:
            requesting_user: SlackUser making the request
            action: Action being performed (read, write, delete, etc.)
            resource_type: Type of resource being accessed
            resource_id: Optional resource identifier
            success: Whether access was granted
            
        Validates: Requirements 8.2, 8.5
        """
        log_level = "info" if success else "warning"
        log_method = getattr(logger, log_level)
        
        log_method(
            f"Data access {'granted' if success else 'denied'}",
            extra={
                "user_id": requesting_user.triage_user_id,
                "slack_user_id": requesting_user.slack_user_id,
                "slack_team_id": requesting_user.slack_team_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "success": success
            }
        )


class QueryFilter:
    """
    Helper class for building user-isolated database queries.
    
    This class provides utilities for adding user isolation filters
    to database queries automatically.
    
    Validates: Requirements 8.2, 8.5
    """
    
    @staticmethod
    def add_user_filter(
        query_params: Dict[str, Any],
        requesting_user: SlackUser
    ) -> Dict[str, Any]:
        """
        Add user ID filter to query parameters.
        
        Args:
            query_params: Existing query parameters
            requesting_user: SlackUser making the request
            
        Returns:
            Updated query parameters with user filter
            
        Validates: Requirements 8.2, 8.5
        """
        filtered_params = query_params.copy()
        filtered_params["user_id"] = requesting_user.triage_user_id
        
        logger.debug(
            "Added user filter to query",
            extra={"user_id": requesting_user.triage_user_id}
        )
        
        return filtered_params
    
    @staticmethod
    def add_workspace_filter(
        query_params: Dict[str, Any],
        requesting_user: SlackUser
    ) -> Dict[str, Any]:
        """
        Add workspace/team ID filter to query parameters.
        
        Args:
            query_params: Existing query parameters
            requesting_user: SlackUser making the request
            
        Returns:
            Updated query parameters with workspace filter
            
        Validates: Requirements 8.2, 8.5
        """
        filtered_params = query_params.copy()
        filtered_params["team_id"] = requesting_user.slack_team_id
        
        logger.debug(
            "Added workspace filter to query",
            extra={"team_id": requesting_user.slack_team_id}
        )
        
        return filtered_params
    
    @staticmethod
    def verify_query_has_user_filter(
        query_params: Dict[str, Any],
        requesting_user: SlackUser
    ) -> bool:
        """
        Verify that query parameters include proper user isolation filter.
        
        This method checks that queries are properly filtered to prevent
        accidental data leakage.
        
        Args:
            query_params: Query parameters to verify
            requesting_user: SlackUser making the request
            
        Returns:
            True if query has proper user filter, False otherwise
            
        Validates: Requirements 8.2, 8.5
        """
        has_user_filter = (
            query_params.get("user_id") == requesting_user.triage_user_id
        )
        
        if not has_user_filter:
            logger.warning(
                "Query missing user isolation filter",
                extra={
                    "user_id": requesting_user.triage_user_id,
                    "query_params": query_params
                }
            )
        
        return has_user_filter
