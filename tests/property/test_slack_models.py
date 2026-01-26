# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for Slack data models.

Feature: slack-integration
Property: For any Slack user model with valid fields, serialization then 
deserialization produces equivalent object.

Validates: Requirements 8.1
"""

from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume
from slack_bot.models import (
    SlackUser,
    SlackConfig,
    WebhookEvent,
    SlackMessage,
    PendingFeedback,
    WebhookDeduplication,
    WorkspaceToken,
    SlashCommand,
    BlockAction,
    ErrorContext,
)


# Custom strategies for generating Slack-specific data

@st.composite
def slack_user_id_strategy(draw):
    """Generate valid Slack user IDs (format: U + 8-11 alphanumeric chars)."""
    length = draw(st.integers(min_value=8, max_value=11))
    # Use only uppercase letters A-Z and digits 0-9
    chars = ''.join(draw(st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')) for _ in range(length))
    return f"U{chars}"


@st.composite
def slack_team_id_strategy(draw):
    """Generate valid Slack team IDs (format: T + 8-11 alphanumeric chars)."""
    length = draw(st.integers(min_value=8, max_value=11))
    # Use only uppercase letters A-Z and digits 0-9
    chars = ''.join(draw(st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')) for _ in range(length))
    return f"T{chars}"


@st.composite
def slack_channel_id_strategy(draw):
    """Generate valid Slack channel IDs or 'DM'."""
    use_dm = draw(st.booleans())
    if use_dm:
        return "DM"
    else:
        length = draw(st.integers(min_value=8, max_value=11))
        # Use only uppercase letters A-Z and digits 0-9
        chars = ''.join(draw(st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')) for _ in range(length))
        return f"C{chars}"


@st.composite
def time_string_strategy(draw):
    """Generate valid HH:MM time strings."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def slack_user_strategy(draw):
    """Generate valid SlackUser objects."""
    return SlackUser(
        slack_user_id=draw(slack_user_id_strategy()),
        slack_team_id=draw(slack_team_id_strategy()),
        triage_user_id=draw(st.text(min_size=1, max_size=50)),
        jira_email=draw(st.emails()),
        display_name=draw(st.text(min_size=1, max_size=100)),
    )


@st.composite
def slack_config_strategy(draw):
    """Generate valid SlackConfig objects."""
    return SlackConfig(
        user_id=draw(st.text(min_size=1, max_size=50)),
        notification_channel=draw(slack_channel_id_strategy()),
        delivery_time=draw(time_string_strategy()),
        notifications_enabled=draw(st.booleans()),
        timezone=draw(st.sampled_from([
            "UTC", "America/New_York", "America/Los_Angeles",
            "Europe/London", "Europe/Paris", "Asia/Tokyo"
        ])),
    )


@st.composite
def webhook_event_strategy(draw):
    """Generate valid WebhookEvent objects."""
    event_types = [
        'slash_command', 'block_action', 'message',
        'app_mention', 'view_submission', 'view_closed'
    ]
    return WebhookEvent(
        event_id=draw(st.uuids()).hex,
        event_type=draw(st.sampled_from(event_types)),
        user_id=draw(slack_user_id_strategy()),
        team_id=draw(slack_team_id_strategy()),
        payload=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(), st.integers(), st.booleans()),
            max_size=10
        )),
        timestamp=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        )),
    )


@st.composite
def block_strategy(draw):
    """Generate valid Block Kit blocks."""
    block_types = ['header', 'section', 'divider', 'actions', 'context']
    block_type = draw(st.sampled_from(block_types))
    
    block = {'type': block_type}
    
    if block_type == 'header':
        block['text'] = {
            'type': 'plain_text',
            'text': draw(st.text(min_size=1, max_size=150))
        }
    elif block_type == 'section':
        block['text'] = {
            'type': 'mrkdwn',
            'text': draw(st.text(min_size=1, max_size=3000))
        }
    
    return block


@st.composite
def slack_message_strategy(draw):
    """Generate valid SlackMessage objects."""
    num_blocks = draw(st.integers(min_value=0, max_value=10))
    blocks = [draw(block_strategy()) for _ in range(num_blocks)]
    
    return SlackMessage(
        blocks=blocks,
        text=draw(st.text(min_size=1, max_size=500)),
        thread_ts=draw(st.one_of(
            st.none(),
            st.text(min_size=10, max_size=20, alphabet=st.characters(whitelist_categories=("Nd", "P")))
        )),
        channel=draw(st.one_of(st.none(), slack_channel_id_strategy())),
    )


@st.composite
def pending_feedback_strategy(draw):
    """Generate valid PendingFeedback objects."""
    created = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    expires = created + timedelta(minutes=30)
    
    return PendingFeedback(
        feedback_id=draw(st.uuids()).hex,
        user_id=draw(slack_user_id_strategy()),
        plan_id=draw(st.text(min_size=1, max_size=50)),
        thread_ts=draw(st.text(min_size=10, max_size=20)),
        created_at=created,
        expires_at=expires,
        reminder_sent=draw(st.booleans()),
    )


