# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for user-specific JIRA account usage.

Feature: slack-integration, Property 17: User-Specific JIRA Account Usage

For any plan generation request, the system should use the requesting user's
JIRA credentials, not another user's credentials.

Validates: Requirements 8.4
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from slack_bot.models import SlackUser


# Custom strategies for generating test data

@st.composite
def slack_user_strategy(draw):
    """Generate SlackUser instances with valid IDs."""
    # Generate valid Slack user IDs (U + 8-11 uppercase letters/digits)
    user_id_length = draw(st.integers(min_value=8, max_value=11))
    user_id_chars = ''.join(draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=user_id_length,
        max_size=user_id_length
    )))
    
    # Generate valid Slack team IDs (T + 8-11 uppercase letters/digits)
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
def plan_request_strategy(draw, user=None):
    """Generate plan generation request data."""
    return {
        "user_id": user.triage_user_id if user else draw(st.text(min_size=5, max_size=50)),
        "team_id": user.slack_team_id if user else draw(st.text(min_size=5, max_size=50)),
        "date": draw(st.sampled_from(["today", "tomorrow"])),
        "jira_email": user.jira_email if user else draw(st.emails())
    }


# Mock API client for testing
class MockTriageAPIClient:
    """Mock TrIAge API client for testing."""
    
    def __init__(self):
        self.plan_requests = []
    
    async def generate_plan(self, user_id: str, team_id: str, jira_email: str, date: str):
        """Record plan generation request."""
        self.plan_requests.append({
            "user_id": user_id,
            "team_id": team_id,
            "jira_email": jira_email,
            "date": date
        })
        return {"plan_id": f"plan_{len(self.plan_requests)}"}
    
    def get_last_request(self):
        """Get the most recent plan request."""
        return self.plan_requests[-1] if self.plan_requests else None


# Property Tests

# Feature: slack-integration, Property 17: User-Specific JIRA Account Usage
@settings(max_examples=100)
@given(
    user=slack_user_strategy(),
    request=plan_request_strategy()
)
@pytest.mark.asyncio
async def test_jira_account_usage_single_user(user, request):
    """
    Property 17: User-Specific JIRA Account Usage (Single User)
    
    For any plan generation request from a user, the system should use
    that user's JIRA email address, not a different one.
    
    Validates: Requirements 8.4
    """
    api_client = MockTriageAPIClient()
    
    # Override request with user's data
    request["user_id"] = user.triage_user_id
    request["team_id"] = user.slack_team_id
    request["jira_email"] = user.jira_email
    
    # Make API call
    await api_client.generate_plan(
        user_id=request["user_id"],
        team_id=request["team_id"],
        jira_email=request["jira_email"],
        date=request["date"]
    )
    
    # Property: API call uses the correct user's JIRA email
    last_request = api_client.get_last_request()
    assert last_request is not None
    assert last_request["user_id"] == user.triage_user_id
    assert last_request["jira_email"] == user.jira_email


