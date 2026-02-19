# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for task classification.

Feature: ai-secretary
"""

from hypothesis import given
from hypothesis import strategies as st

from triage.models import (
    IssueLink,
    JiraIssue,
    TaskCategory,
    TaskClassification,
)
from triage.task_classifier import TaskClassifier


# Custom strategies for generating test data
@st.composite
def issue_link_strategy(draw):
    """Generate random IssueLink objects."""
    link_types = ["blocks", "is blocked by", "relates to", "duplicates", "depends on", "blocked by"]
    # Generate JIRA-style keys like PROJ-123
    project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    target_key = f"{project}-{number}"

    return IssueLink(
        link_type=draw(st.sampled_from(link_types)),
        target_key=target_key,
        target_summary=draw(st.text(min_size=5, max_size=100)),
    )


@st.composite
def jira_issue_strategy(draw):
    """Generate random JiraIssue objects."""
    issue_types = ["Story", "Bug", "Task", "Epic", "Sub-task", "Administrative Task", "Admin", "Approval"]
    priorities = ["Blocker", "High", "Medium", "Low"]
    statuses = ["To Do", "In Progress", "Blocked", "Done"]

    # Generate JIRA-style keys like PROJ-123
    project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
    number = draw(st.integers(min_value=1, max_value=9999))
    key = f"{project}-{number}"

    return JiraIssue(
        key=key,
        summary=draw(st.text(min_size=5, max_size=200)),
        description=draw(st.text(min_size=0, max_size=500)),
        issue_type=draw(st.sampled_from(issue_types)),
        priority=draw(st.sampled_from(priorities)),
        status=draw(st.sampled_from(statuses)),
        assignee=draw(st.emails()),
        story_points=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=13))),
        time_estimate=draw(st.one_of(st.none(), st.integers(min_value=3600, max_value=86400))),
        labels=draw(st.lists(st.text(min_size=1, max_size=20), max_size=5)),
        issue_links=draw(st.lists(issue_link_strategy(), max_size=3)),
        custom_fields=draw(
            st.dictionaries(st.text(min_size=1, max_size=20), st.text(min_size=0, max_size=50), max_size=3)
        ),
    )


@st.composite
def jira_issue_with_dependencies_strategy(draw):
    """Generate JiraIssue objects with various dependency structures."""
    issue = draw(jira_issue_strategy())

    # Decide what kind of dependencies to add
    dependency_type = draw(st.sampled_from(["issue_links", "custom_fields", "both", "none"]))

    if dependency_type in ["issue_links", "both"]:
        # Add blocking issue links
        blocking_link_types = ["is blocked by", "depends on", "blocked by"]
        num_links = draw(st.integers(min_value=1, max_value=3))
        blocking_links = []
        for _ in range(num_links):
            project = draw(st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=("Lu",))))
            number = draw(st.integers(min_value=1, max_value=9999))
            target_key = f"{project}-{number}"
            blocking_links.append(
                IssueLink(
                    link_type=draw(st.sampled_from(blocking_link_types)),
                    target_key=target_key,
                    target_summary=draw(st.text(min_size=5, max_size=100)),
                )
            )
        issue.issue_links.extend(blocking_links)

    if dependency_type in ["custom_fields", "both"]:
        # Add custom field dependencies
        field_names = ["external_dependency", "blocked_by_field", "dependency_list"]
        field_name = draw(st.sampled_from(field_names))
        field_value = draw(
            st.one_of(
                st.text(min_size=1, max_size=50), st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=3)
            )
        )
        issue.custom_fields[field_name] = field_value

    return issue


@st.composite
def jira_issue_with_admin_markers_strategy(draw):
    """Generate JiraIssue objects with administrative markers."""
    issue = draw(jira_issue_strategy())

    # Decide what kind of admin markers to add
    marker_type = draw(st.sampled_from(["label", "issue_type", "both"]))

    if marker_type in ["label", "both"]:
        # Add admin labels
        admin_labels = ["admin", "administrative", "email", "report", "approval", "meeting", "review"]
        issue.labels.append(draw(st.sampled_from(admin_labels)))

    if marker_type in ["issue_type", "both"]:
        # Set admin issue type
        admin_types = ["Administrative Task", "Admin", "Approval", "Review"]
        issue.issue_type = draw(st.sampled_from(admin_types))

    return issue


# Property 3: Task Classification Completeness
@given(jira_issue_strategy())
def test_property_3_task_classification_completeness(issue: JiraIssue):
    """Property 3: Task Classification Completeness

    For any task fetched from JIRA, the Task_Classifier shall produce a classification
    containing category, eligibility status, dependency status, and effort estimate.

    Feature: ai-secretary, Property 3: Task Classification Completeness
    Validates: Requirements 1.2, 2.1
    """
    classifier = TaskClassifier()

    # Classify the task
    classification = classifier.classify_task(issue)

    # Verify classification is returned
    assert isinstance(classification, TaskClassification)

    # Verify all required fields are present and have valid values
    assert classification.task is issue, "Classification must reference the original task"

    # Verify category is set
    assert isinstance(classification.category, TaskCategory), "Category must be a TaskCategory enum"
    assert classification.category in TaskCategory, "Category must be a valid TaskCategory value"

    # Verify eligibility status is set
    assert isinstance(classification.is_priority_eligible, bool), "is_priority_eligible must be a boolean"

    # Verify dependency status is set
    assert isinstance(classification.has_dependencies, bool), "has_dependencies must be a boolean"

    # Verify effort estimate is set and valid
    assert isinstance(classification.estimated_days, (int, float)), "estimated_days must be numeric"
    assert classification.estimated_days > 0, "estimated_days must be positive"

    # Verify blocking_reason is set appropriately
    if classification.category == TaskCategory.BLOCKING:
        assert classification.blocking_reason is not None, "Blocking tasks must have a blocking_reason"
    # Note: blocking_reason can be None for non-blocking tasks


# Property 4: Classification Idempotence
@given(jira_issue_strategy())
def test_property_4_classification_idempotence(issue: JiraIssue):
    """Property 4: Classification Idempotence

    For any task, classifying it multiple times shall produce equivalent classifications
    (classification does not modify state).

    Feature: ai-secretary, Property 4: Classification Idempotence
    Validates: Requirements 2.2
    """
    classifier = TaskClassifier()

    # Classify the same task multiple times
    classification1 = classifier.classify_task(issue)
    classification2 = classifier.classify_task(issue)
    classification3 = classifier.classify_task(issue)

    # Verify all classifications are equivalent
    assert (
        classification1.category == classification2.category == classification3.category
    ), "Category must be the same across multiple classifications"

    assert (
        classification1.is_priority_eligible
        == classification2.is_priority_eligible
        == classification3.is_priority_eligible
    ), "is_priority_eligible must be the same across multiple classifications"

    assert (
        classification1.has_dependencies == classification2.has_dependencies == classification3.has_dependencies
    ), "has_dependencies must be the same across multiple classifications"

    assert (
        classification1.estimated_days == classification2.estimated_days == classification3.estimated_days
    ), "estimated_days must be the same across multiple classifications"

    assert (
        classification1.blocking_reason == classification2.blocking_reason == classification3.blocking_reason
    ), "blocking_reason must be the same across multiple classifications"

    # Verify the original issue was not modified
    assert classification1.task is issue, "Original issue must not be modified"
    assert classification2.task is issue, "Original issue must not be modified"
    assert classification3.task is issue, "Original issue must not be modified"


# Property 27: Dependency Detection Completeness
@given(jira_issue_with_dependencies_strategy())
def test_property_27_dependency_detection_completeness(issue: JiraIssue):
    """Property 27: Dependency Detection Completeness

    For any task with third-party dependencies in JIRA metadata (issue links, custom fields),
    the Task_Classifier shall identify all dependencies.

    Feature: ai-secretary, Property 27: Dependency Detection Completeness
    Validates: Requirements 10.1
    """
    classifier = TaskClassifier()

    # Check if the issue actually has dependencies based on our generation
    has_blocking_links = any(
        any(blocking_type in link.link_type.lower() for blocking_type in ["is blocked by", "depends on", "blocked by"])
        for link in issue.issue_links
    )

    has_dependency_custom_fields = any(
        ("external" in field_name.lower() or "dependency" in field_name.lower() or "blocked" in field_name.lower())
        and field_value  # Non-empty value
        for field_name, field_value in issue.custom_fields.items()
    )

    expected_has_dependencies = has_blocking_links or has_dependency_custom_fields

    # Classify the task
    classification = classifier.classify_task(issue)

    # Verify dependency detection
    if expected_has_dependencies:
        assert (
            classification.has_dependencies
        ), f"Task with dependencies was not detected. Links: {issue.issue_links}, Custom fields: {issue.custom_fields}"

    # If has_dependencies is True, verify it's reflected in category or eligibility
    if classification.has_dependencies:
        assert (
            not classification.is_priority_eligible or classification.category == TaskCategory.DEPENDENT
        ), "Tasks with dependencies should not be priority eligible or should be categorized as DEPENDENT"


# Property 5: Administrative Task Grouping (partial - marking aspect)
@given(jira_issue_with_admin_markers_strategy())
def test_property_5_administrative_task_marking(issue: JiraIssue):
    """Property 5: Administrative Task Grouping (partial - marking aspect)

    For any task with administrative labels or issue types, the Task_Classifier
    shall mark it correctly as administrative.

    Feature: ai-secretary, Property 5: Administrative Task Grouping
    Validates: Requirements 2.3
    """
    classifier = TaskClassifier()

    # Check if the issue has admin markers
    admin_labels = {"admin", "administrative", "email", "report", "approval", "meeting", "review"}
    admin_issue_types = {"Administrative Task", "Admin", "Approval", "Review"}

    has_admin_label = any(label.lower() in admin_labels for label in issue.labels)
    has_admin_issue_type = issue.issue_type in admin_issue_types or any(
        keyword in issue.issue_type.lower() for keyword in ["admin", "approval", "review"]
    )

    expected_is_admin = has_admin_label or has_admin_issue_type

    # Classify the task
    classification = classifier.classify_task(issue)

    # Verify administrative marking
    if expected_is_admin:
        # Check if classified as administrative
        actual_is_admin = classifier.is_administrative(issue)
        assert actual_is_admin, f"Task with admin markers was not detected as administrative. Labels: {issue.labels}, Type: {issue.issue_type}"

        # Verify administrative tasks are not priority eligible
        # (unless they also have other disqualifying factors that take precedence)
        if classification.category == TaskCategory.ADMINISTRATIVE:
            assert not classification.is_priority_eligible, "Administrative tasks should not be priority eligible"