@st.composite
def webhook_deduplication_strategy(draw):
    """Generate valid WebhookDeduplication objects."""
    return WebhookDeduplication(
        event_id=draw(st.uuids()).hex,
        processed_at=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        )),
        ttl=draw(st.integers(min_value=60, max_value=3600)),
    )


@st.composite
def workspace_token_strategy(draw):
    """Generate valid WorkspaceToken objects."""
    return WorkspaceToken(
        team_id=draw(slack_team_id_strategy()),
        access_token=draw(st.text(min_size=20, max_size=200)),
        bot_user_id=draw(slack_user_id_strategy()),
        scope=draw(st.text(min_size=1, max_size=500)),
        installed_at=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        )),
    )


@st.composite
def slash_command_strategy(draw):
    """Generate valid SlashCommand objects."""
    commands = ['/triage', '/triagebot', '/ai-secretary']
    return SlashCommand(
        command=draw(st.sampled_from(commands)),
        text=draw(st.text(max_size=500)),
        user_id=draw(slack_user_id_strategy()),
        team_id=draw(slack_team_id_strategy()),
        channel_id=draw(slack_channel_id_strategy()),
        response_url=draw(st.from_regex(r'https://hooks\.slack\.com/commands/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+')),
    )


@st.composite
def block_action_strategy(draw):
    """Generate valid BlockAction objects."""
    action_ids = ['approve_plan', 'reject_plan', 'modify_plan', 'replan_blocking']
    return BlockAction(
        action_id=draw(st.sampled_from(action_ids)),
        value=draw(st.text(min_size=1, max_size=100)),
        user_id=draw(slack_user_id_strategy()),
        team_id=draw(slack_team_id_strategy()),
        message_ts=draw(st.text(min_size=10, max_size=20)),
        response_url=draw(st.from_regex(r'https://hooks\.slack\.com/actions/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+')),
        channel_id=draw(st.one_of(st.none(), slack_channel_id_strategy())),
    )


@st.composite
def error_context_strategy(draw):
    """Generate valid ErrorContext objects."""
    error_types = [
        'api_unavailable', 'invalid_command', 'not_configured',
        'rate_limited', 'unauthorized', 'network_error'
    ]
    return ErrorContext(
        error_type=draw(st.sampled_from(error_types)),
        message=draw(st.text(min_size=1, max_size=500)),
        suggestion=draw(st.text(min_size=1, max_size=500)),
        user_id=draw(st.one_of(st.none(), slack_user_id_strategy())),
        context=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(), st.integers(), st.booleans()),
            max_size=10
        )),
        timestamp=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        )),
    )


# Property Tests

# Feature: slack-integration, Property: SlackUser Serialization Roundtrip
@given(user=slack_user_strategy())
def test_slack_user_serialization_roundtrip(user):
    """
    For any SlackUser with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 8.1
    """
    # Serialize to dict
    user_dict = user.model_dump()
    
    # Deserialize back to object
    user_restored = SlackUser(**user_dict)
    
    # Objects should be equivalent
    assert user == user_restored
    assert user.slack_user_id == user_restored.slack_user_id
    assert user.slack_team_id == user_restored.slack_team_id
    assert user.triage_user_id == user_restored.triage_user_id
    assert user.jira_email == user_restored.jira_email
    assert user.display_name == user_restored.display_name


# Feature: slack-integration, Property: SlackConfig Serialization Roundtrip
@given(config=slack_config_strategy())
def test_slack_config_serialization_roundtrip(config):
    """
    For any SlackConfig with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 10.2
    """
    # Serialize to dict
    config_dict = config.model_dump()
    
    # Deserialize back to object
    config_restored = SlackConfig(**config_dict)
    
    # Objects should be equivalent
    assert config == config_restored
    assert config.user_id == config_restored.user_id
    assert config.notification_channel == config_restored.notification_channel
    assert config.delivery_time == config_restored.delivery_time
    assert config.notifications_enabled == config_restored.notifications_enabled
    assert config.timezone == config_restored.timezone


# Feature: slack-integration, Property: WebhookEvent Serialization Roundtrip
@given(event=webhook_event_strategy())
def test_webhook_event_serialization_roundtrip(event):
    """
    For any WebhookEvent with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 7.1, 7.2, 7.3
    """
    # Serialize to dict
    event_dict = event.model_dump()
    
    # Deserialize back to object
    event_restored = WebhookEvent(**event_dict)
    
    # Objects should be equivalent
    assert event.event_id == event_restored.event_id
    assert event.event_type == event_restored.event_type
    assert event.user_id == event_restored.user_id
    assert event.team_id == event_restored.team_id
    assert event.payload == event_restored.payload


