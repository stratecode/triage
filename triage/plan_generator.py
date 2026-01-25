# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Plan generation logic for creating daily execution plans."""

import json
import os
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Dict

from triage.jira_client import JiraClient
from triage.task_classifier import TaskClassifier
from triage.models import (
    DailyPlan,
    AdminBlock,
    TaskClassification,
    TaskCategory,
    JiraIssue,
    SubtaskSpec,
    TaskCompletion,
    ClosureRecord,
)

# Set up logging
logger = logging.getLogger(__name__)


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
    
    def __init__(self, jira_client: JiraClient, classifier: TaskClassifier, 
                 closure_tracking_dir: Optional[str] = None):
        """
        Initialize plan generator with dependencies.
        
        Args:
            jira_client: JIRA client for fetching tasks
            classifier: Task classifier for categorizing tasks
            closure_tracking_dir: Directory for storing closure tracking data (default: .triage/closure)
        """
        self.jira_client = jira_client
        self.classifier = classifier
        
        # Set up closure tracking directory
        if closure_tracking_dir is None:
            closure_tracking_dir = os.path.join(os.getcwd(), '.triage', 'closure')
        
        self.closure_tracking_dir = Path(closure_tracking_dir)
        self.closure_tracking_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Plan generator initialized with closure tracking at: {self.closure_tracking_dir}")
    
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
        Rank tasks by status, priority, effort, and age.
        
        Ranking criteria (in order):
        1. Status (In Progress first - should be completed)
        2. Priority (Blocker > High > Medium > Low)
        3. Effort (smaller first)
        4. Age (older first - using key as proxy)
        
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
            
            # Prioritize tasks already in progress (should be completed first)
            status_rank = 0 if task.status.lower() == 'in progress' else 1
            
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
            
            return (status_rank, priority_rank, effort, age_proxy)
        
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
        
        # Sort admin tasks by effort (smallest first) to maximize tasks that fit
        admin_tasks_sorted = sorted(admin_tasks, key=lambda c: c.estimated_days)
        
        # Calculate time allocation and limit to 90 minutes
        selected_tasks = []
        total_minutes = 0
        
        for task in admin_tasks_sorted:
            # Convert days to minutes (8 hours per day)
            task_minutes = task.estimated_days * 8 * 60
            
            # Check if adding this task would exceed the limit
            if total_minutes + task_minutes <= self.MAX_ADMIN_MINUTES:
                selected_tasks.append(task)
                total_minutes += task_minutes
            # If task doesn't fit, skip it and try the next one
        
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
                                  If None, will attempt to load from previous day's record
            
        Returns:
            DailyPlan with up to 3 priorities and admin block
        """
        logger.info("Generating daily plan")
        
        # Fetch all active tasks from JIRA
        logger.debug("Fetching active tasks from JIRA")
        active_tasks = self.jira_client.fetch_active_tasks()
        logger.info(f"Fetched {len(active_tasks)} active tasks")
        
        # Classify all tasks
        logger.debug("Classifying tasks")
        classifications = [
            self.classifier.classify_task(task)
            for task in active_tasks
        ]
        logger.info(f"Classified {len(classifications)} tasks")
        
        # Identify tasks that need decomposition (long-running tasks)
        decomposition_suggestions = [
            c for c in classifications
            if c.category == TaskCategory.LONG_RUNNING
        ]
        if decomposition_suggestions:
            logger.info(f"Found {len(decomposition_suggestions)} tasks requiring decomposition")
            for c in decomposition_suggestions:
                logger.info(f"  {c.task.key}: {c.estimated_days:.1f} days - {c.task.summary}")
        
        # Filter eligible tasks for priority selection
        eligible_tasks = self._filter_eligible_tasks(classifications)
        logger.info(f"Found {len(eligible_tasks)} priority-eligible tasks")
        
        # Rank eligible tasks
        ranked_tasks = self._rank_tasks(eligible_tasks)
        logger.debug(f"Ranked {len(ranked_tasks)} tasks")
        
        # Select top 3 as priorities
        priorities = self._select_priorities(ranked_tasks)
        logger.info(f"Selected {len(priorities)} priority tasks")
        for i, p in enumerate(priorities, 1):
            logger.info(f"  Priority {i}: {p.task.key} - {p.task.summary}")
        
        # Group administrative tasks
        admin_block = self._group_admin_tasks(classifications)
        logger.info(f"Grouped {len(admin_block.tasks)} administrative tasks ({admin_block.time_allocation_minutes} minutes)")
        
        # Collect other tasks for reference (non-priority, non-admin, non-decomposition-suggestions)
        priority_keys = {c.task.key for c in priorities}
        admin_keys = {c.task.key for c in admin_block.tasks}
        decomposition_keys = {c.task.key for c in decomposition_suggestions}
        
        other_tasks = [
            c for c in classifications
            if c.task.key not in priority_keys 
            and c.task.key not in admin_keys
            and c.task.key not in decomposition_keys
        ]
        logger.info(f"Identified {len(other_tasks)} other tasks for reference")
        
        # Get previous closure rate if not provided
        if previous_closure_rate is None:
            previous_closure_rate = self.get_previous_closure_rate(date.today())
            if previous_closure_rate is not None:
                logger.info(f"Previous closure rate: {previous_closure_rate:.2%}")
        
        # Create and return daily plan
        plan = DailyPlan(
            date=date.today(),
            priorities=priorities,
            admin_block=admin_block,
            other_tasks=other_tasks,
            previous_closure_rate=previous_closure_rate,
            decomposition_suggestions=decomposition_suggestions
        )
        
        logger.info(f"Daily plan generated successfully for {plan.date}")
        return plan
    
    def generate_replan(self, blocking_task: JiraIssue, current_plan: DailyPlan) -> DailyPlan:
        """
        Generate new plan incorporating a blocking task.
        
        This method is triggered when a blocking task is detected and creates
        a new plan that includes the blocking task as a priority, potentially
        replacing some or all of the current priorities.
        
        Args:
            blocking_task: The blocking task that triggered re-planning
            current_plan: Current plan being interrupted
            
        Returns:
            New DailyPlan with blocking task as priority
        """
        # Fetch all active tasks from JIRA
        active_tasks = self.jira_client.fetch_active_tasks()
        
        # Classify all tasks
        classifications = [
            self.classifier.classify_task(task)
            for task in active_tasks
        ]
        
        # Classify the blocking task
        blocking_classification = self.classifier.classify_task(blocking_task)
        
        # Ensure the blocking task is included in classifications if not already
        blocking_keys = {c.task.key for c in classifications}
        if blocking_task.key not in blocking_keys:
            classifications.append(blocking_classification)
        
        # Filter eligible tasks for priority selection (excluding the blocking task for now)
        eligible_tasks = self._filter_eligible_tasks(classifications)
        
        # Rank eligible tasks
        ranked_tasks = self._rank_tasks(eligible_tasks)
        
        # Start with the blocking task as the first priority
        new_priorities = [blocking_classification]
        
        # Add up to 2 more priorities from the ranked tasks
        # Exclude tasks that were in the current plan's priorities to give preference to new work
        current_priority_keys = {c.task.key for c in current_plan.priorities}
        
        for task in ranked_tasks:
            if len(new_priorities) >= self.MAX_PRIORITIES:
                break
            
            # Skip if this is the blocking task (already added)
            if task.task.key == blocking_task.key:
                continue
            
            # Add to new priorities
            new_priorities.append(task)
        
        # Group administrative tasks (same as before)
        admin_block = self._group_admin_tasks(classifications)
        
        # Collect other tasks for reference (non-priority, non-admin)
        priority_keys = {c.task.key for c in new_priorities}
        admin_keys = {c.task.key for c in admin_block.tasks}
        
        other_tasks = [
            c for c in classifications
            if c.task.key not in priority_keys and c.task.key not in admin_keys
        ]
        
        # Get previous closure rate from current plan
        previous_closure_rate = current_plan.previous_closure_rate
        
        # Create and return new daily plan
        return DailyPlan(
            date=date.today(),
            priorities=new_priorities,
            admin_block=admin_block,
            other_tasks=other_tasks,
            previous_closure_rate=previous_closure_rate
        )
    
    def propose_decomposition(self, long_running_task: JiraIssue) -> List[SubtaskSpec]:
        """
        Propose decomposition of multi-day task into daily-closable subtasks.
        
        This method analyzes a long-running task and generates a proposal for
        breaking it down into smaller subtasks that can each be completed within
        one working day.
        
        Args:
            long_running_task: Task estimated to take > 1 day
            
        Returns:
            List of proposed subtasks, each closable in one day
        """
        logger.info(f"Proposing decomposition for task: {long_running_task.key} - {long_running_task.summary}")
        
        # First, classify the task to get its estimated effort
        classification = self.classifier.classify_task(long_running_task)
        logger.debug(f"Task estimated effort: {classification.estimated_days} days")
        
        # Verify this is actually a long-running task
        if classification.estimated_days <= 1.0:
            # Task is not long-running, return empty list
            logger.warning(f"Task {long_running_task.key} is not long-running ({classification.estimated_days} days), skipping decomposition")
            return []
        
        # Calculate number of subtasks needed
        # We aim for subtasks of ~0.75 days each to ensure they're comfortably under 1 day
        target_subtask_days = 0.75
        num_subtasks = max(2, int(classification.estimated_days / target_subtask_days) + 1)
        logger.debug(f"Calculated {num_subtasks} subtasks needed")
        
        # Calculate effort per subtask
        effort_per_subtask = classification.estimated_days / num_subtasks
        
        # Ensure no subtask exceeds 1.0 days
        if effort_per_subtask > 1.0:
            # Recalculate with more subtasks
            num_subtasks = int(classification.estimated_days) + 1
            effort_per_subtask = classification.estimated_days / num_subtasks
            logger.debug(f"Adjusted to {num_subtasks} subtasks to ensure each is <= 1 day")
        
        logger.debug(f"Effort per subtask: {effort_per_subtask:.2f} days")
        
        # Generate subtask specifications
        subtasks = []
        
        # Extract task type for better subtask naming
        task_type = long_running_task.issue_type.lower()
        
        for i in range(num_subtasks):
            order = i + 1
            
            # Generate descriptive summary based on task type and order
            if num_subtasks == 2:
                phase_names = ["Initial Implementation", "Completion and Testing"]
            elif num_subtasks == 3:
                phase_names = ["Initial Setup", "Core Implementation", "Testing and Refinement"]
            elif num_subtasks == 4:
                phase_names = ["Setup and Planning", "Initial Implementation", "Core Features", "Testing and Documentation"]
            else:
                # For more subtasks, use generic phase naming
                phase_names = [f"Phase {j+1}" for j in range(num_subtasks)]
            
            phase_name = phase_names[i] if i < len(phase_names) else f"Phase {order}"
            
            summary = f"{long_running_task.summary} - {phase_name}"
            
            # Generate description with context
            description = f"""This is subtask {order} of {num_subtasks} for the parent task: {long_running_task.key}

