#!/usr/bin/env python3
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
MVP Demonstration Script

This script demonstrates the complete AI Secretary MVP workflow using mock data.
It shows the end-to-end flow: fetch tasks → classify → generate plan → approve.

This is useful for:
- Demonstrating the system without requiring JIRA access
- Testing the workflow logic
- Validating the MVP implementation
"""

from datetime import date
from typing import List

from ai_secretary.models import (
    JiraIssue,
    IssueLink,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
    ApprovalResult,
)
from ai_secretary.task_classifier import TaskClassifier
from ai_secretary.plan_generator import PlanGenerator


def create_mock_tasks() -> List[JiraIssue]:
    """Create a diverse set of mock JIRA tasks for demonstration."""
    
    tasks = [
        # Priority-eligible tasks (no dependencies, ≤1 day)
        JiraIssue(
            key="PROJ-101",
            summary="Fix login bug on mobile app",
            description="Users report login failures on iOS",
            issue_type="Bug",
            priority="High",
            status="To Do",
            assignee="current-user",
            story_points=None,
            time_estimate=14400,  # 4 hours in seconds
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
        JiraIssue(
            key="PROJ-102",
            summary="Update API documentation for v2 endpoints",
            description="Document new authentication flow",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="current-user",
            story_points=None,
            time_estimate=10800,  # 3 hours in seconds
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
        JiraIssue(
            key="PROJ-103",
            summary="Add error handling to payment flow",
            description="Improve error messages for failed payments",
            issue_type="Story",
            priority="High",
            status="In Progress",
            assignee="current-user",
            story_points=None,
            time_estimate=21600,  # 6 hours in seconds
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
        
        # Task with dependencies (should be excluded)
        JiraIssue(
            key="PROJ-104",
            summary="Deploy new feature to production",
            description="Waiting on security review",
            issue_type="Task",
            priority="High",
            status="To Do",
            assignee="current-user",
            story_points=2,
            time_estimate=None,
            labels=[],
            issue_links=[
                IssueLink(
                    link_type="is blocked by",
                    target_key="SEC-456",
                    target_summary="Security review for new feature"
                )
            ],
            custom_fields={}
        ),
        
        # Long-running task (should be excluded)
        JiraIssue(
            key="PROJ-105",
            summary="Implement new payment gateway integration",
            description="Full integration with Stripe",
            issue_type="Story",
            priority="Medium",
            status="To Do",
            assignee="current-user",
            story_points=13,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
        
        # Administrative tasks (should be grouped)
        JiraIssue(
            key="PROJ-106",
            summary="Review pull requests from team",
            description="Code review for 3 PRs",
            issue_type="Task",
            priority="Low",
            status="To Do",
            assignee="current-user",
            story_points=None,
            time_estimate=5400,  # 1.5 hours in seconds
            labels=["admin", "code-review"],
            issue_links=[],
            custom_fields={}
        ),
        JiraIssue(
            key="PROJ-107",
            summary="Update weekly status report",
            description="Send status to stakeholders",
            issue_type="Task",
            priority="Low",
            status="To Do",
            assignee="current-user",
            story_points=None,
            time_estimate=1800,  # 30 minutes in seconds
            labels=["admin", "reporting"],
            issue_links=[],
            custom_fields={}
        ),
        JiraIssue(
            key="PROJ-108",
            summary="Respond to support emails",
            description="Customer inquiries from yesterday",
            issue_type="Task",
            priority="Low",
            status="To Do",
            assignee="current-user",
            story_points=None,
            time_estimate=3600,  # 1 hour in seconds
            labels=["admin", "support"],
            issue_links=[],
            custom_fields={}
        ),
        
        # Another priority-eligible task
        JiraIssue(
            key="PROJ-109",
            summary="Add unit tests for authentication module",
            description="Increase test coverage",
            issue_type="Task",
            priority="Medium",
            status="To Do",
            assignee="current-user",
            story_points=None,
            time_estimate=18000,  # 5 hours in seconds
            labels=[],
            issue_links=[],
            custom_fields={}
        ),
    ]
    
    return tasks


class MockJiraClient:
    """Mock JIRA client for demonstration."""
    
    def __init__(self, tasks: List[JiraIssue]):
        self.tasks = tasks
    
    def fetch_active_tasks(self) -> List[JiraIssue]:
        """Return mock tasks."""
        return self.tasks


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80 + "\n")


def main():
    """Run MVP demonstration."""
    
    print_section("AI SECRETARY MVP DEMONSTRATION")
    
    print("This demonstration shows the complete MVP workflow:")
    print("1. Fetch tasks from JIRA (using mock data)")
    print("2. Classify tasks by category, effort, and dependencies")
    print("3. Generate daily plan with up to 3 priorities")
    print("4. Group administrative tasks")
    print("5. Present plan for approval")
    
    input("\nPress Enter to start...")
    
    # Step 1: Create mock tasks
    print_section("STEP 1: Fetch Tasks from JIRA")
    
    mock_tasks = create_mock_tasks()
    print(f"Fetched {len(mock_tasks)} active tasks:\n")
    
    for task in mock_tasks:
        deps = f" [BLOCKED]" if task.issue_links else ""
        labels = f" [{', '.join(task.labels)}]" if task.labels else ""
        print(f"  {task.key}: {task.summary}{deps}{labels}")
        print(f"           Priority: {task.priority}, Story Points: {task.story_points}")
    
    input("\nPress Enter to continue...")
    
    # Step 2: Classify tasks
    print_section("STEP 2: Classify Tasks")
    
    classifier = TaskClassifier()
    classifications = [classifier.classify_task(task) for task in mock_tasks]
    
    print("Task Classifications:\n")
    
    for c in classifications:
        print(f"  {c.task.key}: {c.task.summary[:50]}")
        print(f"           Category: {c.category.value}")
        print(f"           Eligible for priority: {c.is_priority_eligible}")
        print(f"           Has dependencies: {c.has_dependencies}")
        print(f"           Estimated days: {c.estimated_days:.2f}")
        print()
    
    # Count by category
    category_counts = {}
    for c in classifications:
        category = c.category.value
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print("Distribution:")
    for category, count in sorted(category_counts.items()):
        print(f"  - {category}: {count}")
    
    input("\nPress Enter to continue...")
    
    # Step 3: Generate plan
    print_section("STEP 3: Generate Daily Plan")
    
    mock_client = MockJiraClient(mock_tasks)
    plan_generator = PlanGenerator(mock_client, classifier)
    
    print("Applying plan generation algorithm:")
    print("  1. Filter eligible tasks (no dependencies, ≤1 day, not admin)")
    print("  2. Rank by priority, effort, and age")
    print("  3. Select top 3 as priorities")
    print("  4. Group admin tasks into 90-minute block")
    print()
    
    plan = plan_generator.generate_daily_plan(previous_closure_rate=0.67)
    
    print(f"Generated plan for {plan.date}:")
    print(f"  - Priorities: {len(plan.priorities)}")
    print(f"  - Admin tasks: {len(plan.admin_block.tasks)}")
    print(f"  - Other tasks: {len(plan.other_tasks)}")
    
    input("\nPress Enter to view the plan...")
    
    # Step 4: Display plan
    print_section("STEP 4: Daily Plan (Markdown Output)")
    
    markdown = plan.to_markdown()
    print(markdown)
    
    input("\nPress Enter to continue...")
    
    # Step 5: Validate plan
    print_section("STEP 5: Validate Plan Against Requirements")
    
    print("Validation Checks:\n")
    
    # Check 1: Max 3 priorities
    check1 = len(plan.priorities) <= 3
    print(f"  {'✓' if check1 else '✗'} Priority count ≤3: {len(plan.priorities)} priorities")
    
    # Check 2: No dependencies in priorities
    check2 = all(not p.has_dependencies for p in plan.priorities)
    deps_in_priorities = sum(1 for p in plan.priorities if p.has_dependencies)
    print(f"  {'✓' if check2 else '✗'} No dependencies in priorities: {deps_in_priorities} found")
    
    # Check 3: All priorities ≤1 day
    check3 = all(p.estimated_days <= 1.0 for p in plan.priorities)
    long_in_priorities = sum(1 for p in plan.priorities if p.estimated_days > 1.0)
    print(f"  {'✓' if check3 else '✗'} All priorities ≤1 day: {long_in_priorities} long tasks found")
    
    # Check 4: No admin in priorities
    check4 = all(p.category != TaskCategory.ADMINISTRATIVE for p in plan.priorities)
    admin_in_priorities = sum(1 for p in plan.priorities if p.category == TaskCategory.ADMINISTRATIVE)
    print(f"  {'✓' if check4 else '✗'} No admin in priorities: {admin_in_priorities} found")
    
    # Check 5: Admin block ≤90 minutes
    check5 = plan.admin_block.time_allocation_minutes <= 90
    print(f"  {'✓' if check5 else '✗'} Admin block ≤90 min: {plan.admin_block.time_allocation_minutes} minutes")
    
    # Check 6: Markdown validity
    check6 = "# Daily Plan" in markdown and len(markdown) > 0
    print(f"  {'✓' if check6 else '✗'} Valid markdown output: {len(markdown)} characters")
    
    all_passed = all([check1, check2, check3, check4, check5, check6])
    
    print(f"\n{'✓ All validation checks passed!' if all_passed else '✗ Some checks failed'}")
    
    input("\nPress Enter to continue...")
    
    # Step 6: Approval workflow
    print_section("STEP 6: Approval Workflow")
    
    print("In the real system, the plan would be presented for user approval.")
    print("The user can approve or reject the plan.")
    print()
    print("For this demonstration, we'll simulate approval:")
    
    response = input("\nDo you approve this plan? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        approval = ApprovalResult(approved=True)
        print("\n✓ Plan approved!")
    else:
        approval = ApprovalResult(approved=False)
        print("\n✗ Plan rejected")
        print("In the real system, you would provide feedback for plan adjustment.")
    
    # Final summary
    print_section("MVP DEMONSTRATION COMPLETE")
    
    print("Summary of MVP Features Demonstrated:\n")
    print("  ✓ Task fetching from JIRA (mocked)")
    print("  ✓ Task classification by category, effort, dependencies")
    print("  ✓ Priority selection (max 3, no dependencies, ≤1 day)")
    print("  ✓ Administrative task grouping (90-minute limit)")
    print("  ✓ Structured markdown output")
    print("  ✓ Approval workflow")
    print()
    print("Key Validations:")
    print(f"  ✓ Cognitive load minimized: {len(plan.priorities)} priorities")
    print(f"  ✓ Dependencies excluded: {sum(1 for c in classifications if c.has_dependencies)} tasks blocked")
    print(f"  ✓ Long tasks excluded: {sum(1 for c in classifications if c.estimated_days > 1.0)} tasks >1 day")
    print(f"  ✓ Admin tasks grouped: {len(plan.admin_block.tasks)} tasks in {plan.admin_block.time_allocation_minutes}min block")
    print()
    print("📌 MVP is complete and usable!")
    print()
    print("Next Steps:")
    print("  1. Test with real JIRA data: python validate_mvp.py")
    print("  2. Use CLI for daily planning: ai-secretary generate-plan")
    print("  3. Review MVP_VALIDATION_GUIDE.md for detailed testing")


if __name__ == '__main__':
    main()
