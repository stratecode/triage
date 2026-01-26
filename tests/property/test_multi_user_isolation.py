# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for multi-user data isolation.

Feature: slack-integration, Property 16: Multi-User Data Isolation

For any two different users in the same workspace, one user's plans, tasks,
and configuration should never be visible to or modifiable by the other user.

Validates: Requirements 8.2, 8.5
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from slack_bot.models import SlackUser
from slack_bot.data_isolation import DataIsolationChecker, DataIsolationError, QueryFilter


# Custom strategies for generating test data

@st.composite
def slack_user_strategy(draw):
    """Generate SlackUser instances."""
    # Generate unique user IDs (ASCII only)
    user_id_length = draw(st.integers(min_value=8, max_value=11))
    user_id_chars = ''.join(draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=user_id_length,
        max_size=user_id_length
    )))
    
    team_id_length = draw(st.integers(min_value=8, max_value=11))
    team_id_chars = ''.join(draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=team_id_length,
        max_size=team_id_length
    )))
    
    return SlackUser(
        slack_user_id=f"U{user_id_chars}",
        slack_team_id=f"T{team_id_chars}",
        triage_user_id=draw(st.text(min_size=5, max_size=50)),
        jira_email=draw(st.emails()),
        display_name=draw(st.text(min_size=1, max_size=100))
    )


@st.composite
def plan_data_strategy(draw, user_id=None):
    """Generate plan data dictionaries."""
    return {
        "id": draw(st.text(min_size=10, max_size=50)),
        "user_id": user_id or draw(st.text(min_size=5, max_size=50)),
        "date": draw(st.dates()).isoformat(),
        "priority_tasks": draw(st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.text(min_size=1, max_size=100),
                min_size=1,
                max_size=5
            ),
            min_size=0,
            max_size=3
        )),
        "admin_tasks": draw(st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.text(min_size=1, max_size=100),
                min_size=1,
                max_size=5
            ),
            min_size=0,
            max_size=10
        )),
        "status": draw(st.sampled_from(["pending", "approved", "rejected"]))
    }


@st.composite
def task_data_strategy(draw, user_id=None):
    """Generate task data dictionaries."""
    return {
        "id": draw(st.text(min_size=10, max_size=50)),
        "user_id": user_id or draw(st.text(min_size=5, max_size=50)),
        "key": draw(st.text(min_size=5, max_size=20)),
        "summary": draw(st.text(min_size=10, max_size=200)),
        "urgency": draw(st.sampled_from(["High", "Medium", "Low"])),
        "effort_days": draw(st.floats(min_value=0.1, max_value=5.0))
    }


# Property Tests

# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy(),
    plan=plan_data_strategy()
)
@pytest.mark.asyncio
async def test_multi_user_data_isolation_plan_access(user1, user2, plan):
    """
    Property 16: Multi-User Data Isolation (Plan Access)
    
    For any two different users, user1 should not be able to access
    user2's plans, and vice versa.
    
    Validates: Requirements 8.2, 8.5
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    
    checker = DataIsolationChecker()
    
    # Override plan ownership to user2
    plan["user_id"] = user2.triage_user_id
    
    # Property: user1 cannot access user2's plan
    with pytest.raises(DataIsolationError):
        checker.verify_plan_access(user1, plan)
    
    # Property: user2 can access their own plan
    checker.verify_plan_access(user2, plan)  # Should not raise


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy(),
    task=task_data_strategy()
)
@pytest.mark.asyncio
async def test_multi_user_data_isolation_task_access(user1, user2, task):
    """
    Property 16: Multi-User Data Isolation (Task Access)
    
    For any two different users, user1 should not be able to access
    user2's tasks, and vice versa.
    
    Validates: Requirements 8.2, 8.5
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    
    checker = DataIsolationChecker()
    
    # Override task ownership to user2
    task["user_id"] = user2.triage_user_id
    
    # Property: user1 cannot access user2's task
    with pytest.raises(DataIsolationError):
        checker.verify_task_access(user1, task)
    
    # Property: user2 can access their own task
    checker.verify_task_access(user2, task)  # Should not raise


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy()
)
@pytest.mark.asyncio
async def test_multi_user_data_isolation_config_access(user1, user2):
    """
    Property 16: Multi-User Data Isolation (Config Access)
    
    For any two different users, user1 should not be able to access
    user2's configuration, and vice versa.
    
    Validates: Requirements 8.2, 8.5
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    
    checker = DataIsolationChecker()
    
    # Property: user1 cannot access user2's config
    with pytest.raises(DataIsolationError):
        checker.verify_config_access(user1, user2.triage_user_id)
    
    # Property: user2 can access their own config
    checker.verify_config_access(user2, user2.triage_user_id)  # Should not raise


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy(),
    num_items=st.integers(min_value=1, max_value=20)
)
@pytest.mark.asyncio
async def test_multi_user_data_isolation_filtering(user1, user2, num_items):
    """
    Property 16: Multi-User Data Isolation (Data Filtering)
    
    For any list of data items containing items from multiple users,
    filtering should return only items belonging to the requesting user.
    
    Validates: Requirements 8.2, 8.5
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    
    checker = DataIsolationChecker()
    
    # Create mixed list of items from both users
    items = []
    user1_count = 0
    user2_count = 0
    
    for i in range(num_items):
        if i % 2 == 0:
            items.append({"user_id": user1.triage_user_id, "data": f"item_{i}"})
            user1_count += 1
        else:
            items.append({"user_id": user2.triage_user_id, "data": f"item_{i}"})
            user2_count += 1
    
    # Filter for user1
    user1_items = checker.filter_user_data(user1, items)
    
    # Property: Filtered list contains only user1's items
    assert len(user1_items) == user1_count
    assert all(item["user_id"] == user1.triage_user_id for item in user1_items)
    
    # Filter for user2
    user2_items = checker.filter_user_data(user2, items)
    
    # Property: Filtered list contains only user2's items
    assert len(user2_items) == user2_count
    assert all(item["user_id"] == user2.triage_user_id for item in user2_items)
    
    # Property: No overlap between filtered lists
    user1_ids = {item["data"] for item in user1_items}
    user2_ids = {item["data"] for item in user2_items}
    assert len(user1_ids & user2_ids) == 0


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy()
)
@pytest.mark.asyncio
async def test_multi_user_workspace_isolation(user1, user2):
    """
    Property 16: Multi-User Data Isolation (Workspace Isolation)
    
    For any two users from different workspaces, they should not be
    able to access each other's resources.
    
    Validates: Requirements 8.2, 8.5
    """
    # Ensure users are from different workspaces
    assume(user1.slack_team_id != user2.slack_team_id)
    
    checker = DataIsolationChecker()
    
    # Property: user1 cannot access resources from user2's workspace
    with pytest.raises(DataIsolationError):
        checker.verify_workspace_isolation(user1, user2.slack_team_id)
    
    # Property: user2 cannot access resources from user1's workspace
    with pytest.raises(DataIsolationError):
        checker.verify_workspace_isolation(user2, user1.slack_team_id)
    
    # Property: Each user can access their own workspace
    checker.verify_workspace_isolation(user1, user1.slack_team_id)  # Should not raise
    checker.verify_workspace_isolation(user2, user2.slack_team_id)  # Should not raise


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(user=slack_user_strategy())
@pytest.mark.asyncio
async def test_query_filter_adds_user_isolation(user):
    """
    Property 16: Multi-User Data Isolation (Query Filtering)
    
    For any user and query parameters, adding a user filter should
    ensure the query only returns data for that user.
    
    Validates: Requirements 8.2, 8.5
    """
    # Create query parameters without user filter
    query_params = {
        "status": "active",
        "date": "2026-01-15"
    }
    
    # Add user filter
    filtered_params = QueryFilter.add_user_filter(query_params, user)
    
    # Property: Filtered params include user_id
    assert "user_id" in filtered_params
    assert filtered_params["user_id"] == user.triage_user_id
    
    # Property: Original params are preserved
    assert filtered_params["status"] == query_params["status"]
    assert filtered_params["date"] == query_params["date"]
    
    # Property: Verification passes for filtered params
    assert QueryFilter.verify_query_has_user_filter(filtered_params, user)


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy()
)
@pytest.mark.asyncio
async def test_user_filter_prevents_cross_user_access(user1, user2):
    """
    Property 16: Multi-User Data Isolation (Filter Verification)
    
    For any two different users, a query filtered for user1 should
    fail verification for user2, and vice versa.
    
    Validates: Requirements 8.2, 8.5
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    
    # Create query filtered for user1
    query_params = QueryFilter.add_user_filter({}, user1)
    
    # Property: Query passes verification for user1
    assert QueryFilter.verify_query_has_user_filter(query_params, user1)
    
    # Property: Query fails verification for user2
    assert not QueryFilter.verify_query_has_user_filter(query_params, user2)


# Feature: slack-integration, Property 16: Multi-User Data Isolation
@settings(max_examples=100)
@given(user=slack_user_strategy())
@pytest.mark.asyncio
async def test_user_access_verification_self(user):
    """
    Property 16: Multi-User Data Isolation (Self Access)
    
    For any user, they should always be able to access their own resources.
    
    Validates: Requirements 8.2, 8.5
    """
    checker = DataIsolationChecker()
    
    # Property: User can access their own resources
    checker.verify_user_access(user, user.triage_user_id, "test_resource")  # Should not raise
    
    # Property: User filter matches their own ID
    user_filter = checker.create_user_filter(user)
    assert user_filter["user_id"] == user.triage_user_id
    
    # Property: Workspace filter matches their own workspace
    workspace_filter = checker.create_workspace_filter(user)
    assert workspace_filter["team_id"] == user.slack_team_id