# Feature: slack-integration, Property: SlackMessage Serialization Roundtrip
@given(message=slack_message_strategy())
def test_slack_message_serialization_roundtrip(message):
    """
    For any SlackMessage with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 2.2, 9.1
    """
    # Serialize to dict
    message_dict = message.model_dump()
    
    # Deserialize back to object
    message_restored = SlackMessage(**message_dict)
    
    # Objects should be equivalent
    assert message.blocks == message_restored.blocks
    assert message.text == message_restored.text
    assert message.thread_ts == message_restored.thread_ts
    assert message.channel == message_restored.channel


# Feature: slack-integration, Property: PendingFeedback Serialization Roundtrip
@given(feedback=pending_feedback_strategy())
def test_pending_feedback_serialization_roundtrip(feedback):
    """
    For any PendingFeedback with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 6.1, 6.2, 6.3
    """
    # Serialize to dict
    feedback_dict = feedback.model_dump()
    
    # Deserialize back to object
    feedback_restored = PendingFeedback(**feedback_dict)
    
    # Objects should be equivalent
    assert feedback.feedback_id == feedback_restored.feedback_id
    assert feedback.user_id == feedback_restored.user_id
    assert feedback.plan_id == feedback_restored.plan_id
    assert feedback.thread_ts == feedback_restored.thread_ts
    assert feedback.reminder_sent == feedback_restored.reminder_sent


# Feature: slack-integration, Property: WebhookDeduplication Serialization Roundtrip
@given(dedup=webhook_deduplication_strategy())
def test_webhook_deduplication_serialization_roundtrip(dedup):
    """
    For any WebhookDeduplication with valid fields, serialization then
    deserialization produces an equivalent object.
    
    Validates: Requirements 7.4
    """
    # Serialize to dict
    dedup_dict = dedup.model_dump()
    
    # Deserialize back to object
    dedup_restored = WebhookDeduplication(**dedup_dict)
    
    # Objects should be equivalent
    assert dedup.event_id == dedup_restored.event_id
    assert dedup.ttl == dedup_restored.ttl


# Feature: slack-integration, Property: WorkspaceToken Serialization Roundtrip
@given(token=workspace_token_strategy())
def test_workspace_token_serialization_roundtrip(token):
    """
    For any WorkspaceToken with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 1.2, 12.1
    """
    # Serialize to dict
    token_dict = token.model_dump()
    
    # Deserialize back to object
    token_restored = WorkspaceToken(**token_dict)
    
    # Objects should be equivalent
    assert token.team_id == token_restored.team_id
    assert token.access_token == token_restored.access_token
    assert token.bot_user_id == token_restored.bot_user_id
    assert token.scope == token_restored.scope


# Feature: slack-integration, Property: SlashCommand Serialization Roundtrip
@given(command=slash_command_strategy())
def test_slash_command_serialization_roundtrip(command):
    """
    For any SlashCommand with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 4.1, 4.2, 4.3
    """
    # Serialize to dict
    command_dict = command.model_dump()
    
    # Deserialize back to object
    command_restored = SlashCommand(**command_dict)
    
    # Objects should be equivalent
    assert command.command == command_restored.command
    assert command.text == command_restored.text
    assert command.user_id == command_restored.user_id
    assert command.team_id == command_restored.team_id
    assert command.channel_id == command_restored.channel_id
    assert command.response_url == command_restored.response_url


# Feature: slack-integration, Property: BlockAction Serialization Roundtrip
@given(action=block_action_strategy())
def test_block_action_serialization_roundtrip(action):
    """
    For any BlockAction with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 3.2, 3.3, 3.4, 3.5
    """
    # Serialize to dict
    action_dict = action.model_dump()
    
    # Deserialize back to object
    action_restored = BlockAction(**action_dict)
    
    # Objects should be equivalent
    assert action.action_id == action_restored.action_id
    assert action.value == action_restored.value
    assert action.user_id == action_restored.user_id
    assert action.team_id == action_restored.team_id
    assert action.message_ts == action_restored.message_ts
    assert action.response_url == action_restored.response_url
    assert action.channel_id == action_restored.channel_id


# Feature: slack-integration, Property: ErrorContext Serialization Roundtrip
@given(error=error_context_strategy())
def test_error_context_serialization_roundtrip(error):
    """
    For any ErrorContext with valid fields, serialization then deserialization
    produces an equivalent object.
    
    Validates: Requirements 11.3, 11.5
    """
    # Serialize to dict
    error_dict = error.model_dump()
    
    # Deserialize back to object
    error_restored = ErrorContext(**error_dict)
    
    # Objects should be equivalent
    assert error.error_type == error_restored.error_type
    assert error.message == error_restored.message
    assert error.suggestion == error_restored.suggestion
    assert error.user_id == error_restored.user_id
    assert error.context == error_restored.context
