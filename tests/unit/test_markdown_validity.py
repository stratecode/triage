# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Test markdown output validity."""

from datetime import date

import markdown

from triage.models import (
    AdminBlock,
    DailyPlan,
    JiraIssue,
    TaskCategory,
    TaskClassification,
)


def test_markdown_output_is_parseable():
    """Test that generated markdown can be parsed by markdown library."""
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
        previous_closure_rate=0.67,
    )

    markdown_text = plan.to_markdown()

    # Parse markdown - should not raise any exceptions
    html = markdown.markdown(markdown_text)

    # Verify HTML was generated
    assert html
    assert len(html) > 0

    # Verify key elements are present in HTML
    assert "Daily Plan" in html
    assert "PROJ-123" in html
