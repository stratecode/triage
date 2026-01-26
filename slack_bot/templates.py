# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Message templates for Slack integration.

This module defines the MessageTemplate protocol and concrete template
implementations for daily plans, blocking tasks, and error messages.

Validates: Requirements 2.2, 5.2, 11.3
"""

from typing import Protocol, Dict, Any, List, Optional
from datetime import date
from slack_bot.models import SlackMessage
from triage.models import DailyPlan, JiraIssue, TaskClassification


class MessageTemplate(Protocol):
    """
    Protocol for message templates.
    
    All message templates must implement the render method to generate
    SlackMessage objects with Block Kit formatting.
    """
    
    def render(self, **kwargs) -> SlackMessage:
        """
        Render template with provided data.
        
        Args:
            **kwargs: Template-specific data
            
        Returns:
            SlackMessage with Block Kit blocks and fallback text
        """
        ...


class DailyPlanTemplate:
    """
    Template for daily plan messages with approval buttons.
    
    Formats a DailyPlan into a rich Slack message with:
    - Header with date
    - Priority tasks section (up to 3 tasks)
    - Administrative block section
    - Approval action buttons
    
    Validates: Requirements 2.2, 2.3, 2.4, 2.5, 9.3, 9.5
    """
    
    def __init__(self, jira_base_url: str = "https://jira.example.com"):
        """
        Initialize template with JIRA base URL.
        
        Args:
            jira_base_url: Base URL for JIRA instance (for creating links)
        """
        self.jira_base_url = jira_base_url.rstrip('/')
    
    def _format_urgency_emoji(self, urgency: str) -> str:
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
    
    def _format_effort(self, effort_days: float) -> str:
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
    
    def _create_jira_link(self, key: str) -> str:
        """
        Create clickable JIRA link.
        
        Args:
            key: JIRA issue key (e.g., PROJ-123)
            
        Returns:
            Markdown link to JIRA issue
            
        Validates: Requirements 9.3
        """
        url = f"{self.jira_base_url}/browse/{key}"
        return f"<{url}|{key}>"
    
    def _truncate_description(self, text: str, max_length: int = 200) -> str:
        """
        Truncate long descriptions with ellipsis.
        
        Args:
            text: Description text
            max_length: Maximum length before truncation
            
        Returns:
            Truncated text with ellipsis if needed
            
        Validates: Requirements 9.4
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
    
    def render(self, plan: DailyPlan, plan_id: str) -> SlackMessage:
        """
        Render daily plan as Slack message with Block Kit.
        
        Args:
            plan: DailyPlan object to render
            plan_id: Unique identifier for the plan (for approval tracking)
            
        Returns:
            SlackMessage with formatted blocks and approval buttons
            
        Validates: Requirements 2.2, 2.3, 2.4, 2.5
        """
        blocks: List[Dict[str, Any]] = []
        
        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 Your Daily Plan - {plan.date.strftime('%B %d, %Y')}"
            }
        })
        
        # Previous day closure rate (if available)
        if plan.previous_closure_rate is not None:
            percentage = int(plan.previous_closure_rate * 100)
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"Yesterday's completion rate: *{percentage}%*"
                }]
            })
        
        # Priority tasks section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🎯 Priority Tasks (Max 3)*"
            }
        })
        
        if not plan.priorities:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No priority tasks for today._"
                }
            })
        else:
            for i, classification in enumerate(plan.priorities, 1):
                task = classification.task
                urgency_emoji = self._format_urgency_emoji(task.priority)
                effort_str = self._format_effort(classification.estimated_days)
                jira_link = self._create_jira_link(task.key)
                summary = self._truncate_description(task.summary, 150)
                
                blocks.append({
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Task:* {jira_link}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Urgency:* {urgency_emoji} {task.priority}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Summary:* {summary}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Effort:* {effort_str}"
                        }
                    ]
                })
        
        # Divider
        blocks.append({"type": "divider"})
        
        # Administrative block
        if plan.admin_block.tasks:
            admin_time = plan.admin_block.time_allocation_minutes
            admin_tasks_text = "\n".join([
                f"• {self._create_jira_link(t.task.key)}: {self._truncate_description(t.task.summary, 100)}"
                for t in plan.admin_block.tasks
            ])
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📝 Administrative Block ({admin_time} min)*\n{admin_tasks_text}"
                }
            })
            
            blocks.append({"type": "divider"})
        
        # Approval buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve"
                    },
                    "style": "primary",
                    "action_id": "approve_plan",
                    "value": plan_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Reject"
                    },
                    "style": "danger",
                    "action_id": "reject_plan",
                    "value": plan_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✏️ Modify"
                    },
                    "action_id": "modify_plan",
                    "value": plan_id
                }
            ]
        })
        
        # Fallback text for notifications
        priority_count = len(plan.priorities)
        admin_count = len(plan.admin_block.tasks)
        fallback_text = (
            f"Daily Plan for {plan.date.strftime('%Y-%m-%d')}: "
            f"{priority_count} priority tasks, {admin_count} admin tasks"
        )
        
        return SlackMessage(
            blocks=blocks,
            text=fallback_text
        )


