# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for Slack message formatting.

Feature: slack-integration
Properties:
- Property 3: Complete Plan Formatting
- Property 19: JIRA Link Formatting
- Property 21: Urgency Emoji Mapping

Validates: Requirements 2.2, 2.3, 2.4, 2.5, 9.3, 9.5
"""

from datetime import date
from hypothesis import given, strategies as st, assume
from slack_bot.message_formatter import MessageFormatter
from slack_bot.templates import DailyPlanTemplate, BlockingTaskTemplate
from triage.models import (
    JiraIssue,
    TaskClassification,
    TaskCategory,
    DailyPlan,
    AdminBlock,
    IssueLink,
)


# Custom strategies for generating test data

@st.composite
def issue_link_strategy(draw):
    """Generate random IssueLink objects."""
    link_types = ["blocks", "is blocked by", "relates to", "duplicates"]
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
    issue_types = ["Story", "Bug", "Task", "Epic", "Sub-task"]
    priorities = ["Blocker", "High", "Medium", "Low"]
    statuses = ["To Do", "In Progress", "Blocked", "Done"]
    
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
        custom_fields=draw(st.dictionaries(st.text(min_size=1, max_size=20), st.text(min_size=0, max_size=50), max_size=3)),
    )


@st.composite
def task_classification_strategy(draw):
    """Generate random TaskClassification objects."""
    issue = draw(jira_issue_strategy())
    category = draw(st.sampled_from(list(TaskCategory)))
    
    is_priority_eligible = category == TaskCategory.PRIORITY_ELIGIBLE
    has_dependencies = category == TaskCategory.DEPENDENT
    
    if is_priority_eligible:
        estimated_days = draw(st.floats(min_value=0.1, max_value=1.0))
    else:
        estimated_days = draw(st.floats(min_value=0.1, max_value=10.0))
    
    blocking_reason = None
    if category == TaskCategory.BLOCKING:
        blocking_reason = draw(st.text(min_size=10, max_size=100))
    
    return TaskClassification(
        task=issue,
        category=category,
        is_priority_eligible=is_priority_eligible,
        has_dependencies=has_dependencies,
        estimated_days=estimated_days,
        blocking_reason=blocking_reason,
    )


@st.composite
def admin_block_strategy(draw):
    """Generate random AdminBlock objects."""
    num_tasks = draw(st.integers(min_value=0, max_value=5))
    tasks = []
    for _ in range(num_tasks):
        issue = draw(jira_issue_strategy())
        classification = TaskClassification(
            task=issue,
            category=TaskCategory.ADMINISTRATIVE,
            is_priority_eligible=False,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.1, max_value=0.5)),
        )
        tasks.append(classification)
    
    time_allocation = draw(st.integers(min_value=0, max_value=90))
    hour = draw(st.integers(min_value=13, max_value=17))
    start_min = draw(st.integers(min_value=0, max_value=30))
    end_hour = hour + 1 if start_min + time_allocation <= 60 else hour + 2
    end_min = (start_min + time_allocation) % 60
    scheduled_time = f"{hour:02d}:{start_min:02d}-{end_hour:02d}:{end_min:02d}"
    
    return AdminBlock(
        tasks=tasks,
        time_allocation_minutes=time_allocation,
        scheduled_time=scheduled_time,
    )


@st.composite
def daily_plan_strategy(draw):
    """Generate random DailyPlan objects."""
    num_priorities = draw(st.integers(min_value=0, max_value=3))
    priorities = []
    for _ in range(num_priorities):
        issue = draw(jira_issue_strategy())
        classification = TaskClassification(
            task=issue,
            category=TaskCategory.PRIORITY_ELIGIBLE,
            is_priority_eligible=True,
            has_dependencies=False,
            estimated_days=draw(st.floats(min_value=0.1, max_value=1.0)),
        )
        priorities.append(classification)
    
    admin_block = draw(admin_block_strategy())
    
    num_other = draw(st.integers(min_value=0, max_value=10))
    other_tasks = [draw(task_classification_strategy()) for _ in range(num_other)]
    
    previous_closure_rate = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0)))
    
    plan_date = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    
    return DailyPlan(
        date=plan_date,
        priorities=priorities,
        admin_block=admin_block,
        other_tasks=other_tasks,
        previous_closure_rate=previous_closure_rate,
    )


# Property Tests

# Feature: slack-integration, Property 3: Complete Plan Formatting
@given(plan=daily_plan_strategy(), plan_id=st.text(min_size=1, max_size=50))
def test_property_3_complete_plan_formatting(plan, plan_id):
    """
    Property 3: Complete Plan Formatting
    
    For any daily plan with priority tasks and administrative tasks, the
    formatted Block Kit message should contain all required sections:
    - Header with date
    - Priority tasks section with key/summary/urgency/effort
    - Administrative block with time estimate
    - Approval buttons (Approve, Reject, Modify)
    
    Validates: Requirements 2.2, 2.3, 2.4, 2.5
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    message = formatter.format_daily_plan(plan, plan_id)
    
    # Message must have blocks and fallback text
    assert message.blocks is not None
    assert len(message.blocks) > 0
    assert message.text is not None
    assert len(message.text) > 0
    
    blocks = message.blocks
    block_types = [b.get("type") for b in blocks]
    
    # Must have header block
    assert "header" in block_types, "Message must have a header block"
    header_block = next(b for b in blocks if b["type"] == "header")
    assert "text" in header_block
    assert plan.date.strftime('%B %d, %Y') in header_block["text"]["text"]
    
    # Must have approval buttons (actions block)
    assert "actions" in block_types, "Message must have action buttons"
    action_block = next(b for b in blocks if b["type"] == "actions")
    assert "elements" in action_block
    buttons = action_block["elements"]
    assert len(buttons) == 3, "Must have exactly 3 buttons (Approve, Reject, Modify)"
    
    # Verify button action IDs
    action_ids = [btn["action_id"] for btn in buttons]
    assert "approve_plan" in action_ids
    assert "reject_plan" in action_ids
    assert "modify_plan" in action_ids
    
    # Verify button values contain plan_id
    for btn in buttons:
        assert btn["value"] == plan_id
    
    # If priority tasks exist, must display them with all required fields
    if plan.priorities:
        # Find section blocks with fields (task details)
        section_blocks = [b for b in blocks if b["type"] == "section" and "fields" in b]
        
        # Should have at least one section block per priority task
        # (may have more for other content)
        assert len(section_blocks) >= len(plan.priorities), \
            f"Expected at least {len(plan.priorities)} section blocks with fields, got {len(section_blocks)}"
        
        # Check that task information is present in the message
        message_str = str(blocks)
        for classification in plan.priorities:
            task = classification.task
            # Task key should appear in message
            assert task.key in message_str, f"Task key {task.key} not found in message"
    
    # If admin block has tasks, must display them
    if plan.admin_block.tasks:
        message_str = str(blocks)
        # Admin block time allocation should appear
        assert str(plan.admin_block.time_allocation_minutes) in message_str, \
            "Admin block time allocation not found in message"
        
        # At least one admin task key should appear
        admin_keys = [t.task.key for t in plan.admin_block.tasks]
        assert any(key in message_str for key in admin_keys), \
            "No admin task keys found in message"


