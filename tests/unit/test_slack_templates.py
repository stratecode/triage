# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for Slack message templates.

Tests message formatting, Block Kit structure, and template rendering.
"""

from datetime import date
import pytest
from slack_bot.templates import (
    DailyPlanTemplate,
    BlockingTaskTemplate,
    ErrorTemplate,
    ApprovalConfirmationTemplate,
)
from triage.models import (
    DailyPlan,
    TaskClassification,
    AdminBlock,
    JiraIssue,
    TaskCategory,
)


def create_test_issue(
    key: str = "PROJ-123",
    summary: str = "Test task",
    priority: str = "High",
    issue_type: str = "Story"
) -> JiraIssue:
    """Helper to create test JIRA issues."""
    return JiraIssue(
        key=key,
        summary=summary,
        description="Test description",
        issue_type=issue_type,
        priority=priority,
        status="To Do",
        assignee="test@example.com"
    )


def create_test_classification(
    issue: JiraIssue,
    estimated_days: float = 0.5,
    category: TaskCategory = TaskCategory.PRIORITY_ELIGIBLE
) -> TaskClassification:
    """Helper to create test task classifications."""
    return TaskClassification(
        task=issue,
        category=category,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=estimated_days
    )


class TestDailyPlanTemplate:
    """Tests for DailyPlanTemplate."""
    
    def test_render_plan_with_priorities(self):
        """Test rendering a plan with priority tasks."""
        # Create test data
        issue1 = create_test_issue("PROJ-1", "High priority task", "High")
        issue2 = create_test_issue("PROJ-2", "Medium priority task", "Medium")
        
        classification1 = create_test_classification(issue1, 0.5)
        classification2 = create_test_classification(issue2, 0.75)
        
        plan = DailyPlan(
            date=date(2026, 1, 15),
            priorities=[classification1, classification2],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[]
        )
        
        # Render template
        template = DailyPlanTemplate(jira_base_url="https://jira.test.com")
        message = template.render(plan, "plan_123")
        
        # Verify structure
        assert len(message.blocks) > 0
        assert message.text  # Fallback text exists
        
        # Verify header
        header_block = next((b for b in message.blocks if b["type"] == "header"), None)
        assert header_block is not None
        assert "January 15, 2026" in header_block["text"]["text"]
        
        # Verify priority tasks section
        section_blocks = [b for b in message.blocks if b["type"] == "section"]
        assert len(section_blocks) >= 2  # At least priority header + tasks
        
        # Verify action buttons
        action_block = next((b for b in message.blocks if b["type"] == "actions"), None)
        assert action_block is not None
        assert len(action_block["elements"]) == 3  # Approve, Reject, Modify
        
        # Verify button values
        approve_button = next((e for e in action_block["elements"] if e["action_id"] == "approve_plan"), None)
        assert approve_button is not None
        assert approve_button["value"] == "plan_123"
    
    def test_render_plan_with_no_priorities(self):
        """Test rendering a plan with no priority tasks."""
        plan = DailyPlan(
            date=date(2026, 1, 15),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[]
        )
        
        template = DailyPlanTemplate()
        message = template.render(plan, "plan_123")
        
        # Should still have structure
        assert len(message.blocks) > 0
        assert message.text
        
        # Should indicate no priority tasks
        text_content = str(message.blocks)
        assert "No priority tasks" in text_content or "0 priority" in message.text
    
    def test_render_plan_with_admin_block(self):
        """Test rendering a plan with administrative tasks."""
        admin_issue = create_test_issue("PROJ-100", "Admin task", "Low", "Administrative Task")
        admin_classification = create_test_classification(admin_issue, 0.25, TaskCategory.ADMINISTRATIVE)
        
        plan = DailyPlan(
            date=date(2026, 1, 15),
            priorities=[],
            admin_block=AdminBlock(
                tasks=[admin_classification],
                time_allocation_minutes=90,
                scheduled_time="14:00-15:30"
            ),
            other_tasks=[]
        )
        
        template = DailyPlanTemplate()
        message = template.render(plan, "plan_123")
        
        # Verify admin block section exists
        text_content = str(message.blocks)
        assert "Administrative Block" in text_content
        assert "90 min" in text_content
    
    def test_urgency_emoji_mapping(self):
        """Test urgency level to emoji mapping."""
        template = DailyPlanTemplate()
        
        assert template._format_urgency_emoji("Blocker") == "🔴"
        assert template._format_urgency_emoji("High") == "🔴"
        assert template._format_urgency_emoji("Medium") == "🟡"
        assert template._format_urgency_emoji("Low") == "🟢"
        assert template._format_urgency_emoji("Unknown") == "⚪"
    
    def test_effort_formatting(self):
        """Test effort estimate formatting."""
        template = DailyPlanTemplate()
        
        # Minutes
        assert "min" in template._format_effort(0.1)
        
        # Hours
        assert "hours" in template._format_effort(0.5)
        
        # Days
        assert "days" in template._format_effort(2.0)
    
    def test_jira_link_creation(self):
        """Test JIRA link formatting."""
        template = DailyPlanTemplate(jira_base_url="https://jira.test.com")
        
        link = template._create_jira_link("PROJ-123")
        assert "https://jira.test.com/browse/PROJ-123" in link
        assert "PROJ-123" in link
    
    def test_description_truncation(self):
        """Test long description truncation."""
        template = DailyPlanTemplate()
        
        short_text = "Short description"
        assert template._truncate_description(short_text, 200) == short_text
        
        long_text = "A" * 250
        truncated = template._truncate_description(long_text, 200)
        assert len(truncated) == 200
        assert truncated.endswith("...")
    
    def test_previous_closure_rate_display(self):
        """Test display of previous day's closure rate."""
        plan = DailyPlan(
            date=date(2026, 1, 15),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[],
            previous_closure_rate=0.67
        )
        
        template = DailyPlanTemplate()
        message = template.render(plan, "plan_123")
        
        # Should mention closure rate
        text_content = str(message.blocks)
        assert "67%" in text_content or "closure" in text_content.lower()


