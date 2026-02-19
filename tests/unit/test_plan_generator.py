# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for PlanGenerator."""

from datetime import date
from unittest.mock import Mock

from triage.models import JiraIssue
from triage.plan_generator import PlanGenerator
from triage.task_classifier import TaskClassifier


class TestPlanGenerator:
    """Test suite for PlanGenerator class."""

    def test_generate_daily_plan_basic(self):
        """Test basic daily plan generation."""
        # Create test tasks
        tasks = [
            JiraIssue(
                key="PROJ-1",
                summary="Quick bug fix",
                description="Fix a small bug",
                issue_type="Bug",
                priority="High",
                status="To Do",
                assignee="user@example.com",
                story_points=1,
                labels=[],
                issue_links=[],
            ),
        ]

        # Create mock JIRA client
        mock_jira_client = Mock()
        mock_jira_client.fetch_active_tasks.return_value = tasks

        # Create plan generator
        classifier = TaskClassifier()
        plan_generator = PlanGenerator(mock_jira_client, classifier)

        # Generate plan
        plan = plan_generator.generate_daily_plan()

        # Verify plan structure
        assert plan.date == date.today()
        assert len(plan.priorities) <= 3
        assert plan.admin_block.time_allocation_minutes <= 90

        # Verify PROJ-1 is in priorities (it's priority eligible)
        priority_keys = [c.task.key for c in plan.priorities]
        assert "PROJ-1" in priority_keys

    def test_generate_daily_plan_with_closure_rate(self):
        """Test daily plan generation with previous closure rate."""
        # Create mock JIRA client with no tasks
        mock_jira_client = Mock()
        mock_jira_client.fetch_active_tasks.return_value = []

        # Create plan generator
        classifier = TaskClassifier()
        plan_generator = PlanGenerator(mock_jira_client, classifier)

        # Generate plan with closure rate
        plan = plan_generator.generate_daily_plan(previous_closure_rate=0.67)

        # Verify closure rate is set
        assert plan.previous_closure_rate == 0.67

    def test_generate_daily_plan_max_priorities(self):
        """Test that plan generator respects max 3 priorities."""
        # Create 10 priority-eligible tasks
        tasks = [
            JiraIssue(
                key=f"PROJ-{i}",
                summary=f"Task {i}",
                description="A task",
                issue_type="Story",
                priority="Medium",
                status="To Do",
                assignee="user@example.com",
                story_points=1,
                labels=[],
                issue_links=[],
            )
            for i in range(10)
        ]

        # Create mock JIRA client
        mock_jira_client = Mock()
        mock_jira_client.fetch_active_tasks.return_value = tasks

        # Create plan generator
        classifier = TaskClassifier()
        plan_generator = PlanGenerator(mock_jira_client, classifier)

        # Generate plan
        plan = plan_generator.generate_daily_plan()

        # Verify max 3 priorities
        assert len(plan.priorities) <= 3

    def test_generate_daily_plan_admin_overflow(self):
        """Test that admin block respects 90-minute limit."""
        # Create many admin tasks (each ~30 minutes = 0.0625 days)
        tasks = [
            JiraIssue(
                key=f"ADMIN-{i}",
                summary=f"Admin task {i}",
                description="An admin task",
                issue_type="Administrative Task",
                priority="Low",
                status="To Do",
                assignee="user@example.com",
                story_points=None,
                time_estimate=1800,  # 30 minutes in seconds
                labels=["admin"],
                issue_links=[],
            )
            for i in range(10)
        ]

        # Create mock JIRA client
        mock_jira_client = Mock()
        mock_jira_client.fetch_active_tasks.return_value = tasks

        # Create plan generator
        classifier = TaskClassifier()
        plan_generator = PlanGenerator(mock_jira_client, classifier)

        # Generate plan
        plan = plan_generator.generate_daily_plan()

        # Verify admin block does not exceed 90 minutes
        assert plan.admin_block.time_allocation_minutes <= 90

        # Verify some tasks were deferred
        assert len(plan.admin_block.tasks) < len(tasks)
