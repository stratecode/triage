# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for user identification consistency.

Feature: slack-integration, Property 15: User Identification Consistency

For any user interaction (command, button click, message), the system should
correctly identify the user by their Slack user ID and use it for all
subsequent API calls.

Validates: Requirements 8.1
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timezone
from slack_bot.models import SlackUser, WebhookEvent, SlashCommand, BlockAction
from slack_bot.user_middleware import UserIdentificationMiddleware, UserMapper
from slack_bot.user_storage import UserMappingStorage


# Custom strategies for generating test data

@st.composite
def slack_user_id_strategy(draw):
    """Generate valid Slack user IDs."""
    # Slack user IDs start with 'U' followed by 8-11 alphanumeric characters (ASCII only)
    length = draw(st.integers(min_value=8, max_value=11))
    chars = ''.join(draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=length,
        max_size=length
    )))
    return f"U{chars}"


@st.composite
def slack_team_id_strategy(draw):
    """Generate valid Slack team IDs."""
    # Slack team IDs start with 'T' followed by 8-11 alphanumeric characters (ASCII only)
    length = draw(st.integers(min_value=8, max_value=11))
    chars = ''.join(draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=length,
        max_size=length
    )))
    return f"T{chars}"


@st.composite
def slack_user_strategy(draw):
    """Generate SlackUser instances."""
    return SlackUser(
        slack_user_id=draw(slack_user_id_strategy()),
        slack_team_id=draw(slack_team_id_strategy()),
        triage_user_id=draw(st.text(min_size=5, max_size=50)),
        jira_email=draw(st.emails()),
        display_name=draw(st.text(min_size=1, max_size=100))
    )


@st.composite
def webhook_event_strategy(draw, user_id=None, team_id=None):
    """Generate WebhookEvent instances."""
    return WebhookEvent(
        event_id=draw(st.uuids()).hex,
        event_type=draw(st.sampled_from([
            "slash_command", "block_action", "message", "app_mention"
        ])),
        user_id=user_id or draw(slack_user_id_strategy()),
        team_id=team_id or draw(slack_team_id_strategy()),
        payload=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(min_size=1, max_size=50),
            min_size=0,
            max_size=5
        )),
        timestamp=datetime.now(timezone.utc)
    )


@st.composite
def slash_command_strategy(draw, user_id=None, team_id=None):
    """Generate SlashCommand instances."""
    return SlashCommand(
        command="/triage",
        text=draw(st.sampled_from(["plan", "status", "help", "config"])),
        user_id=user_id or draw(slack_user_id_strategy()),
        team_id=team_id or draw(slack_team_id_strategy()),
        channel_id=draw(st.text(min_size=9, max_size=11).map(lambda s: f"C{s}")),
        response_url=draw(st.from_regex(r"https://hooks\.slack\.com/.*", fullmatch=True))
    )


@st.composite
def block_action_strategy(draw, user_id=None, team_id=None):
    """Generate BlockAction instances."""
    return BlockAction(
        action_id=draw(st.sampled_from([
            "approve_plan", "reject_plan", "modify_plan", "replan_blocking"
        ])),
        value=draw(st.text(min_size=5, max_size=50)),
        user_id=user_id or draw(slack_user_id_strategy()),
        team_id=team_id or draw(slack_team_id_strategy()),
        message_ts=draw(st.text(min_size=10, max_size=20)),
        response_url=draw(st.from_regex(r"https://hooks\.slack\.com/.*", fullmatch=True)),
        channel_id=draw(st.text(min_size=9, max_size=11).map(lambda s: f"C{s}"))
    )


# Mock storage for testing
class MockUserMappingStorage:
    """Mock storage for user mappings."""
    
    def __init__(self):
        self.mappings = {}
    
    async def get_mapping(self, slack_user_id: str, slack_team_id: str):
        key = (slack_user_id, slack_team_id)
        return self.mappings.get(key)
    
    async def create_mapping(self, slack_user: SlackUser):
        key = (slack_user.slack_user_id, slack_user.slack_team_id)
        if key in self.mappings:
            raise ValueError("Mapping already exists")
        self.mappings[key] = slack_user
        return slack_user
    
    async def update_mapping(self, slack_user_id: str, slack_team_id: str, **kwargs):
        key = (slack_user_id, slack_team_id)
        if key not in self.mappings:
            return None
        user = self.mappings[key]
        if 'jira_email' in kwargs and kwargs['jira_email'] is not None:
            user.jira_email = kwargs['jira_email']
        if 'display_name' in kwargs and kwargs['display_name'] is not None:
            user.display_name = kwargs['display_name']
        return user
    
    async def delete_mapping(self, slack_user_id: str, slack_team_id: str):
        key = (slack_user_id, slack_team_id)
        if key in self.mappings:
            del self.mappings[key]
            return True
        return False
    
    async def list_workspace_mappings(self, slack_team_id: str):
        return [
            user for (uid, tid), user in self.mappings.items()
            if tid == slack_team_id
        ]


