# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Interaction handler for Slack button clicks and interactive elements.

This module processes Block Kit interactive elements (buttons, select menus)
and routes them to appropriate handlers. All business logic is delegated to
the TrIAge API; this handler only translates between Slack's format and API calls.

Validates: Requirements 3.2, 3.3, 3.4, 3.5
"""

from typing import Optional, Dict, Any
import httpx

from slack_bot.models import BlockAction, SlackMessage
from slack_bot.message_formatter import MessageFormatter
from slack_bot.logging_config import get_logger


logger = get_logger(__name__)


class InteractionHandler:
    """
    Handles Slack interactive element actions (button clicks, etc.).
    
    This class provides action routing and message update functionality,
    delegating all business logic to the TrIAge API.
    
    Validates: Requirements 3.2, 3.5
    """
    
    def __init__(
        self,
        triage_api_url: str,
        triage_api_token: str,
        slack_bot_token: str,
        message_formatter: MessageFormatter
    ):
        """
        Initialize interaction handler.
        
        Args:
            triage_api_url: Base URL for TrIAge API
            triage_api_token: Bearer token for API authentication
            slack_bot_token: Slack bot token for API calls
            message_formatter: MessageFormatter instance for responses
        """
        self.triage_api_url = triage_api_url.rstrip('/')
        self.triage_api_token = triage_api_token
        self.slack_bot_token = slack_bot_token
        self.formatter = message_formatter
        
        # HTTP client for TrIAge API calls
        self.triage_client = httpx.AsyncClient(
            base_url=self.triage_api_url,
            headers={
                "Authorization": f"Bearer {self.triage_api_token}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(10.0)
        )
        
        # HTTP client for Slack API calls
        self.slack_client = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={
                "Authorization": f"Bearer {self.slack_bot_token}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(10.0)
        )
    
    async def handle_action(self, action: BlockAction) -> None:
        """
        Process button click or interactive element action.
        
        Routes action to appropriate handler based on action_id.
        
        Args:
            action: BlockAction object with action details
            
        Validates: Requirements 3.2, 3.5
        """
        logger.info(
            "Processing block action",
            extra={
                "action_id": action.action_id,
                "value": action.value,
                "user_id": action.user_id,
                "team_id": action.team_id
            }
        )
        
        try:
            # Route to appropriate handler based on action_id
            if action.action_id == "approve_plan":
                await self.handle_approve(action)
            elif action.action_id == "reject_plan":
                await self.handle_reject(action)
            elif action.action_id == "modify_plan":
                await self.handle_modify(action)
            elif action.action_id == "replan_blocking":
                await self.handle_replan_blocking(action)
            else:
                logger.warning(
                    "Unknown action_id",
                    extra={"action_id": action.action_id}
                )
        
        except Exception as e:
            logger.error(
                "Error processing action",
                extra={
                    "action_id": action.action_id,
                    "user_id": action.user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            # Send error message to user
            error_message = self.formatter.format_error_message(
                error_type="action_error",
                message="An error occurred while processing your action.",
                suggestion="Please try again or contact support if the problem persists."
            )
            await self.send_ephemeral_message(
                channel=action.channel_id or action.user_id,
                user=action.user_id,
                message=error_message
            )
    
    async def handle_approve(self, action: BlockAction) -> None:
        """
        Process plan approval button click.
        
        Calls TrIAge API approval endpoint, updates message to show
        approval status, and disables action buttons.
        
        Args:
            action: BlockAction with plan_id in value field
            
        Validates: Requirements 3.2, 3.5
        """
        plan_id = action.value
        
        logger.info(
            "Handling plan approval",
            extra={
                "plan_id": plan_id,
                "user_id": action.user_id
            }
        )
        
        try:
            # Call TrIAge API to approve plan
            response = await self.triage_client.post(
                f"/api/v1/plans/{plan_id}/approve",
                json={
                    "user_id": action.user_id,
                    "team_id": action.team_id
                }
            )
            
            if response.status_code == 200:
                # Plan approved successfully
                logger.info(
                    "Plan approved successfully",
                    extra={"plan_id": plan_id}
                )
                
                # Update message to show approval and disable buttons
                await self.update_message_with_approval_status(
                    channel=action.channel_id or action.user_id,
                    message_ts=action.message_ts,
                    approved=True,
                    user_id=action.user_id
                )
            elif response.status_code == 404:
                # Plan not found
                error_message = self.formatter.format_error_message(
                    error_type="not_found",
                    message="Plan not found.",
                    suggestion="The plan may have expired or been deleted."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
            elif response.status_code == 409:
                # Plan already approved/rejected
                error_message = self.formatter.format_error_message(
                    error_type="already_processed",
                    message="This plan has already been processed.",
                    suggestion="No further action is needed."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
            else:
                # API error
                error_message = self.formatter.format_error_message(
                    error_type="api_error",
                    message=f"Failed to approve plan (status {response.status_code}).",
                    suggestion="Please try again in a few moments."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling TrIAge API",
                extra={"error": str(e)},
                exc_info=True
            )
            error_message = self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service.",
                suggestion="Please try again in a few moments."
            )
            await self.send_ephemeral_message(
                channel=action.channel_id or action.user_id,
                user=action.user_id,
                message=error_message
            )
    
    async def handle_reject(self, action: BlockAction) -> None:
        """
        Process plan rejection button click.
        
        Creates feedback collection thread and prompts user for
        rejection reason.
        
        Args:
            action: BlockAction with plan_id in value field
            
        Validates: Requirements 3.3, 6.1
        """
        plan_id = action.value
        
        logger.info(
            "Handling plan rejection",
            extra={
                "plan_id": plan_id,
                "user_id": action.user_id
            }
        )
        
        try:
            # Call TrIAge API to reject plan
            response = await self.triage_client.post(
                f"/api/v1/plans/{plan_id}/reject",
                json={
                    "user_id": action.user_id,
                    "team_id": action.team_id
                }
            )
            
            if response.status_code == 200:
                # Plan rejected successfully
                logger.info(
                    "Plan rejected successfully",
                    extra={"plan_id": plan_id}
                )
                
                # Update message to show rejection and disable buttons
                await self.update_message_with_approval_status(
                    channel=action.channel_id or action.user_id,
                    message_ts=action.message_ts,
                    approved=False,
                    user_id=action.user_id
                )
                
                # Create feedback collection thread
                feedback_message = SlackMessage(
                    blocks=[
                        self.formatter.create_section_block(
                            "Thank you for reviewing the plan. "
                            "Please share your feedback on why you rejected it.\n\n"
                            "Your feedback helps improve future plans. "
                            "Reply to this thread with your thoughts."
                        )
                    ],
                    text="Please provide feedback on the rejected plan",
                    thread_ts=action.message_ts
                )
                
                await self.send_message(
                    channel=action.channel_id or action.user_id,
                    message=feedback_message
                )
            elif response.status_code == 404:
                # Plan not found
                error_message = self.formatter.format_error_message(
                    error_type="not_found",
                    message="Plan not found.",
                    suggestion="The plan may have expired or been deleted."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
            elif response.status_code == 409:
                # Plan already approved/rejected
                error_message = self.formatter.format_error_message(
                    error_type="already_processed",
                    message="This plan has already been processed.",
                    suggestion="No further action is needed."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
            else:
                # API error
                error_message = self.formatter.format_error_message(
                    error_type="api_error",
                    message=f"Failed to reject plan (status {response.status_code}).",
                    suggestion="Please try again in a few moments."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling TrIAge API",
                extra={"error": str(e)},
                exc_info=True
            )
            error_message = self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service.",
                suggestion="Please try again in a few moments."
            )
            await self.send_ephemeral_message(
                channel=action.channel_id or action.user_id,
                user=action.user_id,
                message=error_message
            )
    
    async def handle_modify(self, action: BlockAction) -> None:
        """
        Process plan modification button click.
        
        Provides modification instructions and guides user to
        appropriate workflow.
        
        Args:
            action: BlockAction with plan_id in value field
            
        Validates: Requirements 3.4
        """
        plan_id = action.value
        
        logger.info(
            "Handling plan modification request",
            extra={
                "plan_id": plan_id,
                "user_id": action.user_id
            }
        )
        
        # Send modification instructions as ephemeral message
        modification_message = SlackMessage(
            blocks=[
                self.formatter.create_header_block("✏️ Modify Your Plan"),
                self.formatter.create_section_block(
                    "To modify your plan, you have several options:\n\n"
                    "*1. Reject and provide feedback*\n"
                    "Click the Reject button and explain what changes you'd like. "
                    "The system will learn from your feedback.\n\n"
                    "*2. Update tasks in JIRA*\n"
                    "Make changes directly in JIRA (priorities, estimates, status). "
                    "Then generate a new plan with `/triage plan`.\n\n"
                    "*3. Manual adjustment*\n"
                    "Approve the plan and manually adjust your schedule as needed."
                ),
                self.formatter.create_context_block([
                    "💡 Tip: The more feedback you provide, the better future plans will be."
                ])
            ],
            text="Plan modification instructions"
        )
        
        await self.send_ephemeral_message(
            channel=action.channel_id or action.user_id,
            user=action.user_id,
            message=modification_message
        )
    
    async def handle_replan_blocking(self, action: BlockAction) -> None:
        """
        Process re-planning action for blocking tasks.
        
        Triggers re-planning via TrIAge API when blocking tasks are detected.
        
        Args:
            action: BlockAction with task_id or plan_id in value field
        """
        logger.info(
            "Handling re-planning for blocking task",
            extra={
                "value": action.value,
                "user_id": action.user_id
            }
        )
        
        try:
            # Call TrIAge API to trigger re-planning
            response = await self.triage_client.post(
                "/api/v1/plans/replan",
                json={
                    "user_id": action.user_id,
                    "team_id": action.team_id,
                    "reason": "blocking_task"
                }
            )
            
            if response.status_code in (200, 202):
                # Re-planning triggered successfully
                success_message = SlackMessage(
                    blocks=[
                        self.formatter.create_section_block(
                            "✅ Re-planning triggered successfully.\n\n"
                            "You'll receive an updated plan shortly."
                        )
                    ],
                    text="Re-planning triggered"
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=success_message
                )
            else:
                error_message = self.formatter.format_error_message(
                    error_type="api_error",
                    message=f"Failed to trigger re-planning (status {response.status_code}).",
                    suggestion="Please try again in a few moments."
                )
                await self.send_ephemeral_message(
                    channel=action.channel_id or action.user_id,
                    user=action.user_id,
                    message=error_message
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error calling TrIAge API",
                extra={"error": str(e)},
                exc_info=True
            )
            error_message = self.formatter.format_error_message(
                error_type="api_unavailable",
                message="Unable to connect to TrIAge service.",
                suggestion="Please try again in a few moments."
            )
            await self.send_ephemeral_message(
                channel=action.channel_id or action.user_id,
                user=action.user_id,
                message=error_message
            )
    
    async def update_message(
        self,
        channel: str,
        message_ts: str,
        new_blocks: list[Dict[str, Any]],
        new_text: str
    ) -> None:
        """
        Update existing Slack message.
        
        Args:
            channel: Channel ID or user ID for DM
            message_ts: Timestamp of message to update
            new_blocks: New Block Kit blocks
            new_text: New fallback text
            
        Validates: Requirements 3.5
        """
        logger.info(
            "Updating Slack message",
            extra={
                "channel": channel,
                "message_ts": message_ts
            }
        )
        
        try:
            response = await self.slack_client.post(
                "/chat.update",
                json={
                    "channel": channel,
                    "ts": message_ts,
                    "blocks": new_blocks,
                    "text": new_text
                }
            )
            
            response_data = response.json()
            if not response_data.get("ok"):
                logger.error(
                    "Failed to update Slack message",
                    extra={
                        "error": response_data.get("error"),
                        "channel": channel,
                        "message_ts": message_ts
                    }
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error updating Slack message",
                extra={"error": str(e)},
                exc_info=True
            )
    
    async def update_message_with_approval_status(
        self,
        channel: str,
        message_ts: str,
        approved: bool,
        user_id: str
    ) -> None:
        """
        Update message to show approval/rejection status and disable buttons.
        
        Args:
            channel: Channel ID or user ID for DM
            message_ts: Timestamp of message to update
            approved: Whether plan was approved or rejected
            user_id: User who performed the action
            
        Validates: Requirements 3.2, 3.5
        """
        status_emoji = "✅" if approved else "❌"
        status_text = "Approved" if approved else "Rejected"
        
        # Create updated blocks with disabled buttons
        updated_blocks = [
            self.formatter.create_section_block(
                f"{status_emoji} *Plan {status_text}*\n\n"
                f"This plan has been {status_text.lower()} by <@{user_id}>."
            ),
            self.formatter.create_context_block([
                f"Action taken at <!date^{int(message_ts.split('.')[0])}^{{date_short_pretty}} {{time}}|{message_ts}>"
            ])
        ]
        
        await self.update_message(
            channel=channel,
            message_ts=message_ts,
            new_blocks=updated_blocks,
            new_text=f"Plan {status_text}"
        )
    
    async def send_message(
        self,
        channel: str,
        message: SlackMessage
    ) -> Optional[str]:
        """
        Send a message to a Slack channel or user.
        
        Args:
            channel: Channel ID or user ID for DM
            message: SlackMessage to send
            
        Returns:
            Message timestamp if successful, None otherwise
        """
        logger.info(
            "Sending Slack message",
            extra={"channel": channel}
        )
        
        try:
            payload = {
                "channel": channel,
                "blocks": message.blocks,
                "text": message.text
            }
            
            if message.thread_ts:
                payload["thread_ts"] = message.thread_ts
            
            response = await self.slack_client.post(
                "/chat.postMessage",
                json=payload
            )
            
            response_data = response.json()
            if response_data.get("ok"):
                return response_data.get("ts")
            else:
                logger.error(
                    "Failed to send Slack message",
                    extra={
                        "error": response_data.get("error"),
                        "channel": channel
                    }
                )
                return None
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error sending Slack message",
                extra={"error": str(e)},
                exc_info=True
            )
            return None
    
    async def send_ephemeral_message(
        self,
        channel: str,
        user: str,
        message: SlackMessage
    ) -> None:
        """
        Send an ephemeral message (visible only to specific user).
        
        Args:
            channel: Channel ID where message appears
            user: User ID who can see the message
            message: SlackMessage to send
        """
        logger.info(
            "Sending ephemeral Slack message",
            extra={"channel": channel, "user": user}
        )
        
        try:
            response = await self.slack_client.post(
                "/chat.postEphemeral",
                json={
                    "channel": channel,
                    "user": user,
                    "blocks": message.blocks,
                    "text": message.text
                }
            )
            
            response_data = response.json()
            if not response_data.get("ok"):
                logger.error(
                    "Failed to send ephemeral message",
                    extra={
                        "error": response_data.get("error"),
                        "channel": channel,
                        "user": user
                    }
                )
        
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error sending ephemeral message",
                extra={"error": str(e)},
                exc_info=True
            )
    
    async def close(self) -> None:
        """Close HTTP clients."""
        await self.triage_client.aclose()
        await self.slack_client.aclose()
