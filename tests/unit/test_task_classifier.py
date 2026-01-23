# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Unit tests for TaskClassifier."""

import pytest
from ai_secretary.models import JiraIssue, IssueLink, TaskCategory
from ai_secretary.task_classifier import TaskClassifier


class TestTaskClassifier:
    """Test suite for TaskClassifier."""
    
    def test_classify_simple_task(self):
        """Test classification of a simple task with no special attributes."""
        issue = JiraIssue(
            key="PROJ-123",
            summary="Simple task",
            description="A simple task",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=1,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        classification = classifier.classify_task(issue)
        
        assert classification.task is issue
        assert classification.category == TaskCategory.PRIORITY_ELIGIBLE
        assert classification.is_priority_eligible is True
        assert classification.has_dependencies is False
        # 1 story point * 1.25 = 1.25, rounded to nearest 0.5 = 1.0 (but min is 1.0)
        assert classification.estimated_days == 1.0
    
    def test_classify_task_with_blocking_link(self):
        """Test classification of a task with blocking dependencies."""
        issue = JiraIssue(
            key="PROJ-124",
            summary="Blocked task",
            description="A blocked task",
            issue_type="Task",
            priority="High",
            status="To Do",
            assignee="user@example.com",
            story_points=1,
            time_estimate=None,
            labels=[],
            issue_links=[
                IssueLink(
                    link_type="is blocked by",
                    target_key="PROJ-100",
                    target_summary="Blocking task"
                )
            ],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        classification = classifier.classify_task(issue)
        
        assert classification.category == TaskCategory.DEPENDENT
        assert classification.is_priority_eligible is False
        assert classification.has_dependencies is True
    
    def test_classify_administrative_task_by_label(self):
        """Test classification of administrative task by label."""
        issue = JiraIssue(
            key="PROJ-125",
            summary="Send weekly report",
            description="Weekly status report",
            issue_type="Task",
            priority="Low",
            status="To Do",
            assignee="user@example.com",
            story_points=None,
            time_estimate=3600,  # 1 hour
            labels=["report", "weekly"],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        classification = classifier.classify_task(issue)
        
        assert classification.category == TaskCategory.ADMINISTRATIVE
        assert classification.is_priority_eligible is False
        assert classifier.is_administrative(issue) is True
    
    def test_classify_administrative_task_by_type(self):
        """Test classification of administrative task by issue type."""
        issue = JiraIssue(
            key="PROJ-126",
            summary="Approve PR",
            description="Code review approval",
            issue_type="Approval",
            priority="Low",
            status="To Do",
            assignee="user@example.com",
            story_points=None,
            time_estimate=1800,  # 30 minutes
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        classification = classifier.classify_task(issue)
        
        assert classification.category == TaskCategory.ADMINISTRATIVE
        assert classification.is_priority_eligible is False
        assert classifier.is_administrative(issue) is True
    
    def test_classify_long_running_task(self):
        """Test classification of long-running task."""
        issue = JiraIssue(
            key="PROJ-127",
            summary="Large feature",
            description="Multi-day feature",
            issue_type="Story",
            priority="High",
            status="To Do",
            assignee="user@example.com",
            story_points=5,  # 5 * 1.25 = 6.25 days
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        classification = classifier.classify_task(issue)
        
        assert classification.category == TaskCategory.LONG_RUNNING
        assert classification.is_priority_eligible is False
        assert classification.estimated_days > 1.0
    
    def test_classify_blocking_task(self):
        """Test classification of blocking priority task."""
        issue = JiraIssue(
            key="PROJ-128",
            summary="Production outage",
            description="Critical production issue",
            issue_type="Bug",
            priority="Blocker",
            status="To Do",
            assignee="user@example.com",
            story_points=None,
            time_estimate=14400,  # 4 hours
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        classification = classifier.classify_task(issue)
        
        assert classification.category == TaskCategory.BLOCKING
        assert classification.is_priority_eligible is False
        assert classification.blocking_reason is not None
    
    def test_has_third_party_dependencies_with_custom_field(self):
        """Test dependency detection via custom fields."""
        issue = JiraIssue(
            key="PROJ-129",
            summary="Task with external dependency",
            description="Depends on external team",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=1,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={
                "external_dependency": "Waiting on Team X"
            }
        )
        
        classifier = TaskClassifier()
        assert classifier.has_third_party_dependencies(issue) is True
    
    def test_estimate_effort_days_with_story_points(self):
        """Test effort estimation using story points."""
        issue = JiraIssue(
            key="PROJ-130",
            summary="Task with story points",
            description="Task",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=2,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        estimated_days = classifier.estimate_effort_days(issue)
        
        # 2 story points * 1.25 = 2.5 days, rounded to nearest 0.5 = 2.5
        assert estimated_days == 2.5
    
    def test_estimate_effort_days_with_time_estimate(self):
        """Test effort estimation using time estimate."""
        issue = JiraIssue(
            key="PROJ-131",
            summary="Task with time estimate",
            description="Task",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=None,
            time_estimate=14400,  # 4 hours = 0.5 days
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        estimated_days = classifier.estimate_effort_days(issue)
        
        # 4 hours = 0.5 days, but conservative default is 1.0
        assert estimated_days == 1.0
    
    def test_estimate_effort_days_default(self):
        """Test effort estimation with no estimates (conservative default)."""
        issue = JiraIssue(
            key="PROJ-132",
            summary="Task without estimates",
            description="Task",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=None,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={}
        )
        
        classifier = TaskClassifier()
        estimated_days = classifier.estimate_effort_days(issue)
        
        # Conservative default is 1.0 day
        assert estimated_days == 1.0
