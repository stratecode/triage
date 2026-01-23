# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for JIRA state reflection and synchronization."""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch
from datetime import date

from triage.jira_client import JiraClient
from triage.task_classifier import TaskClassifier
from triage.plan_generator import PlanGenerator
from triage.models import JiraIssue, IssueLink, TaskCategory


# Custom strategies for generating test data
# Global counter to ensure unique keys across all generated issues
_issue_counter = 0

@st.composite
def jira_issue_strategy(draw, key_prefix="PROJ"):
    """Generate a random JiraIssue with guaranteed unique key."""
    global _issue_counter
    _issue_counter += 1
    # Use counter + random to ensure uniqueness even across test runs
    issue_num = _issue_counter * 10000 + draw(st.integers(min_value=1, max_value=9999))
    key = f"{key_prefix}-{issue_num}"
    
    summary = draw(st.text(min_size=5, max_size=100))
    description = draw(st.text(min_size=0, max_size=500))
    issue_type = draw(st.sampled_from(['Story', 'Bug', 'Task', 'Epic']))
    priority = draw(st.sampled_from(['Blocker', 'High', 'Medium', 'Low']))
    status = draw(st.sampled_from(['To Do', 'In Progress', 'Done', 'Closed']))
    assignee = draw(st.emails())
    
    story_points = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=13)))
    time_estimate = draw(st.one_of(st.none(), st.integers(min_value=3600, max_value=86400)))
    
    labels = draw(st.lists(st.text(min_size=1, max_size=20), max_size=5))
    
    # Generate issue links
    num_links = draw(st.integers(min_value=0, max_value=3))
    issue_links = []
    for _ in range(num_links):
        link_type = draw(st.sampled_from(['blocks', 'is blocked by', 'relates to', 'depends on']))
        target_key = f"{key_prefix}-{draw(st.integers(min_value=1, max_value=9999))}"
        target_summary = draw(st.text(min_size=5, max_size=50))
        issue_links.append(IssueLink(
            link_type=link_type,
            target_key=target_key,
            target_summary=target_summary
        ))
    
    return JiraIssue(
        key=key,
        summary=summary,
        description=description,
        issue_type=issue_type,
        priority=priority,
        status=status,
        assignee=assignee,
        story_points=story_points,
        time_estimate=time_estimate,
        labels=labels,
        issue_links=issue_links,
        custom_fields={}
    )