Parent task summary: {long_running_task.summary}

This subtask focuses on: {phase_name}

Original parent description:
{long_running_task.description}

This subtask should be completable within one working day."""
            
            subtasks.append(SubtaskSpec(
                summary=summary,
                description=description,
                estimated_days=effort_per_subtask,
                order=order
            ))
            
            logger.debug(f"  Subtask {order}: {phase_name} ({effort_per_subtask:.2f} days)")
        
        logger.info(f"Generated {len(subtasks)} subtask proposals for {long_running_task.key}")
        return subtasks
    
    def _get_closure_file_path(self, plan_date: date) -> Path:
        """
        Get the file path for a closure record.
        
        Args:
            plan_date: Date of the plan
            
        Returns:
            Path to closure record file
        """
        filename = f"closure_{plan_date.isoformat()}.json"
        return self.closure_tracking_dir / filename
    
    def record_completion(self, task_key: str, completion_date: date, was_priority: bool) -> None:
        """
        Record completion of a task.
        
        Args:
            task_key: JIRA key of completed task
            completion_date: Date task was completed
            was_priority: Whether task was a priority task
        """
        # Load or create closure record for the date
        closure_file = self._get_closure_file_path(completion_date)
        
        if closure_file.exists():
            with open(closure_file, 'r') as f:
                data = json.load(f)
                
            # Update completion count if this was a priority task
            if was_priority:
                data['completed_priorities'] = data.get('completed_priorities', 0) + 1
                
                # Remove from incomplete tasks if present
                incomplete = data.get('incomplete_tasks', [])
                if task_key in incomplete:
                    incomplete.remove(task_key)
                    data['incomplete_tasks'] = incomplete
                
                # Recalculate closure rate
                total = data.get('total_priorities', 0)
                completed = data['completed_priorities']
                data['closure_rate'] = completed / total if total > 0 else 0.0
            
            # Save updated record
            with open(closure_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    def calculate_closure_rate(self, plan_date: date, priority_tasks: List[TaskClassification]) -> float:
        """
        Calculate closure rate for a given date based on completed tasks.
        
        Args:
            plan_date: Date of the plan
            priority_tasks: List of priority tasks from the plan
            
        Returns:
            Closure rate (0.0-1.0)
        """
        # Get priority task keys
        priority_keys = {c.task.key for c in priority_tasks}
        
        # Fetch current task statuses from JIRA
        active_tasks = self.jira_client.fetch_active_tasks()
        active_keys = {task.key for task in active_tasks}
        
        # Count completed tasks (those not in active tasks anymore)
        completed_count = 0
        for key in priority_keys:
            if key not in active_keys:
                completed_count += 1
        
        # Calculate closure rate
        total_priorities = len(priority_tasks)
        closure_rate = completed_count / total_priorities if total_priorities > 0 else 0.0
        
        return closure_rate
    
    def save_closure_record(self, plan_date: date, priority_tasks: List[TaskClassification]) -> ClosureRecord:
        """
        Save closure record for a plan.
        
        Args:
            plan_date: Date of the plan
            priority_tasks: List of priority tasks from the plan
            
        Returns:
            ClosureRecord with tracking information
        """
        # Calculate closure rate
        closure_rate = self.calculate_closure_rate(plan_date, priority_tasks)
        
        # Get priority task keys
        priority_keys = [c.task.key for c in priority_tasks]
        
        # Fetch current task statuses to identify incomplete tasks
        active_tasks = self.jira_client.fetch_active_tasks()
        active_keys = {task.key for task in active_tasks}
        
        # Identify incomplete tasks
        incomplete_tasks = [key for key in priority_keys if key in active_keys]
        
        # Calculate completed count
        total_priorities = len(priority_tasks)
        completed_priorities = total_priorities - len(incomplete_tasks)
        
        # Create closure record
        record = ClosureRecord(
            date=plan_date,
            total_priorities=total_priorities,
            completed_priorities=completed_priorities,
            closure_rate=closure_rate,
            incomplete_tasks=incomplete_tasks
        )
        
        # Save to file
        closure_file = self._get_closure_file_path(plan_date)
        data = {
            'date': plan_date.isoformat(),
            'total_priorities': record.total_priorities,
            'completed_priorities': record.completed_priorities,
            'closure_rate': record.closure_rate,
            'incomplete_tasks': record.incomplete_tasks
        }
        
        with open(closure_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return record
    
    def load_closure_record(self, plan_date: date) -> Optional[ClosureRecord]:
        """
        Load closure record for a specific date.
        
        Args:
            plan_date: Date of the plan
            
        Returns:
            ClosureRecord if found, None otherwise
        """
        closure_file = self._get_closure_file_path(plan_date)
        
        if not closure_file.exists():
            return None
        
        try:
            with open(closure_file, 'r') as f:
                data = json.load(f)
            
            return ClosureRecord(
                date=date.fromisoformat(data['date']),
                total_priorities=data['total_priorities'],
                completed_priorities=data['completed_priorities'],
                closure_rate=data['closure_rate'],
                incomplete_tasks=data.get('incomplete_tasks', [])
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def get_previous_closure_rate(self, current_date: date) -> Optional[float]:
        """
        Get closure rate from the previous day.
        
        Args:
            current_date: Current plan date
            
        Returns:
            Previous day's closure rate, or None if not available
        """
        # Calculate previous day
        from datetime import timedelta
        previous_date = current_date - timedelta(days=1)
        
        # Load closure record
        record = self.load_closure_record(previous_date)
        
        if record is None:
            return None
        
        return record.closure_rate
    
    def prompt_incomplete_tasks(self, plan_date: date) -> Dict[str, str]:
        """
        Prompt for incomplete tasks from a previous plan.
        
        Args:
            plan_date: Date of the plan to check
            
        Returns:
            Dictionary mapping task keys to user decisions ("carry_forward" or "re_evaluate")
        """
        # Load closure record
        record = self.load_closure_record(plan_date)
        
        if record is None or not record.incomplete_tasks:
            return {}
        
        # In a real implementation, this would prompt the user
        # For now, we'll return an empty dict (no decisions made)
        # This will be implemented in the CLI or approval manager
        return {}