# Feature: slack-integration, Property 19: JIRA Link Formatting
@given(issue=jira_issue_strategy())
def test_property_19_jira_link_formatting(issue):
    """
    Property 19: JIRA Link Formatting
    
    For any JIRA task key displayed in a message, it should be formatted
    as a clickable link to the corresponding JIRA issue.
    
    Validates: Requirements 9.3
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Create a link using the formatter
    link = formatter.create_jira_link(issue.key)
    
    # Link should be in Slack markdown format: <url|text>
    assert link.startswith("<"), "Link should start with <"
    assert link.endswith(">"), "Link should end with >"
    assert "|" in link, "Link should contain | separator"
    
    # Extract URL and text
    link_content = link[1:-1]  # Remove < and >
    url, text = link_content.split("|")
    
    # URL should point to JIRA browse page
    assert url == f"https://jira.example.com/browse/{issue.key}", \
        f"Expected URL to be https://jira.example.com/browse/{issue.key}, got {url}"
    
    # Text should be the issue key
    assert text == issue.key, f"Expected link text to be {issue.key}, got {text}"


# Feature: slack-integration, Property 21: Urgency Emoji Mapping
@given(urgency=st.sampled_from(["Blocker", "High", "Medium", "Low"]))
def test_property_21_urgency_emoji_mapping(urgency):
    """
    Property 21: Urgency Emoji Mapping
    
    For any task with an urgency level, the displayed message should include
    the correct emoji indicator:
    - Blocker/High: 🔴
    - Medium: 🟡
    - Low: 🟢
    
    Validates: Requirements 9.5
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Get emoji for urgency level
    emoji = formatter.format_urgency_emoji(urgency)
    
    # Verify correct emoji mapping
    if urgency in ("Blocker", "High"):
        assert emoji == "🔴", f"Expected 🔴 for {urgency}, got {emoji}"
    elif urgency == "Medium":
        assert emoji == "🟡", f"Expected 🟡 for Medium, got {emoji}"
    elif urgency == "Low":
        assert emoji == "🟢", f"Expected 🟢 for Low, got {emoji}"
    
    # Verify emoji is actually an emoji (non-empty string)
    assert len(emoji) > 0, "Emoji should not be empty"


