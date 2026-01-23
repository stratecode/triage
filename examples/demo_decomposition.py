# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Demo script showing long-running task decomposition workflow."""

from triage.models import JiraIssue
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator
from triage.approval_manager import ApprovalManager
from triage.jira_client import JiraClient
from unittest.mock import Mock


def demo_decomposition():
    """Demonstrate the task decomposition workflow."""
    
    print("=" * 80)
    print("LONG-RUNNING TASK DECOMPOSITION DEMO")
    print("=" * 80)
    print()
    
    # Create a long-running task (5 days of work)
    long_task = JiraIssue(
        key="PROJ-456",
        summary="Implement new authentication system",
        description="Build a complete OAuth2 authentication system with JWT tokens, refresh tokens, and role-based access control.",
        issue_type="Story",
        priority="High",
        status="To Do",
        assignee="developer@example.com",
        story_points=None,
        time_estimate=5 * 8 * 60 * 60,  # 5 days in seconds
        labels=[],
        issue_links=[],
        custom_fields={},
    )
    
    print(f"Long-running task: [{long_task.key}] {long_task.summary}")
    print(f"Estimated effort: 5 days")
    print()
    
    # Create mock JIRA client
    mock_jira_client = Mock(spec=JiraClient)
    
    # Create classifier and plan generator
    classifier = TaskClassifier()
    plan_generator = PlanGenerator(mock_jira_client, classifier)
    
    # Classify the task
    classification = classifier.classify_task(long_task)
    print(f"Task classification:")
    print(f"  Category: {classification.category.value}")
    print(f"  Estimated days: {classification.estimated_days}")
    print(f"  Priority eligible: {classification.is_priority_eligible}")
    print()
    
    # Propose decomposition
    print("Proposing decomposition...")
    print()
    subtasks = plan_generator.propose_decomposition(long_task)
    
    print(f"Proposed {len(subtasks)} subtasks:")
    print()
    for i, subtask in enumerate(subtasks, 1):
        effort_hours = subtask.estimated_days * 8
        print(f"{i}. {subtask.summary}")
        print(f"   Effort: {effort_hours:.1f} hours ({subtask.estimated_days:.2f} days)")
        print(f"   Order: {subtask.order}")
        print()
    
    # Show approval workflow (without actually prompting)
    print("=" * 80)
    print("APPROVAL WORKFLOW")
    print("=" * 80)
    print()
    print("In a real scenario, the ApprovalManager would:")
    print("1. Display the decomposition proposal to the user")
    print("2. Wait for user approval (yes/no)")
    print("3. If approved, create subtasks in JIRA using JiraClient.create_subtask()")
    print("4. If rejected, collect feedback and potentially regenerate")
    print()
    
    # Create approval manager (for demonstration)
    approval_manager = ApprovalManager()
    
    print("Example approval flow:")
    print(f"  - Parent task: [{long_task.key}] {long_task.summary}")
    print(f"  - Proposed subtasks: {len(subtasks)}")
    print(f"  - User approves: Yes")
    print(f"  - System creates {len(subtasks)} subtasks in JIRA")
    print()
    
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    demo_decomposition()
