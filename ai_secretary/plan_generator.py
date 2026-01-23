"""Plan generation logic for creating daily execution plans."""

from datetime import date, datetime
from typing import List, Optional

from ai_secretary.jira_client import JiraClient
from ai_secretary.task_classifier import TaskClassifier
from ai_secretary.models import (
    DailyPlan,
    AdminBlock,
    TaskClassification,
    TaskCategory,
)


class PlanGenerator:
    """
    Generates daily plans with up to 3 priorities and grouped admin tasks.
    """
    
    # Maximum number of priority tasks per day
    MAX_PRIORITIES = 3
    
    # Maximum admin block duration in minutes
    MAX_ADMIN_MINUTES = 90
    
    # Default admin block scheduling time (post-lunch)
    DEFAULT_ADMIN_TIME = "14:00-15:30"
    
    def __init__(self, jira_client: JiraClient, classifier: TaskClassifier):
        """
        Initialize plan generator with dependencies.
        
        Args:
            jira_client: JIRA client for fetching tasks
            classifier: Task classifier for categorizing tasks
        """
        self.jira_client = jira_client
        self.classifier = classifier
    
    def _filter_eligible_tasks(self, classifications: List[TaskClassification]) -> List[TaskClassification]:
        """
        Filter tasks to find those eligible for priority selection.
        
        Excludes:
        - Tasks with dependencies
        - Tasks with >1 day effort
        - Administrative tasks
        
        Args:
            classifications: List of classified tasks
            
        Returns:
            List of priority-eligible tasks
        """
        eligible = []
        
        for classification in classifications:
            # Exclude tasks with dependencies
            if classification.has_dependencies:
                continue
            
            # Exclude tasks with >1 day effort
            if classification.estimated_days > 1.0:
                continue
            
            # Exclude administrative tasks
            if classification.category == TaskCategory.ADMINISTRATIVE:
                continue
            
            # Exclude blocking tasks (they go through re-planning flow)
            if classification.category == TaskCategory.BLOCKING:
                continue
            
            eligible.append(classification)
        
        return eligible
    
    def _rank_tasks(self, tasks: List[TaskClassification]) -> List[TaskClassification]:
        """
        Rank tasks by priority, effort, and age.
        
        Ranking criteria (in order):
        1. Priority (Blocker > High > Medium > Low)
        2. Effort (smaller first)
        3. Age (older first - using key as proxy)
        
        Args:
            tasks: List of tasks to rank
            
        Returns:
            Sorted list of tasks
        """
        # Define priority order
        priority_order = {
            'blocker': 0,
            'highest': 1,
            'high': 2,
            'medium': 3,
            'low': 4,
            'lowest': 5,
        }
        
        def sort_key(classification: TaskClassification):
            task = classification.task
            
            # Get priority rank (lower is higher priority)
            priority_rank = priority_order.get(task.priority.lower(), 3)
            
            # Get effort (smaller is better)
            effort = classification.estimated_days
            
            # Get age proxy (older keys typically have lower numbers)
            # Extract numeric part from key like "PROJ-123"
            try:
                key_parts = task.key.split('-')
                if len(key_parts) >= 2:
                    age_proxy = int(key_parts[-1])
                else:
                    age_proxy = 0
            except (ValueError, IndexError):
                age_proxy = 0
            
            return (priority_rank, effort, age_proxy)
        
        return sorted(tasks, key=sort_key)
    
    def _select_priorities(self, ranked_tasks: List[TaskClassification]) -> List[TaskClassification]:
        """
        Select top 3 tasks as priorities.
        
        Args:
            ranked_tasks: List of ranked tasks
            
        Returns:
            List of up to 3 priority tasks
        """
        return ranked_tasks[:self.MAX_PRIORITIES]
    
    def _group_admin_tasks(self, classifications: List[TaskClassification]) -> AdminBlock:
        """
        Group administrative tasks into a time block with 90-minute limit.
        
        Args:
            classifications: List of all classified tasks
            
        Returns:
            AdminBlock with tasks limited to 90 minutes
        """
        # Collect all administrative tasks
        admin_tasks = [
            c for c in classifications
            if c.category == TaskCategory.ADMINISTRATIVE
        ]
        
        # Calculate time allocation and limit to 90 minutes
        selected_tasks = []
        total_minutes = 0
        
        for task in admin_tasks:
            # Convert days to minutes (8 hours per day)
            task_minutes = task.estimated_days * 8 * 60
            
            # Check if adding this task would exceed the limit
            if total_minutes + task_minutes <= self.MAX_ADMIN_MINUTES:
                selected_tasks.append(task)
                total_minutes += task_minutes
            else:
                # Stop adding tasks once we hit the limit
                break
        
        return AdminBlock(
            tasks=selected_tasks,
            time_allocation_minutes=int(total_minutes),
            scheduled_time=self.DEFAULT_ADMIN_TIME
        )
    
    def generate_daily_plan(self, previous_closure_rate: Optional[float] = None) -> DailyPlan:
        """
        Generate a daily plan from current JIRA state.
        
        Args:
            previous_closure_rate: Closure rate from previous day (0.0-1.0)
            
        Returns:
            DailyPlan with up to 3 priorities and admin block
        """
        # Fetch all active tasks from JIRA
        active_tasks = self.jira_client.fetch_active_tasks()
        
        # Classify all tasks
        classifications = [
            self.classifier.classify_task(task)
            for task in active_tasks
        ]
        
        # Filter eligible tasks for priority selection
        eligible_tasks = self._filter_eligible_tasks(classifications)
        
        # Rank eligible tasks
        ranked_tasks = self._rank_tasks(eligible_tasks)
        
        # Select top 3 as priorities
        priorities = self._select_priorities(ranked_tasks)
        
        # Group administrative tasks
        admin_block = self._group_admin_tasks(classifications)
        
        # Collect other tasks for reference (non-priority, non-admin)
        priority_keys = {c.task.key for c in priorities}
        admin_keys = {c.task.key for c in admin_block.tasks}
        
        other_tasks = [
            c for c in classifications
            if c.task.key not in priority_keys and c.task.key not in admin_keys
        ]
        
        # Create and return daily plan
        return DailyPlan(
            date=date.today(),
            priorities=priorities,
            admin_block=admin_block,
            other_tasks=other_tasks,
            previous_closure_rate=previous_closure_rate
        )
