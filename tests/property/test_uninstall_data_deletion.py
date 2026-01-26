# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for uninstall data deletion.

Feature: slack-integration, Property 31: Uninstall Data Deletion

For any workspace that uninstalls the bot, all associated OAuth tokens
and user data should be deleted from storage.

Validates: Requirements 12.5
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from slack_bot.oauth_manager import OAuthManager
from slack_bot.models import WorkspaceToken, SlackUser
from datetime import datetime, timezone


# Test constants
TEST_ENCRYPTION_KEY = "12345678901234567890123456789012"  # Exactly 32 characters


# Custom strategies
@st.composite
def workspace_token(draw):
    """Generate a WorkspaceToken for testing."""
    team_id = draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', min_size=9, max_size=11).map(lambda s: f"T{s[:9]}"))
    bot_user_id = draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', min_size=9, max_size=11).map(lambda s: f"U{s[:9]}"))
    
    return WorkspaceToken(
        team_id=team_id,
        access_token=draw(st.text(min_size=20, max_size=50)),
        bot_user_id=bot_user_id,
        scope=draw(st.text(min_size=10, max_size=100)),
        installed_at=datetime.now(timezone.utc)
    )


@st.composite
def slack_user(draw, team_id=None):
    """Generate a SlackUser for testing."""
    if team_id is None:
        team_id = draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', min_size=9, max_size=11).map(lambda s: f"T{s[:9]}"))
    
    return SlackUser(
        slack_user_id=draw(st.text(alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', min_size=9, max_size=11).map(lambda s: f"U{s[:9]}")),
        slack_team_id=team_id,
        triage_user_id=draw(st.text(min_size=10, max_size=50)),
        jira_email=draw(st.emails()),
        display_name=draw(st.text(min_size=3, max_size=50))
    )


# Feature: slack-integration, Property 31: Uninstall Data Deletion
@settings(max_examples=50)
@given(token=workspace_token())
@pytest.mark.asyncio
async def test_uninstall_deletes_workspace_token(token):
    """
    Property: For any workspace token, calling handle_uninstall should
    delete the token from storage.
    
    Validates: Requirements 12.5
    """
    # Create OAuth manager with in-memory storage
    token_storage = {}
    oauth_manager = OAuthManager(
        client_id="test_client",
        client_secret="test_secret",
        redirect_url="https://example.com/callback",
        encryption_key=TEST_ENCRYPTION_KEY,
        token_storage=token_storage
    )
    
    # Store token
    await oauth_manager.store_token(token)
    
    # Verify token exists
    assert token.team_id in token_storage, "Token was not stored"
    
    # Handle uninstall
    result = await oauth_manager.handle_uninstall(token.team_id)
    
    # Verify token was deleted
    assert result, "Uninstall handler returned False"
    assert token.team_id not in token_storage, "Token was not deleted after uninstall"
    
    # Verify token cannot be retrieved
    retrieved_token = await oauth_manager.get_token(token.team_id)
    assert retrieved_token is None, "Token still retrievable after uninstall"


# Feature: slack-integration, Property 31: Uninstall Data Deletion
@settings(max_examples=50)
@given(
    token=workspace_token(),
    num_users=st.integers(min_value=1, max_value=5)
)
@pytest.mark.asyncio
async def test_uninstall_deletes_all_workspace_users(token, num_users):
    """
    Property: For any workspace with multiple users, calling handle_uninstall
    should delete all user mappings for that workspace.
    
    Validates: Requirements 12.5
    """
    # Create mock user storage
    class MockUserStorage:
        def __init__(self):
            self.users = {}
            self.deleted_teams = []
        
        async def delete_workspace_mappings(self, team_id):
            """Delete all users for a team."""
            self.deleted_teams.append(team_id)
            count = sum(1 for user in self.users.values() if user.slack_team_id == team_id)
            # Remove users for this team
            self.users = {
                uid: user for uid, user in self.users.items()
                if user.slack_team_id != team_id
            }
            return count
    
    user_storage = MockUserStorage()
    
    # Create OAuth manager with user storage
    token_storage = {}
    oauth_manager = OAuthManager(
        client_id="test_client",
        client_secret="test_secret",
        redirect_url="https://example.com/callback",
        encryption_key=TEST_ENCRYPTION_KEY,
        token_storage=token_storage,
        user_storage=user_storage
    )
    
    # Store token
    await oauth_manager.store_token(token)
    
    # Create users for this workspace
    for i in range(num_users):
        user = SlackUser(
            slack_user_id=f"U{i:09d}",
            slack_team_id=token.team_id,
            triage_user_id=f"triage_user_{i}",
            jira_email=f"user{i}@example.com",
            display_name=f"User {i}"
        )
        user_storage.users[user.slack_user_id] = user
    
    # Verify users exist
    workspace_users = [u for u in user_storage.users.values() if u.slack_team_id == token.team_id]
    assert len(workspace_users) == num_users, "Users were not created"
    
    # Handle uninstall
    result = await oauth_manager.handle_uninstall(token.team_id)
    
    # Verify all users were deleted
    assert result, "Uninstall handler returned False"
    assert token.team_id in user_storage.deleted_teams, "User deletion was not called"
    
    workspace_users_after = [u for u in user_storage.users.values() if u.slack_team_id == token.team_id]
    assert len(workspace_users_after) == 0, f"Users still exist after uninstall: {workspace_users_after}"


# Feature: slack-integration, Property 31: Uninstall Data Deletion
@settings(max_examples=50)
@given(
    token1=workspace_token(),
    token2=workspace_token()
)
@pytest.mark.asyncio
async def test_uninstall_only_deletes_target_workspace(token1, token2):
    """
    Property: For any two workspaces, uninstalling one workspace should
    not affect the other workspace's data.
    
    Validates: Requirements 12.5
    """
    # Ensure different team IDs
    assume(token1.team_id != token2.team_id)
    
    # Create OAuth manager with in-memory storage
    token_storage = {}
    oauth_manager = OAuthManager(
        client_id="test_client",
        client_secret="test_secret",
        redirect_url="https://example.com/callback",
        encryption_key=TEST_ENCRYPTION_KEY,
        token_storage=token_storage
    )
    
    # Store both tokens
    await oauth_manager.store_token(token1)
    await oauth_manager.store_token(token2)
    
    # Verify both tokens exist
    assert token1.team_id in token_storage, "Token 1 was not stored"
    assert token2.team_id in token_storage, "Token 2 was not stored"
    
    # Uninstall first workspace
    result = await oauth_manager.handle_uninstall(token1.team_id)
    
    # Verify only first token was deleted
    assert result, "Uninstall handler returned False"
    assert token1.team_id not in token_storage, "Token 1 was not deleted"
    assert token2.team_id in token_storage, "Token 2 was incorrectly deleted"
    
    # Verify second token is still retrievable
    retrieved_token2 = await oauth_manager.get_token(token2.team_id)
    assert retrieved_token2 is not None, "Token 2 is not retrievable after uninstalling Token 1"
    assert retrieved_token2.team_id == token2.team_id, "Wrong token retrieved"


# Feature: slack-integration, Property 31: Uninstall Data Deletion
@settings(max_examples=50)
@given(team_id=st.text(min_size=9, max_size=11).map(lambda s: f"T{s}"))
@pytest.mark.asyncio
async def test_uninstall_nonexistent_workspace_is_safe(team_id):
    """
    Property: For any team ID that doesn't exist, calling handle_uninstall
    should not raise an error and should return False.
    
    Validates: Requirements 12.5
    """
    # Create OAuth manager with empty storage
    token_storage = {}
    oauth_manager = OAuthManager(
        client_id="test_client",
        client_secret="test_secret",
        redirect_url="https://example.com/callback",
        encryption_key=TEST_ENCRYPTION_KEY,
        token_storage=token_storage
    )
    
    # Try to uninstall non-existent workspace
    result = await oauth_manager.handle_uninstall(team_id)
    
    # Should return False but not raise error
    assert result is False, "Uninstall of non-existent workspace should return False"
