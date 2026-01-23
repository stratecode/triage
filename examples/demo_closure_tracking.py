# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Demonstration of closure tracking functionality.

This script demonstrates:
1. Recording task completions
2. Calculating closure rates
3. Displaying closure rates in daily plans
"""

from datetime import date, timedelta
from unittest.mock import Mock
from triage.models import JiraIssue, TaskClassification, TaskCategory
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator


def main():
    print("=" * 80)
    print("TrIAge - Closure Tracking Demonstration")
    print("=" * 80)
    print()
    
    # Create mock JIRA client
    mock_jira_client = Mock()
    
    # Day 1: Create initial tasks
    print("Day 1: Initial Plan")
    print("-" * 80)
    
    day1_tasks = [
        JiraIssue(
            key="PROJ-101",
            summary="Implement user authentication",
            description="Add login and registration",
            issue_type="Story",
            priority="High",
            status="To Do",
            assignee="user@example.com",
            story_points=3,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-102",
            summary="Fix navigation bug",
            description="Navigation menu not working on mobile",
            issue_type="Bug",
            priority="High",
            status="To Do",
            assignee="user@example.com",
            story_points=2,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-103",
            summary="Update documentation",
            description="Update API documentation",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=1,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
    ]
    
    mock_jira_client.fetch_active_tasks.return_value = day1_tasks
    
    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)
    
    # Generate Day 1 plan (no previous closure rate)
    day1_plan = plan_generator.generate_daily_plan()
    
    print(day1_plan.to_markdown())
    print()
    
    # Simulate completing 2 out of 3 tasks
    print("End of Day 1: Completed 2 out of 3 tasks")
    print("-" * 80)
    
    # Save closure record for Day 1
    day1_date = date.today()
    day1_classifications = [classifier.classify_task(task) for task in day1_tasks]
    
    # Simulate that PROJ-101 and PROJ-102 are completed (not in active tasks anymore)
    day2_active_tasks = [day1_tasks[2]]  # Only PROJ-103 remains
    mock_jira_client.fetch_active_tasks.return_value = day2_active_tasks
    
    # Calculate and save closure record
    closure_record = plan_generator.save_closure_record(day1_date, day1_classifications[:3])
    
    print(f"Closure Rate: {closure_record.completed_priorities}/{closure_record.total_priorities} " 
          f"({int(closure_record.closure_rate * 100)}%)")
    print(f"Incomplete Tasks: {closure_record.incomplete_tasks}")
    print()
    
    # Day 2: Generate new plan with previous closure rate
    print("Day 2: New Plan with Previous Closure Rate")
    print("-" * 80)
    
    day2_tasks = [
        JiraIssue(
            key="PROJ-103",
            summary="Update documentation",
            description="Update API documentation",
            issue_type="Task",
            priority="Medium",
            status="In Progress",
            assignee="user@example.com",
            story_points=1,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-104",
            summary="Add unit tests",
            description="Add tests for authentication module",
            issue_type="Task",
            priority="High",
            status="To Do",
            assignee="user@example.com",
            story_points=2,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-105",
            summary="Optimize database queries",
            description="Improve query performance",
            issue_type="Story",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=3,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
    ]
    
    mock_jira_client.fetch_active_tasks.return_value = day2_tasks
    
    # Generate Day 2 plan (will automatically load previous closure rate)
    day2_plan = plan_generator.generate_daily_plan()
    
    print(day2_plan.to_markdown())
    print()
    
    print("=" * 80)
    print("Demonstration Complete!")
    print("=" * 80)
    print()
    print("Key Features Demonstrated:")
    print("1. Day 1 plan has no previous closure rate (first day)")
    print("2. Closure tracking records completed vs incomplete tasks")
    print("3. Day 2 plan automatically displays previous day's closure rate")
    print("4. Closure rate is calculated as: completed / total priorities")
    print()


if __name__ == "__main__":
    main()