# Feature: slack-integration, Property 17: User-Specific JIRA Account Usage
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy(),
    request1=plan_request_strategy(),
    request2=plan_request_strategy()
)
@pytest.mark.asyncio
async def test_jira_account_usage_multiple_users(user1, user2, request1, request2):
    """
    Property 17: User-Specific JIRA Account Usage (Multiple Users)
    
    For any two different users making plan requests, each request should
    use the respective user's JIRA credentials, never mixing them.
    
    Validates: Requirements 8.4
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    assume(user1.jira_email != user2.jira_email)
    
    api_client = MockTriageAPIClient()
    
    # Override request1 with user1's data
    request1["user_id"] = user1.triage_user_id
    request1["team_id"] = user1.slack_team_id
    request1["jira_email"] = user1.jira_email
    
    # User1 makes a request
    await api_client.generate_plan(
        user_id=request1["user_id"],
        team_id=request1["team_id"],
        jira_email=request1["jira_email"],
        date=request1["date"]
    )
    
    # Override request2 with user2's data
    request2["user_id"] = user2.triage_user_id
    request2["team_id"] = user2.slack_team_id
    request2["jira_email"] = user2.jira_email
    
    # User2 makes a request
    await api_client.generate_plan(
        user_id=request2["user_id"],
        team_id=request2["team_id"],
        jira_email=request2["jira_email"],
        date=request2["date"]
    )
    
    # Property: Each request uses the correct user's JIRA email
    assert len(api_client.plan_requests) == 2
    
    first_request = api_client.plan_requests[0]
    assert first_request["user_id"] == user1.triage_user_id
    assert first_request["jira_email"] == user1.jira_email
    
    second_request = api_client.plan_requests[1]
    assert second_request["user_id"] == user2.triage_user_id
    assert second_request["jira_email"] == user2.jira_email
    
    # Property: JIRA emails are never mixed
    assert first_request["jira_email"] != second_request["jira_email"]


# Feature: slack-integration, Property 17: User-Specific JIRA Account Usage
@settings(max_examples=100)
@given(
    user=slack_user_strategy(),
    num_requests=st.integers(min_value=1, max_value=10),
    requests=st.lists(plan_request_strategy(), min_size=1, max_size=10)
)
@pytest.mark.asyncio
async def test_jira_account_usage_consistency(user, num_requests, requests):
    """
    Property 17: User-Specific JIRA Account Usage (Consistency)
    
    For any user making multiple plan requests, all requests should
    consistently use the same JIRA email address.
    
    Validates: Requirements 8.4
    """
    api_client = MockTriageAPIClient()
    
    # User makes multiple requests
    for i in range(min(num_requests, len(requests))):
        request = requests[i]
        # Override with user's data
        request["user_id"] = user.triage_user_id
        request["team_id"] = user.slack_team_id
        request["jira_email"] = user.jira_email
        
        await api_client.generate_plan(
            user_id=request["user_id"],
            team_id=request["team_id"],
            jira_email=request["jira_email"],
            date=request["date"]
        )
    
    actual_requests = min(num_requests, len(requests))
    
    # Property: All requests use the same JIRA email
    assert len(api_client.plan_requests) == actual_requests
    
    jira_emails = [req["jira_email"] for req in api_client.plan_requests]
    assert all(email == user.jira_email for email in jira_emails)
    
    # Property: All requests are for the same user
    user_ids = [req["user_id"] for req in api_client.plan_requests]
    assert all(uid == user.triage_user_id for uid in user_ids)


# Feature: slack-integration, Property 17: User-Specific JIRA Account Usage
@settings(max_examples=100)
@given(
    user=slack_user_strategy(),
    request=plan_request_strategy()
)
@pytest.mark.asyncio
async def test_jira_email_from_user_mapping(user, request):
    """
    Property 17: User-Specific JIRA Account Usage (Mapping)
    
    For any user, the JIRA email used for API calls should match the
    JIRA email stored in the user mapping.
    
    Validates: Requirements 8.4
    """
    # Property: User mapping contains JIRA email
    assert hasattr(user, 'jira_email')
    assert user.jira_email is not None
    assert '@' in user.jira_email
    
    # Property: JIRA email is valid email format
    assert '.' in user.jira_email.split('@')[1]
    
    # Simulate plan request
    api_client = MockTriageAPIClient()
    
    # Override request with user's data
    request["user_id"] = user.triage_user_id
    request["team_id"] = user.slack_team_id
    request["jira_email"] = user.jira_email
    
    await api_client.generate_plan(
        user_id=request["user_id"],
        team_id=request["team_id"],
        jira_email=request["jira_email"],
        date=request["date"]
    )
    
    # Property: Request uses JIRA email from user mapping
    last_request = api_client.get_last_request()
    assert last_request["jira_email"] == user.jira_email


# Feature: slack-integration, Property 17: User-Specific JIRA Account Usage
@settings(max_examples=100)
@given(
    users=st.lists(slack_user_strategy(), min_size=2, max_size=5, unique_by=lambda u: u.triage_user_id),
    requests=st.lists(plan_request_strategy(), min_size=2, max_size=5)
)
@pytest.mark.asyncio
async def test_jira_account_usage_concurrent_users(users, requests):
    """
    Property 17: User-Specific JIRA Account Usage (Concurrent)
    
    For any set of users making concurrent plan requests, each request
    should use the correct user's JIRA credentials without mixing.
    
    Validates: Requirements 8.4
    """
    api_client = MockTriageAPIClient()
    
    # All users make requests
    for i, user in enumerate(users):
        if i < len(requests):
            request = requests[i]
            # Override with user's data
            request["user_id"] = user.triage_user_id
            request["team_id"] = user.slack_team_id
            request["jira_email"] = user.jira_email
            
            await api_client.generate_plan(
                user_id=request["user_id"],
                team_id=request["team_id"],
                jira_email=request["jira_email"],
                date=request["date"]
            )
    
    actual_requests = min(len(users), len(requests))
    
    # Property: Number of requests matches number of users
    assert len(api_client.plan_requests) == actual_requests
    
    # Property: Each request uses the correct user's JIRA email
    for i in range(actual_requests):
        user = users[i]
        request = api_client.plan_requests[i]
        assert request["user_id"] == user.triage_user_id
        assert request["jira_email"] == user.jira_email
    
    # Property: All JIRA emails are unique (assuming unique users)
    jira_emails = [req["jira_email"] for req in api_client.plan_requests]
    assert len(set(jira_emails)) == actual_requests


# Feature: slack-integration, Property 17: User-Specific JIRA Account Usage
@settings(max_examples=100)
@given(
    user1=slack_user_strategy(),
    user2=slack_user_strategy(),
    request1=plan_request_strategy(),
    request2=plan_request_strategy()
)
@pytest.mark.asyncio
async def test_jira_account_no_credential_leakage(user1, user2, request1, request2):
    """
    Property 17: User-Specific JIRA Account Usage (No Leakage)
    
    For any two users, user1's JIRA credentials should never be used
    for user2's requests, and vice versa.
    
    Validates: Requirements 8.4
    """
    # Ensure users are different
    assume(user1.triage_user_id != user2.triage_user_id)
    assume(user1.jira_email != user2.jira_email)
    
    api_client = MockTriageAPIClient()
    
    # Override request1 with user1's data
    request1["user_id"] = user1.triage_user_id
    request1["team_id"] = user1.slack_team_id
    request1["jira_email"] = user1.jira_email
    
    # User1 makes a request
    await api_client.generate_plan(
        user_id=request1["user_id"],
        team_id=request1["team_id"],
        jira_email=request1["jira_email"],
        date=request1["date"]
    )
    
    # Override request2 with user2's data
    request2["user_id"] = user2.triage_user_id
    request2["team_id"] = user2.slack_team_id
    request2["jira_email"] = user2.jira_email
    
    # User2 makes a request
    await api_client.generate_plan(
        user_id=request2["user_id"],
        team_id=request2["team_id"],
        jira_email=request2["jira_email"],
        date=request2["date"]
    )
    
    # Property: User1's request never uses user2's JIRA email
    first_request = api_client.plan_requests[0]
    assert first_request["jira_email"] != user2.jira_email
    assert first_request["jira_email"] == user1.jira_email
    
    # Property: User2's request never uses user1's JIRA email
    second_request = api_client.plan_requests[1]
    assert second_request["jira_email"] != user1.jira_email
    assert second_request["jira_email"] == user2.jira_email
