# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Demo script showing logging functionality in TrIAge.

This script demonstrates:
1. Configuring logging at different levels
2. Logging output from various components
3. Writing logs to files
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from triage import configure_logging
from triage.models import JiraIssue, IssueLink
from triage.task_classifier import TaskClassifier


def demo_basic_logging():
    """Demonstrate basic logging at INFO level."""
    print("=" * 80)
    print("DEMO 1: Basic Logging (INFO level)")
    print("=" * 80)
    print()
    
    # Configure logging at INFO level
    configure_logging(level=logging.INFO)
    
    # Create a classifier and classify a task
    classifier = TaskClassifier()
    
    # Create a sample task
    task = JiraIssue(
        key="DEMO-1",
        summary="Implement user authentication",
        description="Add OAuth2 authentication to the API",
        issue_type="Story",
        priority="High",
        status="To Do",
        assignee="user@example.com",
        story_points=5,
        labels=["backend", "security"]
    )
    
    print("Classifying task DEMO-1...")
    classification = classifier.classify_task(task)
    
    print(f"\nResult: {classification.category.value}")
    print(f"Priority eligible: {classification.is_priority_eligible}")
    print(f"Estimated days: {classification.estimated_days}")
    print()


def demo_debug_logging():
    """Demonstrate debug logging with detailed output."""
    print("=" * 80)
    print("DEMO 2: Debug Logging (DEBUG level)")
    print("=" * 80)
    print()
    
    # Configure logging at DEBUG level
    configure_logging(level=logging.DEBUG)
    
    # Create a classifier and classify a task
    classifier = TaskClassifier()
    
    # Create a task with dependencies
    task = JiraIssue(
        key="DEMO-2",
        summary="Update API documentation",
        description="Update docs after API changes",
        issue_type="Task",
        priority="Medium",
        status="To Do",
        assignee="user@example.com",
        time_estimate=14400,  # 4 hours in seconds
        labels=["documentation"],
        issue_links=[
            IssueLink(
                link_type="is blocked by",
                target_key="DEMO-1",
                target_summary="Implement user authentication"
            )
        ]
    )
    
    print("Classifying task DEMO-2 with dependencies...")
    classification = classifier.classify_task(task)
    
    print(f"\nResult: {classification.category.value}")
    print(f"Has dependencies: {classification.has_dependencies}")
    print(f"Priority eligible: {classification.is_priority_eligible}")
    print()


def demo_file_logging():
    """Demonstrate logging to a file."""
    print("=" * 80)
    print("DEMO 3: File Logging")
    print("=" * 80)
    print()
    
    # Create a log file path
    log_file = Path(__file__).parent / "triage_demo.log"
    
    # Configure logging to file
    configure_logging(level=logging.DEBUG, log_file=str(log_file))
    
    print(f"Logging to file: {log_file}")
    print()
    
    # Create a classifier and classify multiple tasks
    classifier = TaskClassifier()
    
    tasks = [
        JiraIssue(
            key="DEMO-3",
            summary="Fix login bug",
            description="Users can't log in with special characters",
            issue_type="Bug",
            priority="Blocker",
            status="To Do",
            assignee="user@example.com",
            story_points=2
        ),
        JiraIssue(
            key="DEMO-4",
            summary="Weekly team meeting",
            description="Discuss sprint progress",
            issue_type="Administrative Task",
            priority="Low",
            status="To Do",
            assignee="user@example.com",
            time_estimate=3600,  # 1 hour
            labels=["admin", "meeting"]
        ),
        JiraIssue(
            key="DEMO-5",
            summary="Refactor database layer",
            description="Improve performance and maintainability",
            issue_type="Story",
            priority="Medium",
            status="To Do",
            assignee="user@example.com",
            story_points=13  # Long-running task
        )
    ]
    
    print("Classifying 3 tasks...")
    for task in tasks:
        classification = classifier.classify_task(task)
        print(f"  {task.key}: {classification.category.value}")
    
    print()
    print(f"✓ Detailed logs written to: {log_file}")
    print(f"  View with: cat {log_file}")
    print()


def main():
    """Run all logging demos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TrIAge Logging Demo" + " " * 39 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    try:
        demo_basic_logging()
        input("Press Enter to continue to next demo...")
        print()
        
        demo_debug_logging()
        input("Press Enter to continue to next demo...")
        print()
        
        demo_file_logging()
        
        print("=" * 80)
        print("All demos completed!")
        print("=" * 80)
        print()
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