class TestBlockingTaskTemplate:
    """Tests for BlockingTaskTemplate."""
    
    def test_render_single_blocking_task(self):
        """Test rendering a single blocking task alert."""
        task = create_test_issue("PROJ-456", "Blocked task", "Blocker")
        
        template = BlockingTaskTemplate(jira_base_url="https://jira.test.com")
        message = template.render(task, "Waiting for external API")
        
        # Verify structure
        assert len(message.blocks) > 0
        assert message.text
        
        # Verify header
        header_block = next((b for b in message.blocks if b["type"] == "header"), None)
        assert header_block is not None
        assert "Blocking Task" in header_block["text"]["text"]
        
        # Verify task details
        text_content = str(message.blocks)
        assert "PROJ-456" in text_content
        assert "Waiting for external API" in text_content
        
        # Verify re-planning button
        action_block = next((b for b in message.blocks if b["type"] == "actions"), None)
        assert action_block is not None
        replan_button = next((e for e in action_block["elements"] if e["action_id"] == "replan_blocking"), None)
        assert replan_button is not None
    
    def test_render_grouped_blocking_tasks(self):
        """Test rendering multiple blocking tasks grouped together."""
        task1 = create_test_issue("PROJ-1", "First blocker", "Blocker")
        task2 = create_test_issue("PROJ-2", "Second blocker", "High")
        task3 = create_test_issue("PROJ-3", "Third blocker", "High")
        
        template = BlockingTaskTemplate()
        message = template.render(task1, "Dependency issue", tasks=[task1, task2, task3])
        
        # Verify grouped header
        header_block = next((b for b in message.blocks if b["type"] == "header"), None)
        assert header_block is not None
        assert "3 Blocking Tasks" in header_block["text"]["text"]
        
        # Verify all tasks mentioned
        text_content = str(message.blocks)
        assert "PROJ-1" in text_content
        assert "PROJ-2" in text_content
        assert "PROJ-3" in text_content


class TestErrorTemplate:
    """Tests for ErrorTemplate."""
    
    def test_render_api_unavailable_error(self):
        """Test rendering API unavailable error."""
        template = ErrorTemplate()
        message = template.render(
            "api_unavailable",
            "TrIAge API is not responding"
        )
        
        # Verify structure
        assert len(message.blocks) > 0
        assert message.text
        
        # Verify header
        header_block = next((b for b in message.blocks if b["type"] == "header"), None)
        assert header_block is not None
        assert "Unavailable" in header_block["text"]["text"]
        
        # Verify suggestion
        text_content = str(message.blocks)
        assert "try again" in text_content.lower()
    
    def test_render_invalid_command_error(self):
        """Test rendering invalid command error."""
        template = ErrorTemplate()
        message = template.render(
            "invalid_command",
            "Unknown command: /triage foo"
        )
        
        text_content = str(message.blocks)
        assert "Invalid Command" in text_content
        assert "/triage help" in text_content
    
    def test_render_with_custom_suggestion(self):
        """Test rendering error with custom suggestion."""
        template = ErrorTemplate()
        message = template.render(
            "network_error",
            "Connection timeout",
            suggestion="Check your network connection and VPN settings"
        )
        
        text_content = str(message.blocks)
        assert "VPN settings" in text_content
    
    def test_render_unknown_error_type(self):
        """Test rendering unknown error type uses default template."""
        template = ErrorTemplate()
        message = template.render(
            "some_unknown_error",
            "Something went wrong"
        )
        
        # Should still render successfully
        assert len(message.blocks) > 0
        assert message.text
    
    def test_sensitive_context_not_displayed(self):
        """Test that sensitive information in context is not displayed."""
        template = ErrorTemplate()
        message = template.render(
            "api_unavailable",
            "Authentication failed",
            context={"password": "secret123", "user": "test@example.com"}
        )
        
        # Context should not be displayed due to sensitive key
        text_content = str(message.blocks)
        assert "secret123" not in text_content


class TestApprovalConfirmationTemplate:
    """Tests for ApprovalConfirmationTemplate."""
    
    def test_render_approval_confirmation(self):
        """Test rendering approval confirmation."""
        plan = DailyPlan(
            date=date(2026, 1, 15),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[]
        )
        
        template = ApprovalConfirmationTemplate()
        message = template.render(approved=True, plan=plan)
        
        # Verify approval status
        text_content = str(message.blocks)
        assert "Approved" in text_content
        assert "✅" in text_content or "✅" in message.text
    
    def test_render_rejection_confirmation(self):
        """Test rendering rejection confirmation."""
        plan = DailyPlan(
            date=date(2026, 1, 15),
            priorities=[],
            admin_block=AdminBlock(tasks=[], time_allocation_minutes=0, scheduled_time="14:00-15:30"),
            other_tasks=[]
        )
        
        template = ApprovalConfirmationTemplate()
        message = template.render(approved=False, plan=plan)
        
        # Verify rejection status
        text_content = str(message.blocks)
        assert "Rejected" in text_content
        assert "❌" in text_content or "❌" in message.text