@st.composite
def task_list_strategy(draw, min_size=1, max_size=10):
    """Generate a list of JiraIssue objects with unique keys."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    tasks = []
    used_keys = set()
    
    for _ in range(size):
        task = draw(jira_issue_strategy())
        # Ensure uniqueness within the list
        while task.key in used_keys:
            task = draw(jira_issue_strategy())
        used_keys.add(task.key)
        tasks.append(task)
    
    return tasks


class TestJiraStateReflection:
    """
    Property 17: JIRA State Reflection
    
    For any change to task status or metadata in JIRA (completion, priority change,
    dependency change), the next generated plan shall reflect those changes.
    
    Validates: Requirements 6.3, 6.5, 10.4
    """
    
    @given(
        initial_tasks=task_list_strategy(min_size=3, max_size=8),
        status_change_indices=st.lists(st.integers(min_value=0, max_value=7), min_size=1, max_size=3, unique=True)
    )
    @settings(max_examples=100, deadline=None)
    def test_status_changes_reflected_in_plan(self, initial_tasks, status_change_indices):
        """
        Feature: ai-secretary, Property 17: JIRA State Reflection
        
        Test that status changes in JIRA are reflected in subsequent plans.
        """
        # Filter indices to valid range
        status_change_indices = [i for i in status_change_indices if i < len(initial_tasks)]
        if not status_change_indices:
            return  # Skip if no valid indices
        
        # Create modified tasks with status changes
        modified_tasks = [task for task in initial_tasks]
        for idx in status_change_indices:
            # Change status to 'Done'
            modified_task = JiraIssue(
                key=modified_tasks[idx].key,
                summary=modified_tasks[idx].summary,
                description=modified_tasks[idx].description,
                issue_type=modified_tasks[idx].issue_type,
                priority=modified_tasks[idx].priority,
                status='Done',  # Changed status
                assignee=modified_tasks[idx].assignee,
                story_points=modified_tasks[idx].story_points,
                time_estimate=modified_tasks[idx].time_estimate,
                labels=modified_tasks[idx].labels,
                issue_links=modified_tasks[idx].issue_links,
                custom_fields=modified_tasks[idx].custom_fields
            )
            modified_tasks[idx] = modified_task
        
        # Mock JIRA client to return initial tasks, then modified tasks
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch:
            # First call returns initial tasks
            # Second call returns modified tasks (with completed tasks removed)
            active_modified_tasks = [t for t in modified_tasks if t.status != 'Done']
            mock_fetch.side_effect = [initial_tasks, active_modified_tasks]
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier)
            
            # Generate first plan
            plan1 = plan_generator.generate_daily_plan()
            
            # Generate second plan (should reflect status changes)
            plan2 = plan_generator.generate_daily_plan()
            
            # Verify that completed tasks are not in the second plan
            plan2_keys = {c.task.key for c in plan2.priorities + plan2.admin_block.tasks + plan2.other_tasks}
            
            for idx in status_change_indices:
                completed_key = initial_tasks[idx].key
                assert completed_key not in plan2_keys, \
                    f"Completed task {completed_key} should not appear in subsequent plan"
    
    @given(
        initial_tasks=task_list_strategy(min_size=3, max_size=8),
        priority_change_index=st.integers(min_value=0, max_value=7)
    )
    @settings(max_examples=100, deadline=None)
    def test_priority_changes_reflected_in_plan(self, initial_tasks, priority_change_index):
        """
        Feature: ai-secretary, Property 17: JIRA State Reflection
        
        Test that priority changes in JIRA are reflected in subsequent plans.
        """
        if priority_change_index >= len(initial_tasks):
            return  # Skip if index out of range
        
        # Create modified tasks with priority change
        modified_tasks = [task for task in initial_tasks]
        original_priority = modified_tasks[priority_change_index].priority
        
        # Change priority to 'Blocker' if not already, otherwise to 'Low'
        new_priority = 'Blocker' if original_priority != 'Blocker' else 'Low'
        
        modified_task = JiraIssue(
            key=modified_tasks[priority_change_index].key,
            summary=modified_tasks[priority_change_index].summary,
            description=modified_tasks[priority_change_index].description,
            issue_type=modified_tasks[priority_change_index].issue_type,
            priority=new_priority,  # Changed priority
            status=modified_tasks[priority_change_index].status,
            assignee=modified_tasks[priority_change_index].assignee,
            story_points=modified_tasks[priority_change_index].story_points,
            time_estimate=modified_tasks[priority_change_index].time_estimate,
            labels=modified_tasks[priority_change_index].labels,
            issue_links=modified_tasks[priority_change_index].issue_links,
            custom_fields=modified_tasks[priority_change_index].custom_fields
        )
        modified_tasks[priority_change_index] = modified_task
        
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch:
            mock_fetch.side_effect = [initial_tasks, modified_tasks]
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier)
            
            # Generate first plan
            plan1 = plan_generator.generate_daily_plan()
            
            # Generate second plan (should reflect priority changes)
            plan2 = plan_generator.generate_daily_plan()
            
            # Find the task in both plans
            changed_key = modified_tasks[priority_change_index].key
            
            # Get classifications for the changed task in both plans
            all_plan1_tasks = plan1.priorities + plan1.admin_block.tasks + plan1.other_tasks
            all_plan2_tasks = plan2.priorities + plan2.admin_block.tasks + plan2.other_tasks
            
            task1_classification = next((c for c in all_plan1_tasks if c.task.key == changed_key), None)
            task2_classification = next((c for c in all_plan2_tasks if c.task.key == changed_key), None)
            
            # If task appears in both plans, verify priority changed
            if task1_classification and task2_classification:
                assert task1_classification.task.priority != task2_classification.task.priority, \
                    "Priority change should be reflected in subsequent plan"
                assert task2_classification.task.priority == new_priority, \
                    f"New priority should be {new_priority}"
    
    @given(
        initial_tasks=task_list_strategy(min_size=3, max_size=8),
        metadata_change_index=st.integers(min_value=0, max_value=7)
    )
    @settings(max_examples=100, deadline=None)
    def test_metadata_changes_reflected_in_plan(self, initial_tasks, metadata_change_index):
        """
        Feature: ai-secretary, Property 17: JIRA State Reflection
        
        Test that metadata changes (story points, labels) are reflected in subsequent plans.
        """
        if metadata_change_index >= len(initial_tasks):
            return  # Skip if index out of range
        
        # Create modified tasks with metadata changes
        modified_tasks = [task for task in initial_tasks]
        original_task = modified_tasks[metadata_change_index]
        
        # Change story points - ensure we have a detectable change
        # If original is None, set to 5; otherwise add 5
        original_story_points = original_task.story_points
        new_story_points = 5 if original_story_points is None else original_story_points + 5
        
        # Add a unique label to ensure detectable change
        new_labels = original_task.labels + ['urgent-metadata-change']
        
        modified_task = JiraIssue(
            key=original_task.key,
            summary=original_task.summary,
            description=original_task.description,
            issue_type=original_task.issue_type,
            priority=original_task.priority,
            status=original_task.status,
            assignee=original_task.assignee,
            story_points=new_story_points,  # Changed
            time_estimate=original_task.time_estimate,
            labels=new_labels,  # Changed
            issue_links=original_task.issue_links,
            custom_fields=original_task.custom_fields
        )
        modified_tasks[metadata_change_index] = modified_task
        
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch:
            mock_fetch.side_effect = [initial_tasks, modified_tasks]
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier)
            
            # Generate first plan
            plan1 = plan_generator.generate_daily_plan()
            
            # Generate second plan (should reflect metadata changes)
            plan2 = plan_generator.generate_daily_plan()
            
            # Find the task in both plans
            changed_key = modified_tasks[metadata_change_index].key
            
            all_plan1_tasks = plan1.priorities + plan1.admin_block.tasks + plan1.other_tasks
            all_plan2_tasks = plan2.priorities + plan2.admin_block.tasks + plan2.other_tasks
            
            task1_classification = next((c for c in all_plan1_tasks if c.task.key == changed_key), None)
            task2_classification = next((c for c in all_plan2_tasks if c.task.key == changed_key), None)
            
            # If task appears in both plans, verify metadata changed
            if task1_classification and task2_classification:
                # Verify story points changed (handle None case)
                plan1_story_points = task1_classification.task.story_points
                plan2_story_points = task2_classification.task.story_points
                
                assert plan1_story_points != plan2_story_points, \
                    f"Story points should change from {plan1_story_points} to {plan2_story_points}"
                assert plan2_story_points == new_story_points, \
                    f"New story points should be {new_story_points}, got {plan2_story_points}"
                
                # Verify labels changed
                assert 'urgent-metadata-change' in task2_classification.task.labels, \
                    "New label should be present in subsequent plan"
                assert 'urgent-metadata-change' not in task1_classification.task.labels, \
                    "New label should not be in first plan"



class TestDependencyReEvaluation:
    """
    Property 18: Dependency Re-evaluation
    
    For any task whose dependencies are resolved in JIRA, the Task_Classifier
    shall re-evaluate it as priority-eligible in the next classification cycle.
    
    Validates: Requirements 10.4
    """
    
    @given(
        task_with_dependency=jira_issue_strategy(),
        dependency_resolved=st.booleans()
    )
    @settings(max_examples=100, deadline=None)
    def test_resolved_dependencies_make_task_eligible(self, task_with_dependency, dependency_resolved):
        """
        Feature: ai-secretary, Property 18: Dependency Re-evaluation
        
        Test that tasks with resolved dependencies become priority-eligible.
        """
        # Filter out outgoing dependencies ('blocks', 'relates to') - only keep incoming dependencies
        # that actually block this task from being worked on
        incoming_dependencies = [
            link for link in task_with_dependency.issue_links
            if link.link_type in ['is blocked by', 'depends on', 'blocked by']
        ]
        
        # Always create a task with exactly one incoming blocking dependency
        blocking_link = IssueLink(
            link_type='is blocked by',
            target_key='PROJ-999',
            target_summary='Blocking task'
        )
        
        task_with_dependency = JiraIssue(
            key=task_with_dependency.key,
            summary=task_with_dependency.summary,
            description=task_with_dependency.description,
            issue_type=task_with_dependency.issue_type,
            priority=task_with_dependency.priority,
            status=task_with_dependency.status,
            assignee=task_with_dependency.assignee,
            story_points=task_with_dependency.story_points,
            time_estimate=task_with_dependency.time_estimate,
            labels=task_with_dependency.labels,
            issue_links=[blocking_link],  # Only incoming dependency
            custom_fields=task_with_dependency.custom_fields
        )
        
        # Ensure task has reasonable effort (≤1 day) and is not admin or blocker
        task_with_dependency = JiraIssue(
            key=task_with_dependency.key,
            summary=task_with_dependency.summary,
            description=task_with_dependency.description,
            issue_type='Story',
            priority='Medium',
            status=task_with_dependency.status,
            assignee=task_with_dependency.assignee,
            story_points=1,  # 1.25 days, but will be rounded to 1 day
            time_estimate=28800,  # 8 hours = 1 day
            labels=[],
            issue_links=task_with_dependency.issue_links,
            custom_fields=task_with_dependency.custom_fields
        )
        
        # Create classifier
        classifier = TaskClassifier()
        
        # First classification - should have dependencies
        classification1 = classifier.classify_task(task_with_dependency)
        
        # Verify task has dependencies initially
        assert classification1.has_dependencies, \
            "Task should have dependencies initially"
        assert not classification1.is_priority_eligible, \
            "Task with dependencies should not be priority eligible"
        
        if dependency_resolved:
            # Remove dependencies (simulating resolution)
            task_without_dependency = JiraIssue(
                key=task_with_dependency.key,
                summary=task_with_dependency.summary,
                description=task_with_dependency.description,
                issue_type=task_with_dependency.issue_type,
                priority=task_with_dependency.priority,
                status=task_with_dependency.status,
                assignee=task_with_dependency.assignee,
                story_points=task_with_dependency.story_points,
                time_estimate=task_with_dependency.time_estimate,
                labels=task_with_dependency.labels,
                issue_links=[],  # Dependencies resolved
                custom_fields=task_with_dependency.custom_fields
            )
            
            # Re-classify after dependency resolution
            classification2 = classifier.classify_task(task_without_dependency)
            
            # Verify task no longer has dependencies
            assert not classification2.has_dependencies, \
                "Task should not have dependencies after resolution"
            
            # Verify task is now priority eligible (if other conditions met)
            if classification2.estimated_days <= 1.0 and classification2.category != TaskCategory.ADMINISTRATIVE:
                assert classification2.is_priority_eligible, \
                    "Task should become priority eligible after dependency resolution"
    
    @given(
        initial_tasks=task_list_strategy(min_size=2, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_dependency_resolution_reflected_in_plan(self, initial_tasks):
        """
        Feature: ai-secretary, Property 18: Dependency Re-evaluation
        
        Test that dependency resolution is reflected in subsequent plans.
        """
        if len(initial_tasks) < 2:
            return  # Need at least 2 tasks
        
        # Make first task have a dependency on second task
        task_with_dep = initial_tasks[0]
        blocking_task = initial_tasks[1]
        
        # Ensure first task has reasonable properties for priority eligibility
        task_with_dep = JiraIssue(
            key=task_with_dep.key,
            summary=task_with_dep.summary,
            description=task_with_dep.description,
            issue_type='Story',
            priority='Medium',
            status='To Do',
            assignee=task_with_dep.assignee,
            story_points=1,
            time_estimate=28800,
            labels=[],
            issue_links=[IssueLink(
                link_type='is blocked by',
                target_key=blocking_task.key,
                target_summary=blocking_task.summary
            )],
            custom_fields={}
        )
        
        initial_tasks[0] = task_with_dep
        
        # Create modified tasks with dependency removed
        modified_tasks = [task for task in initial_tasks]
        modified_tasks[0] = JiraIssue(
            key=task_with_dep.key,
            summary=task_with_dep.summary,
            description=task_with_dep.description,
            issue_type=task_with_dep.issue_type,
            priority=task_with_dep.priority,
            status=task_with_dep.status,
            assignee=task_with_dep.assignee,
            story_points=task_with_dep.story_points,
            time_estimate=task_with_dep.time_estimate,
            labels=task_with_dep.labels,
            issue_links=[],  # Dependency resolved
            custom_fields=task_with_dep.custom_fields
        )
        
        # Mock JIRA client
        with patch.object(JiraClient, 'fetch_active_tasks') as mock_fetch:
            mock_fetch.side_effect = [initial_tasks, modified_tasks]
            
            # Create components
            jira_client = JiraClient(
                base_url="https://test.atlassian.net",
                email="test@example.com",
                api_token="test-token"
            )
            classifier = TaskClassifier()
            plan_generator = PlanGenerator(jira_client, classifier)
            
            # Generate first plan
            plan1 = plan_generator.generate_daily_plan()
            
            # Task should not be in priorities (has dependency)
            plan1_priority_keys = {c.task.key for c in plan1.priorities}
            assert task_with_dep.key not in plan1_priority_keys, \
                "Task with dependency should not be in priorities"
            
            # Generate second plan (after dependency resolution)
            plan2 = plan_generator.generate_daily_plan()
            
            # Task might now be in priorities (dependency resolved)
            # We can't guarantee it will be in top 3, but it should be eligible
            all_plan2_tasks = plan2.priorities + plan2.admin_block.tasks + plan2.other_tasks
            task_classification = next((c for c in all_plan2_tasks if c.task.key == task_with_dep.key), None)
            
            if task_classification:
                # Verify task no longer has dependencies
                assert not task_classification.has_dependencies, \
                    "Task should not have dependencies in second plan"
                
                # Verify task is now priority eligible
                assert task_classification.is_priority_eligible, \
                    "Task should be priority eligible after dependency resolution"