# Additional property: Urgency emoji appears in formatted plan
@given(plan=daily_plan_strategy(), plan_id=st.text(min_size=1, max_size=50))
def test_urgency_emoji_in_formatted_plan(plan, plan_id):
    """
    Verify that urgency emojis appear in formatted daily plans.
    
    For any plan with priority tasks, the formatted message should contain
    the appropriate urgency emoji for each task.
    """
    assume(len(plan.priorities) > 0)  # Only test plans with priorities
    
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    message = formatter.format_daily_plan(plan, plan_id)
    
    message_str = str(message.blocks)
    
    # Check that at least one urgency emoji appears
    urgency_emojis = ["🔴", "🟡", "🟢"]
    assert any(emoji in message_str for emoji in urgency_emojis), \
        "No urgency emojis found in formatted plan"
    
    # For each priority task, verify its urgency emoji appears
    for classification in plan.priorities:
        task = classification.task
        expected_emoji = formatter.format_urgency_emoji(task.priority)
        
        # The emoji should appear somewhere in the message
        # (we don't check exact position, just presence)
        assert expected_emoji in message_str, \
            f"Expected emoji {expected_emoji} for task {task.key} with priority {task.priority}"


# Feature: slack-integration, Property: Effort Estimate Formatting
@given(effort_days=st.floats(min_value=0.01, max_value=10.0))
def test_effort_estimate_formatting(effort_days):
    """
    Verify that effort estimates are formatted in human-readable units.
    
    For any effort estimate in days, the formatter should convert it to
    appropriate units (minutes, hours, or days).
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    effort_str = formatter.format_effort(effort_days)
    
    # Result should be a non-empty string
    assert len(effort_str) > 0, "Effort string should not be empty"
    
    # Should contain a unit
    units = ["min", "hour", "day"]
    assert any(unit in effort_str for unit in units), \
        f"Effort string '{effort_str}' should contain a time unit"
    
    # Verify correct unit based on effort
    if effort_days < 0.125:  # Less than 1 hour
        assert "min" in effort_str, f"Expected 'min' for {effort_days} days, got {effort_str}"
    elif effort_days < 1.0:
        assert "hour" in effort_str, f"Expected 'hour' for {effort_days} days, got {effort_str}"
    else:
        assert "day" in effort_str, f"Expected 'day' for {effort_days} days, got {effort_str}"


# Feature: slack-integration, Property: Text Truncation
@given(text=st.text(min_size=1, max_size=1000), max_length=st.integers(min_value=10, max_value=500))
def test_text_truncation(text, max_length):
    """
    Verify that long text is truncated correctly with ellipsis.
    
    For any text exceeding the maximum length, the truncated version should:
    - Be at most max_length characters
    - End with "..." if truncated
    - Preserve original text if within limit
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    truncated = formatter.truncate_text(text, max_length)
    
    # Truncated text should not exceed max_length
    assert len(truncated) <= max_length, \
        f"Truncated text length {len(truncated)} exceeds max {max_length}"
    
    if len(text) <= max_length:
        # Text should be unchanged
        assert truncated == text, "Text within limit should not be modified"
    else:
        # Text should be truncated with ellipsis
        assert truncated.endswith("..."), "Truncated text should end with ..."
        assert len(truncated) == max_length, \
            f"Truncated text should be exactly {max_length} chars"
        
        # Truncated text (minus ellipsis) should be prefix of original
        assert text.startswith(truncated[:-3]), \
            "Truncated text should be a prefix of original"
