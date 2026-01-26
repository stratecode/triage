# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for blocking task notifications.

Feature: slack-integration
Properties:
- Property 8: Complete Blocking Task Notifications
- Property 9: Blocking Task Grouping
- Property 10: Blocking Task Resolution Notifications

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
"""

from hypothesis import given, strategies as st, assume
from slack_bot.message_formatter import MessageFormatter
from slack_bot.templates import BlockingTaskTemplate, BlockingTaskResolvedTemplate
from triage.models import JiraIssue, IssueLink


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
def blocker_reason_strategy(draw):
    """Generate random blocker reasons."""
    reasons = [
        "Waiting for external dependency",
        "Blocked by another task",
        "Missing required information",
        "Waiting for approval",
        "Technical blocker",
        "Resource unavailable",
    ]
    return draw(st.sampled_from(reasons))


# Property Tests

# Feature: slack-integration, Property 8: Complete Blocking Task Notifications
@given(
    task=jira_issue_strategy(),
    blocker_reason=blocker_reason_strategy()
)
def test_property_8_complete_blocking_task_notifications(task, blocker_reason):
    """
    Property 8: Complete Blocking Task Notifications
    
    For any blocking task detection, the notification should include:
    - Task key (as clickable JIRA link)
    - Summary
    - Blocker reason
    - Urgency level (with emoji)
    - Re-planning action button
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    message = formatter.format_blocking_task_alert(task, blocker_reason)
    
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
    assert "Blocking Task" in header_block["text"]["text"]
    
    # Must have re-planning action button
    assert "actions" in block_types, "Message must have action buttons"
    action_block = next(b for b in blocks if b["type"] == "actions")
    assert "elements" in action_block
    buttons = action_block["elements"]
    assert len(buttons) >= 1, "Must have at least one button"
    
    # Verify re-planning button exists
    replan_button = next((btn for btn in buttons if btn["action_id"] == "replan_blocking"), None)
    assert replan_button is not None, "Must have re-planning button"
    assert replan_button["value"] == task.key, "Button value should be task key"
    
    # Convert blocks to string for content verification
    # Check task key appears in blocks
    task_key_found = any(
        task.key in str(block)
        for block in blocks
    )
    assert task_key_found, f"Task key {task.key} not found in message"
    
    # Summary must appear in message (check in blocks directly to avoid escaping issues)
    summary_found = any(
        task.summary in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert summary_found, f"Task summary not found in message"
    
    # Blocker reason must appear in message
    blocker_found = any(
        blocker_reason in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert blocker_found, f"Blocker reason not found in message"
    
    # Urgency level must appear in message
    priority_found = any(
        task.priority in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert priority_found, f"Task priority {task.priority} not found in message"
    
    # Urgency emoji must appear in message
    urgency_emojis = ["🔴", "🟡", "🟢"]
    emoji_found = any(
        any(emoji in str(field.get('text', '')) for emoji in urgency_emojis)
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert emoji_found, "No urgency emoji found in message"
    
    # Verify JIRA link format
    expected_url = f"https://jira.example.com/browse/{task.key}"
    url_found = any(
        expected_url in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert url_found, f"JIRA URL {expected_url} not found in message"


# Feature: slack-integration, Property 9: Blocking Task Grouping
@given(
    primary_task=jira_issue_strategy(),
    blocker_reason=blocker_reason_strategy(),
    num_additional=st.integers(min_value=1, max_value=5)
)
def test_property_9_blocking_task_grouping(primary_task, blocker_reason, num_additional):
    """
    Property 9: Blocking Task Grouping
    
    For any set of multiple blocking tasks detected simultaneously, they
    should be grouped into a single notification message rather than sent
    as separate messages.
    
    The grouped notification should:
    - Display count of blocking tasks in header
    - Show primary task details
    - List additional blocking tasks
    - Have single re-planning button
    
    Validates: Requirements 5.4
    """
    # Generate additional blocking tasks
    additional_tasks = [
        JiraIssue(
            key=f"PROJ-{i}",
            summary=f"Additional blocking task {i}",
            description="",
            issue_type="Task",
            priority="High",
            status="Blocked",
            assignee="user@example.com",
            story_points=None,
            time_estimate=None,
            labels=[],
            issue_links=[],
            custom_fields={},
        )
        for i in range(1, num_additional + 1)
    ]
    
    # Create grouped notification
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    message = formatter.format_blocking_task_alert(
        task=primary_task,
        blocker_reason=blocker_reason,
        tasks=[primary_task] + additional_tasks
    )
    
    # Message must have blocks
    assert message.blocks is not None
    assert len(message.blocks) > 0
    
    blocks = message.blocks
    
    # Header should indicate multiple tasks
    header_block = next(b for b in blocks if b["type"] == "header")
    header_text = header_block["text"]["text"]
    
    # Should mention count of tasks
    total_tasks = 1 + num_additional
    assert str(total_tasks) in header_text, \
        f"Header should mention {total_tasks} tasks"
    
    # Primary task details should be present
    task_key_found = any(
        primary_task.key in str(block)
        for block in blocks
    )
    assert task_key_found, f"Primary task key not found in message"
    
    # Check summary in blocks directly to avoid escaping issues
    summary_found = any(
        primary_task.summary in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert summary_found, f"Primary task summary not found in message"
    
    blocker_found = any(
        blocker_reason in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert blocker_found, f"Blocker reason not found in message"
    
    # Additional tasks should be listed
    for additional_task in additional_tasks:
        task_found = any(
            additional_task.key in str(block)
            for block in blocks
        )
        assert task_found, \
            f"Additional task {additional_task.key} not found in grouped message"
    
    # Should have exactly one re-planning button (not one per task)
    action_blocks = [b for b in blocks if b["type"] == "actions"]
    assert len(action_blocks) == 1, \
        "Grouped notification should have exactly one actions block"
    
    buttons = action_blocks[0]["elements"]
    replan_buttons = [btn for btn in buttons if btn["action_id"] == "replan_blocking"]
    assert len(replan_buttons) == 1, \
        "Grouped notification should have exactly one re-planning button"


# Feature: slack-integration, Property 10: Blocking Task Resolution Notifications
@given(task=jira_issue_strategy())
def test_property_10_blocking_task_resolution_notifications(task):
    """
    Property 10: Blocking Task Resolution Notifications
    
    For any blocking task that transitions to resolved state, a follow-up
    notification should be sent to inform the user of the resolution.
    
    The resolution notification should:
    - Have success/resolved indicator in header
    - Display task key (as clickable link)
    - Display task summary
    - Display urgency level
    - Indicate task is no longer blocking
    
    Validates: Requirements 5.5
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    message = formatter.format_blocking_task_resolved(task)
    
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
    header_text = header_block["text"]["text"]
    
    # Header should indicate resolution
    resolution_indicators = ["Resolved", "resolved", "✅"]
    assert any(indicator in header_text for indicator in resolution_indicators), \
        "Header should indicate task is resolved"
    
    # Convert blocks to string for content verification
    # Task key must appear in message
    task_key_found = any(
        task.key in str(block)
        for block in blocks
    )
    assert task_key_found, f"Task key {task.key} not found in message"
    
    # Summary must appear in message (check in blocks directly to avoid escaping issues)
    summary_found = any(
        task.summary in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert summary_found, f"Task summary not found in message"
    
    # Urgency level must appear in message
    priority_found = any(
        task.priority in str(field.get('text', ''))
        for block in blocks
        if block.get('type') == 'section' and 'fields' in block
        for field in block.get('fields', [])
    )
    assert priority_found, f"Task priority not found in message"
    
    # Should indicate task is no longer blocking
    no_longer_blocking_indicators = [
        "no longer blocking",
        "resolved",
        "unblocked",
    ]
    blocking_indicator_found = any(
        any(indicator in str(block).lower() for indicator in no_longer_blocking_indicators)
        for block in blocks
    )
    assert blocking_indicator_found, \
        "Message should indicate task is no longer blocking"
    
    # Verify JIRA link format
    expected_url = f"https://jira.example.com/browse/{task.key}"
    url_found = any(
        expected_url in str(block)
        for block in blocks
    )
    assert url_found, f"JIRA URL {expected_url} not found in message"
    
    # Fallback text should indicate resolution
    assert any(indicator in message.text for indicator in resolution_indicators), \
        "Fallback text should indicate resolution"


# Additional property: Blocking task template consistency
@given(
    task=jira_issue_strategy(),
    blocker_reason=blocker_reason_strategy()
)
def test_blocking_task_template_consistency(task, blocker_reason):
    """
    Verify that BlockingTaskTemplate produces consistent output.
    
    For any task and blocker reason, the template should produce a valid
    SlackMessage with all required components.
    """
    template = BlockingTaskTemplate(jira_base_url="https://jira.example.com")
    message = template.render(task=task, blocker_reason=blocker_reason)
    
    # Message should have blocks and text
    assert message.blocks is not None
    assert len(message.blocks) > 0
    assert message.text is not None
    assert len(message.text) > 0
    
    # All blocks should have a type
    for block in message.blocks:
        assert "type" in block, "Each block must have a type"
        assert block["type"] in ["header", "section", "divider", "actions", "context"], \
            f"Invalid block type: {block['type']}"


# Additional property: Resolution template consistency
@given(task=jira_issue_strategy())
def test_resolution_template_consistency(task):
    """
    Verify that BlockingTaskResolvedTemplate produces consistent output.
    
    For any resolved task, the template should produce a valid SlackMessage
    with all required components.
    """
    template = BlockingTaskResolvedTemplate(jira_base_url="https://jira.example.com")
    message = template.render(task=task)
    
    # Message should have blocks and text
    assert message.blocks is not None
    assert len(message.blocks) > 0
    assert message.text is not None
    assert len(message.text) > 0
    
    # All blocks should have a type
    for block in message.blocks:
        assert "type" in block, "Each block must have a type"
        assert block["type"] in ["header", "section", "divider", "actions", "context"], \
            f"Invalid block type: {block['type']}"
    
    # Should not have action buttons (resolution is informational only)
    action_blocks = [b for b in message.blocks if b["type"] == "actions"]
    assert len(action_blocks) == 0, \
        "Resolution notification should not have action buttons"
