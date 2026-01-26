# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Message formatter for Slack Block Kit messages.

This module provides the MessageFormatter class with helper methods for
creating common Block Kit structures and formatting TrIAge data for Slack.

Validates: Requirements 2.2
"""

from typing import Any, Dict, List, Optional
from datetime import date
from slack_bot.models import SlackMessage
from slack_bot.templates import (
    DailyPlanTemplate,
    BlockingTaskTemplate,
    ErrorTemplate,
    ApprovalConfirmationTemplate
)
from triage.models import DailyPlan, JiraIssue


class MessageFormatter:
    """
    Formats TrIAge data into Slack Block Kit messages.
    
    This class provides helper methods for creating common Block Kit
    structures and uses templates to format complex messages like
    daily plans and blocking task alerts.
    
    Validates: Requirements 2.2
    """
    
    def __init__(self, jira_base_url: str = "https://jira.example.com"):
        """
        Initialize message formatter.
        
        Args:
            jira_base_url: Base URL for JIRA instance (for creating links)
        """
        self.jira_base_url = jira_base_url.rstrip('/')
        self.daily_plan_template = DailyPlanTemplate(jira_base_url)
        self.blocking_task_template = BlockingTaskTemplate(jira_base_url)
        self.error_template = ErrorTemplate()
        self.approval_template = ApprovalConfirmationTemplate()
    
    # Helper methods for common block types
    
    def create_header_block(self, text: str) -> Dict[str, Any]:
        """
        Create a header block.
        
        Args:
            text: Header text (plain text, max 150 chars)
            
        Returns:
            Block Kit header block
        """
        return {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": text[:150]  # Slack limit
            }
        }
    
    def create_section_block(
        self,
        text: str,
        markdown: bool = True,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a section block with text or fields.
        
        Args:
            text: Section text
            markdown: Whether to use markdown formatting
            fields: Optional list of field texts (max 10)
            
        Returns:
            Block Kit section block
        """
        block: Dict[str, Any] = {
            "type": "section",
            "text": {
                "type": "mrkdwn" if markdown else "plain_text",
                "text": text
            }
        }
        
        if fields:
            block["fields"] = [
                {
                    "type": "mrkdwn",
                    "text": field
                }
                for field in fields[:10]  # Slack limit
            ]
        
        return block
    
    def create_divider_block(self) -> Dict[str, Any]:
        """
        Create a divider block.
        
        Returns:
            Block Kit divider block
        """
        return {"type": "divider"}
    
    def create_context_block(self, elements: List[str]) -> Dict[str, Any]:
        """
        Create a context block with text elements.
        
        Args:
            elements: List of text strings (max 10)
            
        Returns:
            Block Kit context block
        """
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": element
                }
                for element in elements[:10]  # Slack limit
            ]
        }
    
    def create_actions_block(
        self,
        buttons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create an actions block with buttons.
        
        Args:
            buttons: List of button elements (max 5)
            
        Returns:
            Block Kit actions block
        """
        return {
            "type": "actions",
            "elements": buttons[:5]  # Slack limit
        }
    
    def create_button_element(
        self,
        text: str,
        action_id: str,
        value: str,
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a button element.
        
        Args:
            text: Button text
            action_id: Action identifier for routing
            value: Value passed when button clicked
            style: Optional style ("primary", "danger")
            
        Returns:
            Block Kit button element
        """
        button: Dict[str, Any] = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": text
            },
            "action_id": action_id,
            "value": value
        }
        
        if style in ("primary", "danger"):
            button["style"] = style
        
        return button
    
    # Template-based formatting methods
    
    def format_daily_plan(self, plan: DailyPlan, plan_id: str) -> SlackMessage:
        """
        Format daily plan with approval buttons.
        
        Args:
            plan: DailyPlan object to format
            plan_id: Unique identifier for the plan
            
        Returns:
            SlackMessage with formatted daily plan
            
        Validates: Requirements 2.2, 2.3, 2.4, 2.5, 9.3, 9.5
        """
        return self.daily_plan_template.render(plan=plan, plan_id=plan_id)
    
    def format_blocking_task_alert(
        self,
        task: JiraIssue,
        blocker_reason: str,
        tasks: Optional[List[JiraIssue]] = None
    ) -> SlackMessage:
        """
        Format blocking task notification.
        
        Args:
            task: Primary blocking task
            blocker_reason: Reason why task is blocking
            tasks: Optional list of additional blocking tasks for grouping
            
        Returns:
            SlackMessage with formatted blocking task alert
            
        Validates: Requirements 5.1, 5.2, 5.3
        """
        return self.blocking_task_template.render(
            task=task,
            blocker_reason=blocker_reason,
            tasks=tasks
        )
    
    def format_error_message(
        self,
        error_type: str,
        message: str,
        suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> SlackMessage:
        """
        Format user-friendly error message.
        
        Args:
            error_type: Type of error (api_unavailable, invalid_command, etc.)
            message: Error message to display
            suggestion: Optional custom suggestion
            context: Optional additional context
            
        Returns:
            SlackMessage with formatted error
            
        Validates: Requirements 11.3
        """
        return self.error_template.render(
            error_type=error_type,
            message=message,
            suggestion=suggestion,
            context=context
        )
    
    def format_approval_confirmation(
        self,
        approved: bool,
        plan: DailyPlan
    ) -> SlackMessage:
        """
        Format approval confirmation message.
        
        Args:
            approved: Whether plan was approved or rejected
            plan: The DailyPlan that was approved/rejected
            
        Returns:
            SlackMessage with approval status
            
        Validates: Requirements 3.2, 3.5
        """
        return self.approval_template.render(approved=approved, plan=plan)
    
    # Utility methods
    
    def create_jira_link(self, key: str) -> str:
        """
        Create clickable JIRA link in markdown format.
        
        Args:
            key: JIRA issue key (e.g., PROJ-123)
            
        Returns:
            Markdown link to JIRA issue
            
        Validates: Requirements 9.3
        """
        url = f"{self.jira_base_url}/browse/{key}"
        return f"<{url}|{key}>"
    
    def format_urgency_emoji(self, urgency: str) -> str:
        """
        Map urgency level to emoji indicator.
        
        Args:
            urgency: Urgency level (High, Medium, Low, Blocker)
            
        Returns:
            Emoji string for urgency level
            
        Validates: Requirements 9.5
        """
        urgency_map = {
            'Blocker': '🔴',
            'High': '🔴',
            'Medium': '🟡',
            'Low': '🟢',
        }
        return urgency_map.get(urgency, '⚪')
    
    def format_effort(self, effort_days: float) -> str:
        """
        Format effort estimate in human-readable units.
        
        Args:
            effort_days: Effort in days
            
        Returns:
            Human-readable effort string
            
        Validates: Requirements 9.2
        """
        if effort_days < 0.125:  # Less than 1 hour
            hours = effort_days * 8
            return f"{hours * 60:.0f} min"
        elif effort_days < 1.0:
            hours = effort_days * 8
            return f"{hours:.1f} hours"
        else:
            return f"{effort_days:.1f} days"
    
    def truncate_text(self, text: str, max_length: int = 200) -> str:
        """
        Truncate long text with ellipsis.
        
        Args:
            text: Text to truncate
            max_length: Maximum length before truncation
            
        Returns:
            Truncated text with ellipsis if needed
            
        Validates: Requirements 9.4
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def format_blocking_task_resolved(self, task: JiraIssue) -> SlackMessage:
        """
        Format blocking task resolution notification.
        
        Args:
            task: Resolved blocking task
            
        Returns:
            SlackMessage with formatted resolution notification
            
        Validates: Requirements 5.5
        """
        blocks: List[Dict[str, Any]] = []
        
        # Header
        blocks.append(self.create_header_block("✅ Blocking Task Resolved"))
        
        # Task details
        jira_link = self.create_jira_link(task.key)
        urgency_emoji = self.format_urgency_emoji(task.priority)
        
        blocks.append(self.create_section_block(
            f"The blocking task *{jira_link}* has been resolved and is no longer blocking your plan.",
            markdown=True
        ))
        
        blocks.append(self.create_section_block(
            "",
            markdown=True,
            fields=[
                f"*Task:* {jira_link}",
                f"*Urgency:* {urgency_emoji} {task.priority}",
                f"*Summary:* {task.summary}"
            ]
        ))
        
        # Fallback text
        fallback_text = f"✅ Blocking task resolved: {task.key} - {task.summary}"
        
        return SlackMessage(
            blocks=blocks,
            text=fallback_text
        )