# Property Tests

# Feature: slack-integration, Property 15: User Identification Consistency
@settings(max_examples=100)
@given(
    slack_user=slack_user_strategy(),
    event=webhook_event_strategy()
)
@pytest.mark.asyncio
async def test_user_identification_consistency_webhook_event(slack_user, event):
    """
    Property 15: User Identification Consistency (WebhookEvent)
    
    For any WebhookEvent with a valid user ID, the middleware should
    consistently extract the same user ID and map it to the correct
    TrIAge user.
    
    Validates: Requirements 8.1
    """
    # Setup
    storage = MockUserMappingStorage()
    await storage.create_mapping(slack_user)
    
    mapper = UserMapper(storage)
    middleware = UserIdentificationMiddleware(mapper)
    
    # Override event IDs to match the user
    event.user_id = slack_user.slack_user_id
    event.team_id = slack_user.slack_team_id
    
    # Extract user ID
    extracted_user_id = middleware.extract_user_id(event)
    extracted_team_id = middleware.extract_team_id(event)
    
    # Property: Extracted IDs match the event's IDs
    assert extracted_user_id == slack_user.slack_user_id
    assert extracted_team_id == slack_user.slack_team_id
    
    # Identify user
    identified_user = await middleware.identify_user(event)
    
    # Property: Identified user matches the original user
    assert identified_user is not None
    assert identified_user.slack_user_id == slack_user.slack_user_id
    assert identified_user.slack_team_id == slack_user.slack_team_id
    assert identified_user.triage_user_id == slack_user.triage_user_id
    assert identified_user.jira_email == slack_user.jira_email


# Feature: slack-integration, Property 15: User Identification Consistency
@settings(max_examples=100)
@given(
    slack_user=slack_user_strategy(),
    command=slash_command_strategy()
)
@pytest.mark.asyncio
async def test_user_identification_consistency_slash_command(slack_user, command):
    """
    Property 15: User Identification Consistency (SlashCommand)
    
    For any SlashCommand with a valid user ID, the middleware should
    consistently extract the same user ID and map it to the correct
    TrIAge user.
    
    Validates: Requirements 8.1
    """
    # Setup
    storage = MockUserMappingStorage()
    await storage.create_mapping(slack_user)
    
    mapper = UserMapper(storage)
    middleware = UserIdentificationMiddleware(mapper)
    
    # Override command IDs to match the user
    command.user_id = slack_user.slack_user_id
    command.team_id = slack_user.slack_team_id
    
    # Extract user ID
    extracted_user_id = middleware.extract_user_id(command)
    extracted_team_id = middleware.extract_team_id(command)
    
    # Property: Extracted IDs match the command's IDs
    assert extracted_user_id == slack_user.slack_user_id
    assert extracted_team_id == slack_user.slack_team_id
    
    # Identify user
    identified_user = await middleware.identify_user(command)
    
    # Property: Identified user matches the original user
    assert identified_user is not None
    assert identified_user.slack_user_id == slack_user.slack_user_id
    assert identified_user.slack_team_id == slack_user.slack_team_id
    assert identified_user.triage_user_id == slack_user.triage_user_id
    assert identified_user.jira_email == slack_user.jira_email


# Feature: slack-integration, Property 15: User Identification Consistency
@settings(max_examples=100)
@given(
    slack_user=slack_user_strategy(),
    action=block_action_strategy()
)
@pytest.mark.asyncio
async def test_user_identification_consistency_block_action(slack_user, action):
    """
    Property 15: User Identification Consistency (BlockAction)
    
    For any BlockAction with a valid user ID, the middleware should
    consistently extract the same user ID and map it to the correct
    TrIAge user.
    
    Validates: Requirements 8.1
    """
    # Setup
    storage = MockUserMappingStorage()
    await storage.create_mapping(slack_user)
    
    mapper = UserMapper(storage)
    middleware = UserIdentificationMiddleware(mapper)
    
    # Override action IDs to match the user
    action.user_id = slack_user.slack_user_id
    action.team_id = slack_user.slack_team_id
    
    # Extract user ID
    extracted_user_id = middleware.extract_user_id(action)
    extracted_team_id = middleware.extract_team_id(action)
    
    # Property: Extracted IDs match the action's IDs
    assert extracted_user_id == slack_user.slack_user_id
    assert extracted_team_id == slack_user.slack_team_id
    
    # Identify user
    identified_user = await middleware.identify_user(action)
    
    # Property: Identified user matches the original user
    assert identified_user is not None
    assert identified_user.slack_user_id == slack_user.slack_user_id
    assert identified_user.slack_team_id == slack_user.slack_team_id
    assert identified_user.triage_user_id == slack_user.triage_user_id
    assert identified_user.jira_email == slack_user.jira_email


