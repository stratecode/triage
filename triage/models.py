# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Core data models for the AI Secretary system."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskCategory(Enum):
    """Task category classification."""
    PRIORITY_ELIGIBLE = "priority_eligible"
    ADMINISTRATIVE = "administrative"
    LONG_RUNNING = "long_running"
    BLOCKING = "blocking"
    DEPENDENT = "dependent"  # Has third-party dependencies


@dataclass
class IssueLink:
    """Represents a link between JIRA issues."""
    link_type: str  # e.g., "blocks", "is blocked by"
    target_key: str  # Key of linked issue
    target_summary: str  # Summary of linked issue


@dataclass
class JiraIssue:
    """Raw JIRA issue data."""
    key: str  # e.g., "PROJ-123"
    summary: str  # Task title
    description: str  # Task description
    issue_type: str  # e.g., "Story", "Bug", "Task"
    priority: str  # e.g., "High", "Blocker"
    status: str  # e.g., "To Do", "In Progress"
    assignee: str  # User email or username
    story_points: Optional[int] = None  # Story point estimate
    time_estimate: Optional[int] = None  # Time estimate in seconds
    labels: List[str] = field(default_factory=list)  # Task labels
    issue_links: List[IssueLink] = field(default_factory=list)  # Links to other issues
    custom_fields: Dict[str, Any] = field(default_factory=dict)  # Custom field values


@dataclass
class TaskClassification:
    """Classification result for a task."""
    task: JiraIssue
    category: TaskCategory  # PRIORITY_ELIGIBLE, ADMINISTRATIVE, LONG_RUNNING, BLOCKING
    is_priority_eligible: bool  # Can be a daily priority
    has_dependencies: bool  # Has third-party dependencies
    estimated_days: float  # Effort estimate in days
    blocking_reason: Optional[str] = None  # Why task is blocking (if applicable)


@dataclass
class AdminBlock:
    """Grouped administrative tasks."""
    tasks: List[TaskClassification]
    time_allocation_minutes: int  # Max 90 minutes
    scheduled_time: str  # e.g., "14:00-15:30" (post-lunch)


@dataclass
class DailyPlan:
    """A daily execution plan."""
    date: date
    priorities: List[TaskClassification]  # Max 3 tasks
    admin_block: AdminBlock
    other_tasks: List[TaskClassification]  # Non-priority tasks for reference
    previous_closure_rate: Optional[float] = None  # Previous day's closure rate
    
    def to_markdown(self) -> str:
        """Format plan as structured markdown.
        
        Returns:
            Structured markdown representation of the daily plan
        """
        lines = []
        
        # Header
        lines.append(f"# Daily Plan - {self.date.strftime('%Y-%m-%d')}")
        lines.append("")
        
        # Previous day closure rate
        if self.previous_closure_rate is not None:
            # Calculate completed/total based on closure rate
            # Assuming max 3 priorities, but could be less
            # We'll estimate based on the rate
            percentage = int(self.previous_closure_rate * 100)
            
            # For display purposes, we'll show a reasonable completed/total
            # If rate is 1.0, show 3/3; if 0.67, show 2/3; if 0.33, show 1/3; if 0.0, show 0/3
            if self.previous_closure_rate >= 0.95:
                completed, total = 3, 3
            elif self.previous_closure_rate >= 0.6:
                completed, total = 2, 3
            elif self.previous_closure_rate >= 0.3:
                completed, total = 1, 3
            else:
                completed, total = 0, 3
            
            lines.append("## Previous Day")
            lines.append(f"- Closure Rate: {completed}/{total} tasks completed ({percentage}%)")
            lines.append("")
        
        # Today's priorities
        lines.append("## Today's Priorities")
        lines.append("")
        
        if not self.priorities:
            lines.append("No priority tasks for today.")
            lines.append("")
        else:
            for i, classification in enumerate(self.priorities, 1):
                task = classification.task
                effort_hours = classification.estimated_days * 8  # Convert days to hours
                lines.append(f"{i}. **[{task.key}] {task.summary}**")
                lines.append(f"   - Effort: {effort_hours:.1f} hours")
                lines.append(f"   - Type: {task.issue_type}")
                if task.priority:
                    lines.append(f"   - Priority: {task.priority}")
                lines.append("")
        
        # Administrative block
        if self.admin_block.tasks:
            lines.append(f"## Administrative Block ({self.admin_block.scheduled_time})")
            lines.append("")
            for classification in self.admin_block.tasks:
                task = classification.task
                lines.append(f"- [ ] [{task.key}] {task.summary}")
            lines.append("")
        
        # Other active tasks
        if self.other_tasks:
            lines.append("## Other Active Tasks (For Reference)")
            lines.append("")
            for classification in self.other_tasks:
                task = classification.task
                status_note = ""
                if classification.has_dependencies:
                    status_note = " (blocked by dependencies)"
                elif classification.category == TaskCategory.LONG_RUNNING:
                    status_note = " (decomposition needed)"
                lines.append(f"- [{task.key}] {task.summary}{status_note}")
            lines.append("")
        
        return "\n".join(lines)


@dataclass
class SubtaskSpec:
    """Specification for creating a subtask."""
    summary: str
    description: str
    estimated_days: float  # Must be <= 1.0
    order: int  # Sequence order


@dataclass
class TaskCompletion:
    """Record of a completed task."""
    task_key: str  # JIRA key of completed task
    completion_date: date  # Date task was completed
    was_priority: bool  # Whether task was a priority task


@dataclass
class ClosureRecord:
    """Daily closure tracking record."""
    date: date
    total_priorities: int  # Total number of priority tasks
    completed_priorities: int  # Number of completed priority tasks
    closure_rate: float  # Completion rate (0.0-1.0)
    incomplete_tasks: List[str]  # Keys of incomplete priority tasks


@dataclass
class ApprovalResult:
    """Result of user approval interaction."""
    approved: bool
    feedback: Optional[str] = None  # User feedback if rejected
    modifications: Optional[Dict[str, Any]] = None  # User modifications to proposal
