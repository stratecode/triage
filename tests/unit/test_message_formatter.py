# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for Slack message formatter edge cases.

Tests specific examples and edge cases for message formatting:
- Plans with 0 priority tasks
- Plans with no admin tasks
- Long description truncation
- Block Kit structure validation

Validates: Requirements 9.4
"""

import pytest
from datetime import date
from slack_bot.message_formatter import MessageFormatter
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
)


@pytest.fixture
def formatter():
    """Create a MessageFormatter instance for testing."""
    return MessageFormatter(jira_base_url="https://jira.example.com")


@pytest.fixture
def sample_issue():
    """Create a sample JIRA issue for testing."""
    return JiraIssue(
        key="PROJ-123",
        summary="Sample task summary",
        description="Sample task description",
        issue_type="Story",
        priority="High",
        status="To Do",
        assignee="user@example.com",
        story_points=5,
        time_estimate=28800,  # 8 hours
        labels=["backend", "api"],
        issue_links=[],
        custom_fields={}
    )


def test_plan_with_zero_priority_tasks(formatter):
    """
    Test formatting a plan with 0 priority tasks.
    
    The message should still be valid and indicate no priority tasks.
    
    Validates: Requirements 2.2
    """
    # Create plan with no priorities
    plan = DailyPlan(
        date=date(2026, 1, 15),
        priorities=[],  # No priority tasks
        admin_block=AdminBlock(
            tasks=[],
            time_allocation_minutes=0,
            scheduled_time="14:00-14:00"
        ),
        other_tasks=[],
        previous_closure_rate=None
    )
    
    message = formatter.format_daily_plan(plan, "plan_123")
    
    # Should have valid structure
    assert message.blocks is not None
    assert len(message.blocks) > 0
    assert message.text is not None
    
    # Should have header
    assert any(b["type"] == "header" for b in message.blocks)
    
    # Should have approval buttons
    assert any(b["type"] == "actions" for b in message.blocks)
    
    # Should indicate no priority tasks
    message_str = str(message.blocks)
    assert "No priority tasks" in message_str or "0 priority" in message.text


def test_plan_with_no_admin_tasks(formatter, sample_issue):
    """
    Test formatting a plan with no administrative tasks.
    
    The message should not include an admin block section.
    
    Validates: Requirements 2.2
    """
    # Create a priority task
    priority_classification = TaskClassification(
        task=sample_issue,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5
    )
    
    # Create plan with priorities but no admin tasks
    plan = DailyPlan(
        date=date(2026, 1, 15),
        priorities=[priority_classification],
        admin_block=AdminBlock(
            tasks=[],  # No admin tasks
            time_allocation_minutes=0,
            scheduled_time="14:00-14:00"
        ),
        other_tasks=[],
        previous_closure_rate=0.67
    )
    
    message = formatter.format_daily_plan(plan, "plan_123")
    
    # Should have valid structure
    assert message.blocks is not None
    assert len(message.blocks) > 0
    
    # Should have priority task
    message_str = str(message.blocks)
    assert "PROJ-123" in message_str
    
    # Should not have admin block section (or it should be empty)
    # Admin block section would contain "Administrative Block"
    admin_mentions = message_str.count("Administrative Block")
    # If admin block is mentioned, it should indicate 0 minutes or be absent
    if admin_mentions > 0:
        assert "0 min" in message_str or "(0 min)" in message_str


def test_long_description_truncation(formatter):
    """
    Test that long task descriptions are truncated correctly.
    
    Descriptions over 200 characters should be truncated with ellipsis.
    
    Validates: Requirements 9.4
    """
    # Create issue with very long summary
    long_summary = "A" * 300  # 300 character summary
    
    issue = JiraIssue(
        key="PROJ-456",
        summary=long_summary,
        description="Description",
        issue_type="Bug",
        priority="Medium",
        status="In Progress",
        assignee="user@example.com"
    )
    
    classification = TaskClassification(
        task=issue,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.75
    )
    
    plan = DailyPlan(
        date=date(2026, 1, 15),
        priorities=[classification],
        admin_block=AdminBlock(
            tasks=[],
            time_allocation_minutes=0,
            scheduled_time="14:00-14:00"
        ),
        other_tasks=[]
    )
    
    message = formatter.format_daily_plan(plan, "plan_456")
    
    message_str = str(message.blocks)
    
    # The full 300-character summary should not appear
    assert long_summary not in message_str
    
    # Should contain truncated version with ellipsis
    assert "..." in message_str
    
    # Verify truncation happens at reasonable length (around 150 chars for summaries)
    # The template truncates summaries to 150 chars
    truncated_summary = long_summary[:147] + "..."
    assert truncated_summary in message_str


def test_truncate_text_at_boundary(formatter):
    """
    Test text truncation at exact boundary (200 characters).
    
    Text exactly at max_length should not be truncated.
    Text at max_length + 1 should be truncated.
    
    Validates: Requirements 9.4
    """
    # Text exactly at boundary
    text_200 = "A" * 200
    truncated_200 = formatter.truncate_text(text_200, max_length=200)
    assert truncated_200 == text_200
    assert not truncated_200.endswith("...")
    
    # Text one character over boundary
    text_201 = "A" * 201
    truncated_201 = formatter.truncate_text(text_201, max_length=200)
    assert len(truncated_201) == 200
    assert truncated_201.endswith("...")
    assert truncated_201 == ("A" * 197) + "..."


def test_truncate_text_preserves_short_text(formatter):
    """
    Test that text shorter than max_length is not modified.
    
    Validates: Requirements 9.4
    """
    short_text = "This is a short text"
    truncated = formatter.truncate_text(short_text, max_length=200)
    
    assert truncated == short_text
    assert not truncated.endswith("...")


def test_block_kit_structure_validity(formatter, sample_issue):
    """
    Test that generated Block Kit structures are valid.
    
    All blocks should have required 'type' field.
    Buttons should have required fields.
    """
    classification = TaskClassification(
        task=sample_issue,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5
    )
    
    plan = DailyPlan(
        date=date(2026, 1, 15),
        priorities=[classification],
        admin_block=AdminBlock(
            tasks=[],
            time_allocation_minutes=0,
            scheduled_time="14:00-14:00"
        ),
        other_tasks=[]
    )
    
    message = formatter.format_daily_plan(plan, "plan_123")
    
    # All blocks must have 'type' field
    for block in message.blocks:
        assert "type" in block, "Every block must have a 'type' field"
        assert block["type"] in ["header", "section", "divider", "actions", "context"], \
            f"Invalid block type: {block['type']}"
    
    # Find actions block and validate buttons
    action_blocks = [b for b in message.blocks if b["type"] == "actions"]
    assert len(action_blocks) == 1, "Should have exactly one actions block"
    
    action_block = action_blocks[0]
    assert "elements" in action_block
    
    for button in action_block["elements"]:
        assert button["type"] == "button"
        assert "text" in button
        assert "action_id" in button
        assert "value" in button
        assert button["text"]["type"] == "plain_text"


def test_helper_methods(formatter):
    """Test MessageFormatter helper methods."""
    
    # Test create_header_block
    header = formatter.create_header_block("Test Header")
    assert header["type"] == "header"
    assert header["text"]["type"] == "plain_text"
    assert header["text"]["text"] == "Test Header"
    
    # Test create_section_block
    section = formatter.create_section_block("Test section text")
    assert section["type"] == "section"
    assert section["text"]["type"] == "mrkdwn"
    assert section["text"]["text"] == "Test section text"
    
    # Test create_divider_block
    divider = formatter.create_divider_block()
    assert divider["type"] == "divider"
    
    # Test create_context_block
    context = formatter.create_context_block(["Context 1", "Context 2"])
    assert context["type"] == "context"
    assert len(context["elements"]) == 2
    
    # Test create_button_element
    button = formatter.create_button_element(
        text="Click Me",
        action_id="test_action",
        value="test_value",
        style="primary"
    )
    assert button["type"] == "button"
    assert button["text"]["text"] == "Click Me"
    assert button["action_id"] == "test_action"
    assert button["value"] == "test_value"
    assert button["style"] == "primary"


def test_effort_formatting_edge_cases(formatter):
    """Test effort formatting for various edge cases."""
    
    # Very small effort (< 1 hour)
    effort_30min = formatter.format_effort(0.0625)  # 0.5 hours
    assert "min" in effort_30min
    assert "30" in effort_30min
    
    # Exactly 1 hour
    effort_1hour = formatter.format_effort(0.125)
    assert "hour" in effort_1hour
    assert "1.0" in effort_1hour
    
    # Multiple hours
    effort_4hours = formatter.format_effort(0.5)
    assert "hour" in effort_4hours
    assert "4.0" in effort_4hours
    
    # Exactly 1 day
    effort_1day = formatter.format_effort(1.0)
    assert "day" in effort_1day
    assert "1.0" in effort_1day
    
    # Multiple days
    effort_3days = formatter.format_effort(3.0)
    assert "day" in effort_3days
    assert "3.0" in effort_3days


def test_jira_link_with_different_base_urls():
    """Test JIRA link creation with different base URLs."""
    
    # Test with trailing slash
    formatter1 = MessageFormatter(jira_base_url="https://jira.example.com/")
    link1 = formatter1.create_jira_link("PROJ-123")
    assert link1 == "<https://jira.example.com/browse/PROJ-123|PROJ-123>"
    
    # Test without trailing slash
    formatter2 = MessageFormatter(jira_base_url="https://jira.example.com")
    link2 = formatter2.create_jira_link("PROJ-123")
    assert link2 == "<https://jira.example.com/browse/PROJ-123|PROJ-123>"
    
    # Both should produce same result
    assert link1 == link2


def test_error_message_formatting(formatter):
    """Test error message formatting with different error types."""
    
    # Test API unavailable error
    error_msg = formatter.format_error_message(
        error_type="api_unavailable",
        message="TrIAge API is not responding",
        suggestion="Please try again in a few minutes"
    )
    
    assert error_msg.blocks is not None
    assert len(error_msg.blocks) > 0
    assert "TrIAge API is not responding" in str(error_msg.blocks)
    assert "try again" in str(error_msg.blocks).lower()
    
    # Test invalid command error
    error_msg2 = formatter.format_error_message(
        error_type="invalid_command",
        message="Unknown command: /triage foo"
    )
    
    assert error_msg2.blocks is not None
    assert "Unknown command" in str(error_msg2.blocks)


def test_blocking_task_alert_formatting(formatter, sample_issue):
    """Test blocking task alert message formatting."""
    
    message = formatter.format_blocking_task_alert(
        task=sample_issue,
        blocker_reason="Waiting for external API approval"
    )
    
    assert message.blocks is not None
    assert len(message.blocks) > 0
    
    message_str = str(message.blocks)
    
    # Should contain task key
    assert "PROJ-123" in message_str
    
    # Should contain blocker reason
    assert "Waiting for external API approval" in message_str
    
    # Should have re-planning button
    assert any(b["type"] == "actions" for b in message.blocks)
    action_block = next(b for b in message.blocks if b["type"] == "actions")
    assert any("replan" in btn.get("action_id", "").lower() for btn in action_block["elements"])


def test_blocking_task_grouping(formatter):
    """Test blocking task alert with multiple tasks (grouping)."""
    
    task1 = JiraIssue(
        key="PROJ-123",
        summary="First blocking task",
        description="",
        issue_type="Story",
        priority="High",
        status="Blocked",
        assignee="user@example.com"
    )
    
    task2 = JiraIssue(
        key="PROJ-124",
        summary="Second blocking task",
        description="",
        issue_type="Bug",
        priority="Blocker",
        status="Blocked",
        assignee="user@example.com"
    )
    
    task3 = JiraIssue(
        key="PROJ-125",
        summary="Third blocking task",
        description="",
        issue_type="Task",
        priority="High",
        status="Blocked",
        assignee="user@example.com"
    )
    
    message = formatter.format_blocking_task_alert(
        task=task1,
        blocker_reason="External dependency",
        tasks=[task1, task2, task3]
    )
    
    message_str = str(message.blocks)
    
    # Should indicate multiple tasks
    assert "3" in message_str or "multiple" in message_str.lower()
    
    # Should contain all task keys
    assert "PROJ-123" in message_str
    assert "PROJ-124" in message_str
    assert "PROJ-125" in message_str
