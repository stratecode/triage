# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
TrIAge API client for Slack bot.

This module provides an async HTTP client for communicating with the TrIAge API.
All business logic remains in the TrIAge API; this client only handles HTTP
communication, authentication, and error handling.

Validates: Requirements 12.2, 4.1, 3.2, 3.3, 6.2, 10.2, 8.1, 11.2
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime, date

import httpx
from pydantic import BaseModel, Field

from slack_bot.config import SlackBotConfig


logger = logging.getLogger(__name__)


class DailyPlan(BaseModel):
    """Daily plan response from TrIAge API."""
    plan_id: str
    date: date
    priority_tasks: list[Dict[str, Any]]
    admin_tasks: list[Dict[str, Any]]
    approved: bool = False
    
    
class PlanStatus(BaseModel):
    """Plan status response from TrIAge API."""
    plan_id: str
    date: date
    approved: bool
    rejected: bool
    modified: bool
    approval_timestamp: Optional[datetime] = None


class UserConfig(BaseModel):
    """User configuration response from TrIAge API."""
    user_id: str
    notification_channel: str
    delivery_time: str
    notifications_enabled: bool
    timezone: str


class TriageAPIError(Exception):
    """Base exception for TrIAge API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class TriageAPIClient:
    """
    Async HTTP client for TrIAge API.
    
    This client handles all communication with the TrIAge backend API,
    including authentication, retry logic, and error handling.
    
    Key features:
    - HTTPS enforcement (Requirement 12.2)
    - Bearer token authentication
    - Exponential backoff retry (Requirement 11.2)
    - Comprehensive error handling
    
    Validates: Requirements 12.2, 11.2
    """
    
    def __init__(self, config: SlackBotConfig):
        """
        Initialize TrIAge API client.
        
        Args:
            config: Slack bot configuration containing API URL and token
            
        Raises:
            ValueError: If API URL does not use HTTPS
        """
        if not config.triage_api_url.startswith("https://"):
            raise ValueError("TrIAge API URL must use HTTPS (Requirement 12.2)")
        
        self.base_url = config.triage_api_url.rstrip("/")
        self.api_token = config.triage_api_token
        self.max_retries = config.max_retries
        self.retry_backoff_base = config.retry_backoff_base
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        
        # Create async HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "Initialized TrIAge API client",
            extra={
                "base_url": self.base_url,
                "max_retries": self.max_retries
            }
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_auth_headers()
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.
        
        Returns:
            Dictionary with Authorization header
        """
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "TrIAge-Slack-Bot/0.1.0"
        }
    
    def _is_retryable_error(self, status_code: int) -> bool:
        """
        Determine if an HTTP error is retryable.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            True if error should be retried
        """
        # Retry on server errors and rate limits
        return status_code in {429, 500, 502, 503, 504}
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic.
        
        Implements exponential backoff with jitter for retryable errors.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments for httpx request
            
        Returns:
            HTTP response
            
        Raises:
            TriageAPIError: If request fails after retries
            
        Validates: Requirements 11.2
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        
        # Ensure HTTPS
        if not url.startswith("https://"):
            raise ValueError(f"URL must use HTTPS: {url}")
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"Making {method} request to {endpoint}",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries + 1
                    }
                )
                
                response = await self._client.request(method, endpoint, **kwargs)
                
                # Check for errors
                if response.status_code >= 400:
                    if self._is_retryable_error(response.status_code) and attempt < self.max_retries:
                        # Calculate backoff with jitter
                        backoff = (self.retry_backoff_base ** attempt) * 0.5
                        jitter = backoff * 0.1  # 10% jitter
                        wait_time = backoff + jitter
                        
                        logger.warning(
                            f"Retryable error {response.status_code}, retrying in {wait_time:.2f}s",
                            extra={
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                                "wait_time": wait_time
                            }
                        )
                        
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Non-retryable error or max retries exceeded
                    error_body = response.text
                    logger.error(
                        f"API request failed with status {response.status_code}",
                        extra={
                            "status_code": response.status_code,
                            "endpoint": endpoint,
                            "response_body": error_body[:500]  # Truncate for logging
                        }
                    )
                    
                    raise TriageAPIError(
                        f"API request failed: {response.status_code}",
                        status_code=response.status_code,
                        response_body=error_body
                    )
                
                # Success
                logger.debug(
                    f"Request successful: {method} {endpoint}",
                    extra={"status_code": response.status_code}
                )
                return response
                
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = (self.retry_backoff_base ** attempt) * 0.5
                    logger.warning(
                        f"Request timeout, retrying in {backoff:.2f}s",
                        extra={"attempt": attempt + 1}
                    )
                    await asyncio.sleep(backoff)
                    continue
                    
            except httpx.NetworkError as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = (self.retry_backoff_base ** attempt) * 0.5
                    logger.warning(
                        f"Network error, retrying in {backoff:.2f}s",
                        extra={"attempt": attempt + 1, "error": str(e)}
                    )
                    await asyncio.sleep(backoff)
                    continue
        
        # Max retries exceeded
        logger.error(
            f"Max retries exceeded for {method} {endpoint}",
            extra={"max_retries": self.max_retries}
        )
        raise TriageAPIError(
            f"Request failed after {self.max_retries} retries: {str(last_error)}",
            status_code=None,
            response_body=None
        )

    async def generate_plan(
        self,
        user_id: str,
        plan_date: Optional[date] = None
    ) -> DailyPlan:
        """
        Trigger daily plan generation via TrIAge API.
        
        Args:
            user_id: TrIAge user ID
            plan_date: Date for plan generation (defaults to today)
            
        Returns:
            Generated daily plan
            
        Raises:
            TriageAPIError: If plan generation fails
            
        Validates: Requirements 4.1
        """
        if plan_date is None:
            plan_date = date.today()
        
        endpoint = "/api/v1/plans/generate"
        payload = {
            "user_id": user_id,
            "date": plan_date.isoformat()
        }
        
        logger.info(
            "Generating plan",
            extra={"user_id": user_id, "date": plan_date.isoformat()}
        )
        
        try:
            response = await self._make_request("POST", endpoint, json=payload)
            data = response.json()
            
            plan = DailyPlan(**data)
            logger.info(
                "Plan generated successfully",
                extra={
                    "plan_id": plan.plan_id,
                    "user_id": user_id,
                    "priority_tasks": len(plan.priority_tasks),
                    "admin_tasks": len(plan.admin_tasks)
                }
            )
            return plan
            
        except TriageAPIError as e:
            logger.error(
                "Failed to generate plan",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def approve_plan(
        self,
        plan_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Approve a daily plan.
        
        Args:
            plan_id: Plan identifier
            user_id: User approving the plan
            
        Returns:
            Approval confirmation
            
        Raises:
            TriageAPIError: If approval fails
            
        Validates: Requirements 3.2
        """
        endpoint = f"/api/v1/plans/{plan_id}/approve"
        payload = {"user_id": user_id}
        
        logger.info(
            "Approving plan",
            extra={"plan_id": plan_id, "user_id": user_id}
        )
        
        try:
            response = await self._make_request("POST", endpoint, json=payload)
            data = response.json()
            
            logger.info(
                "Plan approved successfully",
                extra={"plan_id": plan_id, "user_id": user_id}
            )
            return data
            
        except TriageAPIError as e:
            logger.error(
                "Failed to approve plan",
                extra={"plan_id": plan_id, "user_id": user_id, "error": str(e)}
            )
            raise
    
    async def reject_plan(
        self,
        plan_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reject a daily plan.
        
        Args:
            plan_id: Plan identifier
            user_id: User rejecting the plan
            reason: Optional rejection reason
            
        Returns:
            Rejection confirmation
            
        Raises:
            TriageAPIError: If rejection fails
            
        Validates: Requirements 3.3
        """
        endpoint = f"/api/v1/plans/{plan_id}/reject"
        payload = {
            "user_id": user_id,
            "reason": reason
        }
        
        logger.info(
            "Rejecting plan",
            extra={"plan_id": plan_id, "user_id": user_id, "has_reason": reason is not None}
        )
        
        try:
            response = await self._make_request("POST", endpoint, json=payload)
            data = response.json()
            
            logger.info(
                "Plan rejected successfully",
                extra={"plan_id": plan_id, "user_id": user_id}
            )
            return data
            
        except TriageAPIError as e:
            logger.error(
                "Failed to reject plan",
                extra={"plan_id": plan_id, "user_id": user_id, "error": str(e)}
            )
            raise
    
    async def submit_feedback(
        self,
        plan_id: str,
        user_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """
        Submit feedback for a rejected plan.
        
        Args:
            plan_id: Plan identifier
            user_id: User providing feedback
            feedback: Feedback text
            
        Returns:
            Feedback submission confirmation
            
        Raises:
            TriageAPIError: If feedback submission fails
            
        Validates: Requirements 6.2
        """
        endpoint = f"/api/v1/plans/{plan_id}/feedback"
        payload = {
            "user_id": user_id,
            "feedback": feedback
        }
        
        logger.info(
            "Submitting feedback",
            extra={
                "plan_id": plan_id,
                "user_id": user_id,
                "feedback_length": len(feedback)
            }
        )
        
        try:
            response = await self._make_request("POST", endpoint, json=payload)
            data = response.json()
            
            logger.info(
                "Feedback submitted successfully",
                extra={"plan_id": plan_id, "user_id": user_id}
            )
            return data
            
        except TriageAPIError as e:
            logger.error(
                "Failed to submit feedback",
                extra={"plan_id": plan_id, "user_id": user_id, "error": str(e)}
            )
            raise
    
    async def get_plan_status(
        self,
        plan_id: str,
        user_id: str
    ) -> PlanStatus:
        """
        Get status of a plan.
        
        Args:
            plan_id: Plan identifier
            user_id: User requesting status
            
        Returns:
            Plan status information
            
        Raises:
            TriageAPIError: If status retrieval fails
            
        Validates: Requirements 4.2
        """
        endpoint = f"/api/v1/plans/{plan_id}/status"
        params = {"user_id": user_id}
        
        logger.debug(
            "Getting plan status",
            extra={"plan_id": plan_id, "user_id": user_id}
        )
        
        try:
            response = await self._make_request("GET", endpoint, params=params)
            data = response.json()
            
            status = PlanStatus(**data)
            logger.debug(
                "Plan status retrieved",
                extra={
                    "plan_id": plan_id,
                    "approved": status.approved,
                    "rejected": status.rejected
                }
            )
            return status
            
        except TriageAPIError as e:
            logger.error(
                "Failed to get plan status",
                extra={"plan_id": plan_id, "user_id": user_id, "error": str(e)}
            )
            raise
    
    async def get_config(
        self,
        user_id: str
    ) -> UserConfig:
        """
        Get user configuration.
        
        Args:
            user_id: TrIAge user ID
            
        Returns:
            User configuration
            
        Raises:
            TriageAPIError: If config retrieval fails
            
        Validates: Requirements 10.2
        """
        endpoint = f"/api/v1/users/{user_id}/slack-config"
        
        logger.debug(
            "Getting user config",
            extra={"user_id": user_id}
        )
        
        try:
            response = await self._make_request("GET", endpoint)
            data = response.json()
            
            config = UserConfig(**data)
            logger.debug(
                "User config retrieved",
                extra={
                    "user_id": user_id,
                    "notifications_enabled": config.notifications_enabled
                }
            )
            return config
            
        except TriageAPIError as e:
            logger.error(
                "Failed to get user config",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def update_config(
        self,
        user_id: str,
        notification_channel: Optional[str] = None,
        delivery_time: Optional[str] = None,
        notifications_enabled: Optional[bool] = None,
        timezone: Optional[str] = None
    ) -> UserConfig:
        """
        Update user configuration.
        
        Args:
            user_id: TrIAge user ID
            notification_channel: Channel ID or "DM"
            delivery_time: Delivery time in HH:MM format
            notifications_enabled: Enable/disable notifications
            timezone: User timezone
            
        Returns:
            Updated user configuration
            
        Raises:
            TriageAPIError: If config update fails
            
        Validates: Requirements 10.2
        """
        endpoint = f"/api/v1/users/{user_id}/slack-config"
        
        # Build payload with only provided fields
        payload = {}
        if notification_channel is not None:
            payload["notification_channel"] = notification_channel
        if delivery_time is not None:
            payload["delivery_time"] = delivery_time
        if notifications_enabled is not None:
            payload["notifications_enabled"] = notifications_enabled
        if timezone is not None:
            payload["timezone"] = timezone
        
        logger.info(
            "Updating user config",
            extra={"user_id": user_id, "fields": list(payload.keys())}
        )
        
        try:
            response = await self._make_request("PUT", endpoint, json=payload)
            data = response.json()
            
            config = UserConfig(**data)
            logger.info(
                "User config updated",
                extra={"user_id": user_id}
            )
            return config
            
        except TriageAPIError as e:
            logger.error(
                "Failed to update user config",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def create_user_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str,
        jira_email: str
    ) -> Dict[str, Any]:
        """
        Create mapping between Slack user and TrIAge user.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace ID
            jira_email: User's JIRA email
            
        Returns:
            User mapping confirmation
            
        Raises:
            TriageAPIError: If mapping creation fails
            
        Validates: Requirements 8.1
        """
        endpoint = "/api/v1/users/slack-mapping"
        payload = {
            "slack_user_id": slack_user_id,
            "slack_team_id": slack_team_id,
            "jira_email": jira_email
        }
        
        logger.info(
            "Creating user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id,
                "jira_email": jira_email
            }
        )
        
        try:
            response = await self._make_request("POST", endpoint, json=payload)
            data = response.json()
            
            logger.info(
                "User mapping created",
                extra={"slack_user_id": slack_user_id}
            )
            return data
            
        except TriageAPIError as e:
            logger.error(
                "Failed to create user mapping",
                extra={"slack_user_id": slack_user_id, "error": str(e)}
            )
            raise
    
    async def get_user_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str
    ) -> Dict[str, Any]:
        """
        Get mapping between Slack user and TrIAge user.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace ID
            
        Returns:
            User mapping information
            
        Raises:
            TriageAPIError: If mapping retrieval fails
            
        Validates: Requirements 8.1
        """
        endpoint = "/api/v1/users/slack-mapping"
        params = {
            "slack_user_id": slack_user_id,
            "slack_team_id": slack_team_id
        }
        
        logger.debug(
            "Getting user mapping",
            extra={"slack_user_id": slack_user_id, "slack_team_id": slack_team_id}
        )
        
        try:
            response = await self._make_request("GET", endpoint, params=params)
            data = response.json()
            
            logger.debug(
                "User mapping retrieved",
                extra={"slack_user_id": slack_user_id}
            )
            return data
            
        except TriageAPIError as e:
            logger.error(
                "Failed to get user mapping",
                extra={"slack_user_id": slack_user_id, "error": str(e)}
            )
            raise
