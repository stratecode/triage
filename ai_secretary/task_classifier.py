# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Task classification logic for categorizing and analyzing JIRA tasks."""

from typing import List, Set

from ai_secretary.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
)


class TaskClassifier:
    """
    Classifies tasks based on metadata and determines eligibility for priority status.
    """
    
    # Administrative task indicators
    ADMIN_LABELS = {'admin', 'administrative', 'email', 'report', 'approval', 'meeting', 'review'}
    ADMIN_ISSUE_TYPES = {'Administrative Task', 'Admin', 'Approval', 'Review'}
    
    # Dependency link types that indicate third-party blocking
    BLOCKING_LINK_TYPES = {'is blocked by', 'depends on', 'blocked by'}
    
    # Story points to days conversion (assuming 8 story points = 1 sprint = 2 weeks = 10 days)
    # Conservative estimate: 1 story point = ~1.25 days
    STORY_POINTS_TO_DAYS = 1.25
    
    # Seconds in a working day (8 hours)
    SECONDS_PER_DAY = 8 * 60 * 60
    
    def classify_task(self, issue: JiraIssue) -> TaskClassification:
        """
        Classify a single task.
        
        Args:
            issue: Raw JIRA issue with metadata
            
        Returns:
            TaskClassification with category, eligibility, and metadata
        """
        # Check for dependencies
        has_dependencies = self.has_third_party_dependencies(issue)
        
        # Estimate effort
        estimated_days = self.estimate_effort_days(issue)
        
        # Check if administrative
        is_admin = self.is_administrative(issue)
        
        # Check if blocking
        is_blocking = issue.priority.lower() == 'blocker'
        blocking_reason = "Marked as blocker priority" if is_blocking else None
        
        # Determine category
        if is_blocking:
            category = TaskCategory.BLOCKING
        elif has_dependencies:
            category = TaskCategory.DEPENDENT
        elif is_admin:
            category = TaskCategory.ADMINISTRATIVE
        elif estimated_days > 1.0:
            category = TaskCategory.LONG_RUNNING
        else:
            category = TaskCategory.PRIORITY_ELIGIBLE
        
        # Determine priority eligibility
        # A task is priority eligible if:
        # - No third-party dependencies
        # - Estimated effort <= 1 day
        # - Not administrative
        # - Not blocking (blocking tasks go through re-planning flow)
        is_priority_eligible = (
            not has_dependencies
            and estimated_days <= 1.0
            and not is_admin
            and not is_blocking
        )
        
        return TaskClassification(
            task=issue,
            category=category,
            is_priority_eligible=is_priority_eligible,
            has_dependencies=has_dependencies,
            estimated_days=estimated_days,
            blocking_reason=blocking_reason
        )
    
    def has_third_party_dependencies(self, issue: JiraIssue) -> bool:
        """
        Check if task has dependencies on external parties.
        
        Examines issue links for "blocks", "is blocked by" relationships
        and custom fields indicating external dependencies.
        
        Returns:
            True if task has third-party dependencies
        """
        # Check issue links for blocking relationships
        for link in issue.issue_links:
            link_type_lower = link.link_type.lower()
            if any(blocking_type in link_type_lower for blocking_type in self.BLOCKING_LINK_TYPES):
                return True
        
        # Check custom fields for external dependency indicators
        for field_name, field_value in issue.custom_fields.items():
            if field_value is None:
                continue
            
            # Check for common external dependency field patterns
            field_name_lower = field_name.lower()
            if 'external' in field_name_lower or 'dependency' in field_name_lower or 'blocked' in field_name_lower:
                # If the field has a non-empty value, consider it a dependency
                if isinstance(field_value, (list, tuple)):
                    if len(field_value) > 0:
                        return True
                elif isinstance(field_value, str):
                    if field_value.strip():
                        return True
                elif field_value:  # Any other truthy value
                    return True
        
        return False
    
    def estimate_effort_days(self, issue: JiraIssue) -> float:
        """
        Estimate effort in working days.
        
        Uses story points (if available) or time tracking estimates.
        When estimates are ambiguous or derived from story points, the system must use
        a conservative default (≥ 1 day) and treat the task as non-priority eligible
        unless explicitly confirmed otherwise.
        
        Returns:
            Estimated effort in days
        """
        # Try story points first
        if issue.story_points is not None and issue.story_points > 0:
            estimated_days = issue.story_points * self.STORY_POINTS_TO_DAYS
            # Conservative rounding: round up to nearest 0.5 day
            return max(1.0, round(estimated_days * 2) / 2)
        
        # Try time estimate
        if issue.time_estimate is not None and issue.time_estimate > 0:
            estimated_days = issue.time_estimate / self.SECONDS_PER_DAY
            # Conservative rounding: round up to nearest 0.5 day
            return max(1.0, round(estimated_days * 2) / 2)
        
        # No estimate available - use conservative default
        # Default to 1 day for tasks without estimates
        return 1.0
    
    def is_administrative(self, issue: JiraIssue) -> bool:
        """
        Determine if task is administrative (low cognitive load).
        
        Checks for labels like "admin", "email", "report", "approval"
        or issue types like "Administrative Task".
        
        Returns:
            True if task is administrative
        """
        # Check labels
        issue_labels_lower = {label.lower() for label in issue.labels}
        if issue_labels_lower & self.ADMIN_LABELS:
            return True
        
        # Check issue type
        if issue.issue_type in self.ADMIN_ISSUE_TYPES:
            return True
        
        # Check if issue type contains admin-related keywords
        issue_type_lower = issue.issue_type.lower()
        if any(admin_keyword in issue_type_lower for admin_keyword in ['admin', 'approval', 'review']):
            return True
        
        return False