class BlockingTaskTemplate:
    """
    Template for blocking task alert notifications.
    
    Formats blocking task alerts with:
    - Alert header
    - Task details (key, summary, blocker reason, urgency)
    - Re-planning action button
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    
    def __init__(self, jira_base_url: str = "https://jira.example.com"):
        """
        Initialize template with JIRA base URL.
        
        Args:
            jira_base_url: Base URL for JIRA instance
        """
        self.jira_base_url = jira_base_url.rstrip('/')
    
    def _format_urgency_emoji(self, urgency: str) -> str:
        """Map urgency level to emoji indicator."""
        urgency_map = {
            'Blocker': '🔴',
            'High': '🔴',
            'Medium': '🟡',
            'Low': '🟢',
        }
        return urgency_map.get(urgency, '⚪')
    
    def _create_jira_link(self, key: str) -> str:
        """Create clickable JIRA link."""
        url = f"{self.jira_base_url}/browse/{key}"
        return f"<{url}|{key}>"
    
    def render(
        self,
        task: JiraIssue,
        blocker_reason: str,
        tasks: Optional[List[JiraIssue]] = None
    ) -> SlackMessage:
        """
        Render blocking task alert as Slack message.
        
        Args:
            task: Primary blocking task
            blocker_reason: Reason why task is blocking
            tasks: Optional list of additional blocking tasks for grouping
            
        Returns:
            SlackMessage with formatted alert and re-planning button
            
        Validates: Requirements 5.1, 5.2, 5.3, 5.4
        """
        blocks: List[Dict[str, Any]] = []
        
        # Determine if this is a grouped notification
        is_grouped = tasks is not None and len(tasks) > 1
        
        # Header
        if is_grouped:
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚠️ {len(tasks)} Blocking Tasks Detected"
                }
            })
        else:
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ Blocking Task Detected"
                }
            })
        
        # Primary task details
        urgency_emoji = self._format_urgency_emoji(task.priority)
        jira_link = self._create_jira_link(task.key)
        
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Task:* {jira_link}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Urgency:* {urgency_emoji} {task.priority}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Summary:* {task.summary}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Blocker:* {blocker_reason}"
                }
            ]
        })
        
        # Additional blocking tasks (if grouped)
        if is_grouped and tasks:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Additional Blocking Tasks:*"
                }
            })
            
            for other_task in tasks[1:]:  # Skip first task (already shown)
                other_link = self._create_jira_link(other_task.key)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• {other_link}: {other_task.summary}"
                    }
                })
        
        # Re-planning action button
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔄 Trigger Re-planning"
                    },
                    "style": "primary",
                    "action_id": "replan_blocking",
                    "value": task.key
                }
            ]
        })
        
        # Fallback text
        if is_grouped:
            fallback_text = f"Blocking tasks detected: {task.key} and {len(tasks) - 1} others"
        else:
            fallback_text = f"Blocking task detected: {task.key} - {task.summary}"
        
        return SlackMessage(
            blocks=blocks,
            text=fallback_text
        )


class ErrorTemplate:
    """
    Template for user-friendly error messages.
    
    Formats error messages with:
    - Error icon and title
    - Error description
    - Troubleshooting suggestions
    - Optional support contact
    
    Validates: Requirements 11.3
    """
    
    # Predefined error templates
    ERROR_TEMPLATES = {
        "api_unavailable": {
            "title": "⚠️ TrIAge Temporarily Unavailable",
            "icon": "⚠️",
            "default_suggestion": "Please try again in a few minutes. If the problem persists, contact support."
        },
        "invalid_command": {
            "title": "❌ Invalid Command",
            "icon": "❌",
            "default_suggestion": "Type `/triage help` to see available commands and usage examples."
        },
        "not_configured": {
            "title": "⚙️ Configuration Required",
            "icon": "⚙️",
            "default_suggestion": "Please configure your JIRA credentials using `/triage config`."
        },
        "rate_limited": {
            "title": "⏱️ Rate Limit Reached",
            "icon": "⏱️",
            "default_suggestion": "Too many requests. Your message will be delivered shortly. No action needed."
        },
        "unauthorized": {
            "title": "🔒 Permission Denied",
            "icon": "🔒",
            "default_suggestion": "You don't have permission to perform this action. Contact your workspace administrator."
        },
        "network_error": {
            "title": "🌐 Network Error",
            "icon": "🌐",
            "default_suggestion": "Unable to connect to TrIAge. Please check your connection and try again."
        },
        "unknown": {
            "title": "❗ Unexpected Error",
            "icon": "❗",
            "default_suggestion": "An unexpected error occurred. Please try again or contact support."
        }
    }
    
    def render(
        self,
        error_type: str,
        message: str,
        suggestion: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> SlackMessage:
        """
        Render error message as Slack message.
        
        Args:
            error_type: Type of error (api_unavailable, invalid_command, etc.)
            message: Error message to display
            suggestion: Optional custom suggestion (uses default if not provided)
            context: Optional additional context for debugging
            
        Returns:
            SlackMessage with formatted error and suggestions
            
        Validates: Requirements 11.3
        """
        blocks: List[Dict[str, Any]] = []
        
        # Get template or use unknown
        template = self.ERROR_TEMPLATES.get(error_type, self.ERROR_TEMPLATES["unknown"])
        
        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": template["title"]
            }
        })
        
        # Error message
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error:* {message}"
            }
        })
        
        # Suggestion
        suggestion_text = suggestion or template["default_suggestion"]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Suggestion:* {suggestion_text}"
            }
        })
        
        # Context (if provided and not sensitive)
        if context and not any(key in str(context).lower() for key in ['password', 'token', 'secret', 'key']):
            context_str = ", ".join([f"{k}: {v}" for k, v in context.items()])
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"_Context: {context_str}_"
                }]
            })
        
        # Fallback text
        fallback_text = f"{template['icon']} {message}"
        
        return SlackMessage(
            blocks=blocks,
            text=fallback_text
        )


class ApprovalConfirmationTemplate:
    """
    Template for approval confirmation messages.
    
    Updates the original plan message to show approval status
    and disable action buttons.
    
    Validates: Requirements 3.2, 3.5
    """
    
    def render(self, approved: bool, plan: DailyPlan) -> SlackMessage:
        """
        Render approval confirmation message.
        
        Args:
            approved: Whether plan was approved or rejected
            plan: The DailyPlan that was approved/rejected
            
        Returns:
            SlackMessage with updated status
        """
        blocks: List[Dict[str, Any]] = []
        
        if approved:
            status_text = "✅ *Plan Approved*"
            status_emoji = "✅"
        else:
            status_text = "❌ *Plan Rejected*"
            status_emoji = "❌"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": status_text
            }
        })
        
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Plan for {plan.date.strftime('%Y-%m-%d')} has been {('approved' if approved else 'rejected')}."
            }]
        })
        
        fallback_text = f"{status_emoji} Plan {('approved' if approved else 'rejected')}"
        
        return SlackMessage(
            blocks=blocks,
            text=fallback_text
        )



class BlockingTaskResolvedTemplate:
    """
    Template for blocking task resolution notifications.
    
    Formats resolution notifications with:
    - Success header
    - Task details (key, summary, urgency)
    - Resolution message
    
    Validates: Requirements 5.5
    """
    
    def __init__(self, jira_base_url: str = "https://jira.example.com"):
        """
        Initialize template with JIRA base URL.
        
        Args:
            jira_base_url: Base URL for JIRA instance
        """
        self.jira_base_url = jira_base_url.rstrip('/')
    
    def _format_urgency_emoji(self, urgency: str) -> str:
        """Map urgency level to emoji indicator."""
        urgency_map = {
            'Blocker': '🔴',
            'High': '🔴',
            'Medium': '🟡',
            'Low': '🟢',
        }
        return urgency_map.get(urgency, '⚪')
    
    def _create_jira_link(self, key: str) -> str:
        """Create clickable JIRA link."""
        url = f"{self.jira_base_url}/browse/{key}"
        return f"<{url}|{key}>"
    
    def render(self, task: JiraIssue) -> SlackMessage:
        """
        Render blocking task resolution notification as Slack message.
        
        Args:
            task: Resolved blocking task
            
        Returns:
            SlackMessage with formatted resolution notification
            
        Validates: Requirements 5.5
        """
        blocks: List[Dict[str, Any]] = []
        
        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "✅ Blocking Task Resolved"
            }
        })
        
        # Resolution message
        jira_link = self._create_jira_link(task.key)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"The blocking task *{jira_link}* has been resolved and is no longer blocking your plan."
            }
        })
        
        # Task details
        urgency_emoji = self._format_urgency_emoji(task.priority)
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Task:* {jira_link}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Urgency:* {urgency_emoji} {task.priority}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Summary:* {task.summary}"
                }
            ]
        })
        
        # Fallback text
        fallback_text = f"✅ Blocking task resolved: {task.key} - {task.summary}"
        
        return SlackMessage(
            blocks=blocks,
            text=fallback_text
        )