# Feature: slack-integration, Property 15: User Identification Consistency
@settings(max_examples=100)
@given(
    slack_user=slack_user_strategy(),
    event_type=st.sampled_from(["webhook", "command", "action"]),
    webhook_event=webhook_event_strategy(),
    slash_command=slash_command_strategy(),
    block_action=block_action_strategy()
)
@pytest.mark.asyncio
async def test_user_identification_idempotent(slack_user, event_type, webhook_event, slash_command, block_action):
    """
    Property 15: User Identification Consistency (Idempotence)
    
    For any event, calling identify_user multiple times should return
    the same result consistently.
    
    Validates: Requirements 8.1
    """
    # Setup
    storage = MockUserMappingStorage()
    await storage.create_mapping(slack_user)
    
    mapper = UserMapper(storage)
    middleware = UserIdentificationMiddleware(mapper)
    
    # Select event based on type and override IDs
    if event_type == "webhook":
        event = webhook_event
        event.user_id = slack_user.slack_user_id
        event.team_id = slack_user.slack_team_id
    elif event_type == "command":
        event = slash_command
        event.user_id = slack_user.slack_user_id
        event.team_id = slack_user.slack_team_id
    else:  # action
        event = block_action
        event.user_id = slack_user.slack_user_id
        event.team_id = slack_user.slack_team_id
    
    # Identify user multiple times
    result1 = await middleware.identify_user(event)
    result2 = await middleware.identify_user(event)
    result3 = await middleware.identify_user(event)
    
    # Property: All results are identical
    assert result1 is not None
    assert result2 is not None
    assert result3 is not None
    
    assert result1.slack_user_id == result2.slack_user_id == result3.slack_user_id
    assert result1.slack_team_id == result2.slack_team_id == result3.slack_team_id
    assert result1.triage_user_id == result2.triage_user_id == result3.triage_user_id
    assert result1.jira_email == result2.jira_email == result3.jira_email


# Feature: slack-integration, Property 15: User Identification Consistency
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy(),
    event1=webhook_event_strategy(),
    event2=webhook_event_strategy()
)
@pytest.mark.asyncio
async def test_user_identification_distinguishes_users(user1, user2, event1, event2):
    """
    Property 15: User Identification Consistency (User Distinction)
    
    For any two different users, the middleware should correctly
    distinguish between them and return different user mappings.
    
    Validates: Requirements 8.1
    """
    # Ensure users are different
    assume(user1.slack_user_id != user2.slack_user_id or 
           user1.slack_team_id != user2.slack_team_id)
    
    # Setup
    storage = MockUserMappingStorage()
    await storage.create_mapping(user1)
    await storage.create_mapping(user2)
    
    mapper = UserMapper(storage)
    middleware = UserIdentificationMiddleware(mapper)
    
    # Override event IDs to match users
    event1.user_id = user1.slack_user_id
    event1.team_id = user1.slack_team_id
    
    event2.user_id = user2.slack_user_id
    event2.team_id = user2.slack_team_id
    
    # Identify users
    identified1 = await middleware.identify_user(event1)
    identified2 = await middleware.identify_user(event2)
    
    # Property: Users are correctly distinguished
    assert identified1 is not None
    assert identified2 is not None
    
    assert identified1.slack_user_id == user1.slack_user_id
    assert identified1.slack_team_id == user1.slack_team_id
    assert identified1.triage_user_id == user1.triage_user_id
    
    assert identified2.slack_user_id == user2.slack_user_id
    assert identified2.slack_team_id == user2.slack_team_id
    assert identified2.triage_user_id == user2.triage_user_id
    
    # Property: Users are different
    assert (identified1.slack_user_id != identified2.slack_user_id or
            identified1.slack_team_id != identified2.slack_team_id)


# Feature: slack-integration, Property 15: User Identification Consistency
@settings(max_examples=100)
@given(
    slack_user=slack_user_strategy(),
    event=webhook_event_strategy()
)
@pytest.mark.asyncio
async def test_user_identification_requires_mapping(slack_user, event):
    """
    Property 15: User Identification Consistency (Missing Mapping)
    
    For any event with a user ID that has no mapping, identify_user
    should return None, and require_user should raise an error.
    
    Validates: Requirements 8.1
    """
    # Setup with empty storage (no mappings)
    storage = MockUserMappingStorage()
    mapper = UserMapper(storage)
    middleware = UserIdentificationMiddleware(mapper)
    
    # Override event IDs to match unmapped user
    event.user_id = slack_user.slack_user_id
    event.team_id = slack_user.slack_team_id
    
    # Property: identify_user returns None for unmapped user
    identified = await middleware.identify_user(event)
    assert identified is None
    
    # Property: require_user raises ValueError for unmapped user
    with pytest.raises(ValueError, match="User identification required"):
        await middleware.require_user(event)
