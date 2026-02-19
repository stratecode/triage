# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for core data models."""

from datetime import date

from triage.models import (
    AdminBlock,
    ApprovalResult,
    DailyPlan,
    IssueLink,
    JiraIssue,
    SubtaskSpec,
    TaskCategory,
    TaskClassification,
)


def test_jira_issue_creation():
    """Test JiraIssue can be created with required fields."""
    issue = JiraIssue(
        key="PROJ-123",
        summary="Test task",
        description="Test description",
        issue_type="Story",
        priority="High",
        status="To Do",
        assignee="user@example.com",
    )
    assert issue.key == "PROJ-123"
    assert issue.summary == "Test task"
    assert issue.labels == []
    assert issue.issue_links == []


def test_issue_link_creation():
    """Test IssueLink can be created."""
    link = IssueLink(
        link_type="blocks",
        target_key="PROJ-124",
        target_summary="Blocked task",
    )
    assert link.link_type == "blocks"
    assert link.target_key == "PROJ-124"


def test_task_classification_creation():
    """Test TaskClassification can be created."""
    issue = JiraIssue(
        key="PROJ-123",
        summary="Test task",
        description="Test description",
        issue_type="Story",
        priority="High",
        status="To Do",
        assignee="user@example.com",
    )
    classification = TaskClassification(
        task=issue,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5,
    )
    assert classification.category == TaskCategory.PRIORITY_ELIGIBLE
    assert classification.is_priority_eligible is True
    assert classification.estimated_days == 0.5


def test_daily_plan_to_markdown_basic():
    """Test DailyPlan.to_markdown() generates valid markdown."""
    issue = JiraIssue(
        key="PROJ-123",
        summary="Implement feature X",
        description="Test description",
        issue_type="Story",
        priority="High",
        status="To Do",
        assignee="user@example.com",
    )
    classification = TaskClassification(
        task=issue,
        category=TaskCategory.PRIORITY_ELIGIBLE,
        is_priority_eligible=True,
        has_dependencies=False,
        estimated_days=0.5,
    )

    admin_block = AdminBlock(
        tasks=[],
        time_allocation_minutes=0,
        scheduled_time="14:00-15:30",
    )

    plan = DailyPlan(
        date=date(2026, 1, 23),
        priorities=[classification],
        admin_block=admin_block,
        other_tasks=[],
    )

    markdown = plan.to_markdown()

    # Verify markdown structure
    assert "# Daily Plan - 2026-01-23" in markdown
    assert "## Today's Priorities" in markdown
    assert "[PROJ-123] Implement feature X" in markdown
    assert "Effort: 4.0 hours" in markdown
    assert "Type: Story" in markdown


def test_daily_plan_to_markdown_with_closure_rate():
    """Test DailyPlan.to_markdown() includes previous closure rate."""
    admin_block = AdminBlock(
        tasks=[],
        time_allocation_minutes=0,
        scheduled_time="14:00-15:30",
    )

    plan = DailyPlan(
        date=date(2026, 1, 23),
        priorities=[],
        admin_block=admin_block,
        other_tasks=[],
        previous_closure_rate=0.67,
    )

    markdown = plan.to_markdown()

    assert "## Previous Day" in markdown
    assert "Closure Rate: 2/3 tasks completed (67%)" in markdown


def test_daily_plan_to_markdown_with_admin_tasks():
    """Test DailyPlan.to_markdown() includes administrative block."""
    admin_issue = JiraIssue(
        key="PROJ-200",
        summary="Review emails",
        description="Admin task",
        issue_type="Task",
        priority="Low",
        status="To Do",
        assignee="user@example.com",
    )
    admin_classification = TaskClassification(
        task=admin_issue,
        category=TaskCategory.ADMINISTRATIVE,
        is_priority_eligible=False,
        has_dependencies=False,
        estimated_days=0.25,
    )

    admin_block = AdminBlock(
        tasks=[admin_classification],
        time_allocation_minutes=60,
        scheduled_time="14:00-15:00",
    )

    plan = DailyPlan(
        date=date(2026, 1, 23),
        priorities=[],
        admin_block=admin_block,
        other_tasks=[],
    )

    markdown = plan.to_markdown()

    assert "## Administrative Block (14:00-15:00)" in markdown
    assert "[PROJ-200] Review emails" in markdown


def test_daily_plan_to_markdown_with_other_tasks():
    """Test DailyPlan.to_markdown() includes other tasks with status notes."""
    blocked_issue = JiraIssue(
        key="PROJ-300",
        summary="Blocked task",
        description="Waiting on external team",
        issue_type="Story",
        priority="Medium",
        status="Blocked",
        assignee="user@example.com",
    )
    blocked_classification = TaskClassification(
        task=blocked_issue,
        category=TaskCategory.DEPENDENT,
        is_priority_eligible=False,
        has_dependencies=True,
        estimated_days=2.0,
    )

    long_issue = JiraIssue(
        key="PROJ-400",
        summary="Long running task",
        description="Multi-day work",
        issue_type="Epic",
        priority="High",
        status="To Do",
        assignee="user@example.com",
        story_points=5,
    )
    long_classification = TaskClassification(
        task=long_issue,
        category=TaskCategory.LONG_RUNNING,
        is_priority_eligible=False,
        has_dependencies=False,
        estimated_days=2.5,
    )

    admin_block = AdminBlock(
        tasks=[],
        time_allocation_minutes=0,
        scheduled_time="14:00-15:30",
    )

    plan = DailyPlan(
        date=date(2026, 1, 23),
        priorities=[],
        admin_block=admin_block,
        other_tasks=[blocked_classification],
        decomposition_suggestions=[long_classification],
    )

    markdown = plan.to_markdown()

    # Check decomposition suggestions section
    assert "## ⚠️ Tasks Requiring Decomposition" in markdown
    assert "[PROJ-400] Long running task" in markdown
    assert "Current estimate: 2.5 days" in markdown
    assert "Story points: 5 SP" in markdown
    assert "Break into 3 daily-closable subtasks" in markdown
    assert "triage decompose PROJ-400" in markdown

    # Check other tasks section
    assert "## Other Active Tasks (For Reference)" in markdown
    assert "[PROJ-300] Blocked task (blocked by dependencies)" in markdown


def test_subtask_spec_creation():
    """Test SubtaskSpec can be created."""
    subtask = SubtaskSpec(
        summary="Subtask 1",
        description="First subtask",
        estimated_days=0.5,
        order=1,
    )
    assert subtask.summary == "Subtask 1"
    assert subtask.estimated_days == 0.5
    assert subtask.order == 1


def test_approval_result_creation():
    """Test ApprovalResult can be created."""
    result = ApprovalResult(
        approved=True,
    )
    assert result.approved is True
    assert result.feedback is None

    result_with_feedback = ApprovalResult(
        approved=False,
        feedback="Need more time",
    )
    assert result_with_feedback.approved is False
    assert result_with_feedback.feedback == "Need more time"
