# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Demo script showing the re-planning flow when a blocking task is detected.

This demonstrates:
1. Generating an initial daily plan
2. Detecting a blocking task
3. Triggering re-planning with the blocking task
4. Presenting the new plan for approval
"""

from datetime import date
from triage.models import JiraIssue, IssueLink
from triage.jira_client import JiraClient
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator
from triage.approval_manager import ApprovalManager


def create_sample_tasks():
    """Create sample tasks for demonstration."""
    return [
        JiraIssue(
            key="PROJ-101",
            summary="Implement user authentication",
            description="Add JWT-based authentication to the API",
            issue_type="Story",
            priority="High",
            status="To Do",
            assignee="user@example.com",
            story_points=3,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-102",
            summary="Fix login page styling",
            description="Update CSS for login page",
            issue_type="Bug",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=1,
            labels=[],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-103",
            summary="Write API documentation",
            description="Document all API endpoints",
            issue_type="Task",
            priority="Low",
            status="To Do",
            assignee="user@example.com",
            story_points=2,
            labels=["admin", "documentation"],
            issue_links=[],
            custom_fields={},
        ),
        JiraIssue(
            key="PROJ-104",
            summary="Review pull requests",
            description="Review pending PRs",
            issue_type="Task",
            priority="Low",
            status="To Do",
            assignee="user@example.com",
            story_points=1,
            labels=["admin"],
            issue_links=[],
            custom_fields={},
        ),
    ]


def create_blocking_task():
    """Create a blocking task that triggers re-planning."""
    return JiraIssue(
        key="PROJ-999",
        summary="CRITICAL: Production database connection failing",
        description="Production database is unreachable. All services are down. Immediate fix required.",
        issue_type="Bug",
        priority="Blocker",
        status="To Do",
        assignee="user@example.com",
        story_points=1,
        labels=["production", "critical"],
        issue_links=[],
        custom_fields={},
    )


def main():
    """Run the re-planning demo."""
    print("=" * 80)
    print("RE-PLANNING FLOW DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Create mock JIRA client with sample tasks
    from unittest.mock import Mock
    mock_jira_client = Mock(spec=JiraClient)
    
    # Initial tasks (no blocking tasks)
    initial_tasks = create_sample_tasks()
    mock_jira_client.fetch_active_tasks.return_value = initial_tasks
    
    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)
    
    # Step 1: Generate initial daily plan
    print("STEP 1: Generating initial daily plan...")
    print()
    initial_plan = plan_generator.generate_daily_plan()
    
    print("Initial Plan:")
    print("-" * 80)
    print(initial_plan.to_markdown())
    print()
    
    # Step 2: Simulate blocking task detection
    print("=" * 80)
    print("STEP 2: Blocking task detected!")
    print("=" * 80)
    print()
    
    blocking_task = create_blocking_task()
    print(f"Blocking Task: [{blocking_task.key}] {blocking_task.summary}")
    print(f"Priority: {blocking_task.priority}")
    print(f"Description: {blocking_task.description}")
    print()
    
    # Update mock to include blocking task
    all_tasks = initial_tasks + [blocking_task]
    mock_jira_client.fetch_active_tasks.return_value = all_tasks
    
    # Step 3: Generate re-plan
    print("STEP 3: Generating new plan with blocking task...")
    print()
    
    new_plan = plan_generator.generate_replan(blocking_task, initial_plan)
    
    print("New Plan (with blocking task):")
    print("-" * 80)
    print(new_plan.to_markdown())
    print()
    
    # Step 4: Show what changed
    print("=" * 80)
    print("STEP 4: Plan Comparison")
    print("=" * 80)
    print()
    
    print("Initial Priorities:")
    for i, classification in enumerate(initial_plan.priorities, 1):
        print(f"  {i}. [{classification.task.key}] {classification.task.summary}")
    print()
    
    print("New Priorities (after re-planning):")
    for i, classification in enumerate(new_plan.priorities, 1):
        marker = " ← BLOCKING TASK" if classification.task.key == blocking_task.key else ""
        print(f"  {i}. [{classification.task.key}] {classification.task.summary}{marker}")
    print()
    
    # Step 5: Demonstrate approval flow
    print("=" * 80)
    print("STEP 5: Approval Flow")
    print("=" * 80)
    print()
    print("In a real scenario, the ApprovalManager would present this plan to the user")
    print("and wait for approval before replacing the current plan.")
    print()
    print("The user would see:")
    print("  - A notification about the blocking task")
    print("  - The current plan being interrupted")
    print("  - The new proposed plan")
    print("  - A prompt to approve or reject the change")
    print()
    
    # Show what the approval manager would display
    print("Example approval prompt:")
    print("-" * 80)
    approval_manager = ApprovalManager()
    print("⚠️  BLOCKING TASK DETECTED - PLAN INTERRUPTION")
    print()
    print(f"Task: [{blocking_task.key}] {blocking_task.summary}")
    print(f"Priority: {blocking_task.priority}")
    print()
    print("Your current plan will be interrupted and replaced with a new plan")
    print("that includes this blocking task as a priority.")
    print()
    print("Do you approve this plan replacement? (yes/no)")
    print()
    
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("Key Features Demonstrated:")
    print("  ✓ Initial plan generation with 3 priorities")
    print("  ✓ Blocking task detection")
    print("  ✓ Re-planning flow triggered by blocking task")
    print("  ✓ Blocking task included as first priority in new plan")
    print("  ✓ Plan respects max 3 priorities constraint")
    print("  ✓ Approval workflow for plan replacement")
    print()


if __name__ == "__main__":
    main()
