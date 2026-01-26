# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for user configuration persistence.

Feature: slack-integration, Property 22: Configuration Persistence

For any user configuration change (notification channel, delivery time, enabled status),
the new settings should be stored and retrieved correctly for that user.

Validates: Requirements 10.2
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import os

from slack_bot.models import SlackConfig
from slack_bot.config_storage import ConfigStorage


# Custom strategies for generating test data
@st.composite
def user_id_strategy(draw):
    """Generate valid user IDs."""
    return f"user_{draw(st.integers(min_value=1, max_value=999999))}"


@st.composite
def channel_strategy(draw):
    """Generate valid channel configurations."""
    is_dm = draw(st.booleans())
    if is_dm:
        return "DM"
    else:
        # Generate channel ID starting with C
        channel_num = draw(st.integers(min_value=100000000, max_value=999999999))
        return f"C{channel_num}"


@st.composite
def time_strategy(draw):
    """Generate valid time strings in HH:MM format."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def timezone_strategy(draw):
    """Generate valid timezone strings."""
    timezones = [
        "UTC",
        "America/New_York",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Paris",
        "Asia/Tokyo",
        "Australia/Sydney"
    ]
    return draw(st.sampled_from(timezones))


@st.composite
def slack_config_strategy(draw):
    """Generate valid SlackConfig objects."""
    return SlackConfig(
        user_id=draw(user_id_strategy()),
        notification_channel=draw(channel_strategy()),
        delivery_time=draw(time_strategy()),
        notifications_enabled=draw(st.booleans()),
        timezone=draw(timezone_strategy())
    )


# Test database URL from environment or use in-memory SQLite for testing
# Note: SQLite doesn't support all PostgreSQL features, but works for basic CRUD testing
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:"
)


@pytest.fixture
async def config_storage():
    """Create a ConfigStorage instance for testing."""
    # For SQLite, we need to use aiosqlite instead of asyncpg
    # This is a simplified version for testing
    # In production, PostgreSQL with asyncpg should be used
    
    # Skip these tests if no PostgreSQL database is available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required for configuration persistence tests. "
                   "Set TEST_DATABASE_URL environment variable to run these tests.")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    await storage.connect()
    await storage.initialize_schema()
    
    yield storage
    
    # Cleanup: delete all test data
    if storage._pool:
        async with storage._pool.acquire() as conn:
            await conn.execute("DELETE FROM slack_user_config")
    
    await storage.disconnect()


# Feature: slack-integration, Property 22: Configuration Persistence
@settings(max_examples=100, deadline=5000)
@given(config=slack_config_strategy())
@pytest.mark.asyncio
async def test_config_create_and_retrieve_persistence(config):
    """
    Property 22: Configuration Persistence (Create and Retrieve)
    
    For any user configuration, creating it and then retrieving it
    should return the same configuration values.
    
    Validates: Requirements 10.2
    """
    # Skip if no PostgreSQL database available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    
    try:
        await storage.connect()
        await storage.initialize_schema()
        
        # Clean up any existing config for this user
        await storage.delete_config(config.user_id)
        
        # Create configuration
        created_config = await storage.create_config(config)
        
        # Verify created config matches input
        assert created_config.user_id == config.user_id
        assert created_config.notification_channel == config.notification_channel
        assert created_config.delivery_time == config.delivery_time
        assert created_config.notifications_enabled == config.notifications_enabled
        assert created_config.timezone == config.timezone
        
        # Retrieve configuration
        retrieved_config = await storage.get_config(config.user_id)
        
        # Verify retrieved config matches created config
        assert retrieved_config is not None
        assert retrieved_config.user_id == created_config.user_id
        assert retrieved_config.notification_channel == created_config.notification_channel
        assert retrieved_config.delivery_time == created_config.delivery_time
        assert retrieved_config.notifications_enabled == created_config.notifications_enabled
        assert retrieved_config.timezone == created_config.timezone
        
        # Cleanup
        await storage.delete_config(config.user_id)
        
    finally:
        await storage.disconnect()


# Feature: slack-integration, Property 22: Configuration Persistence
@settings(max_examples=100, deadline=5000)
@given(
    initial_config=slack_config_strategy(),
    new_channel=channel_strategy()
)
@pytest.mark.asyncio
async def test_config_update_channel_persistence(initial_config, new_channel):
    """
    Property 22: Configuration Persistence (Update Channel)
    
    For any user configuration, updating the notification channel
    should persist the new value and leave other fields unchanged.
    
    Validates: Requirements 10.2
    """
    assume(initial_config.notification_channel != new_channel)
    
    # Skip if no PostgreSQL database available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    
    try:
        await storage.connect()
        await storage.initialize_schema()
        
        # Clean up any existing config
        await storage.delete_config(initial_config.user_id)
        
        # Create initial configuration
        await storage.create_config(initial_config)
        
        # Update notification channel
        updated_config = await storage.update_config(
            user_id=initial_config.user_id,
            notification_channel=new_channel
        )
        
        # Verify update was applied
        assert updated_config is not None
        assert updated_config.notification_channel == new_channel
        
        # Verify other fields unchanged
        assert updated_config.delivery_time == initial_config.delivery_time
        assert updated_config.notifications_enabled == initial_config.notifications_enabled
        assert updated_config.timezone == initial_config.timezone
        
        # Retrieve and verify persistence
        retrieved_config = await storage.get_config(initial_config.user_id)
        assert retrieved_config is not None
        assert retrieved_config.notification_channel == new_channel
        assert retrieved_config.delivery_time == initial_config.delivery_time
        assert retrieved_config.notifications_enabled == initial_config.notifications_enabled
        
        # Cleanup
        await storage.delete_config(initial_config.user_id)
        
    finally:
        await storage.disconnect()


# Feature: slack-integration, Property 22: Configuration Persistence
@settings(max_examples=100, deadline=5000)
@given(
    initial_config=slack_config_strategy(),
    new_time=time_strategy()
)
@pytest.mark.asyncio
async def test_config_update_time_persistence(initial_config, new_time):
    """
    Property 22: Configuration Persistence (Update Delivery Time)
    
    For any user configuration, updating the delivery time
    should persist the new value and leave other fields unchanged.
    
    Validates: Requirements 10.2
    """
    assume(initial_config.delivery_time != new_time)
    
    # Skip if no PostgreSQL database available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    
    try:
        await storage.connect()
        await storage.initialize_schema()
        
        # Clean up any existing config
        await storage.delete_config(initial_config.user_id)
        
        # Create initial configuration
        await storage.create_config(initial_config)
        
        # Update delivery time
        updated_config = await storage.update_config(
            user_id=initial_config.user_id,
            delivery_time=new_time
        )
        
        # Verify update was applied
        assert updated_config is not None
        assert updated_config.delivery_time == new_time
        
        # Verify other fields unchanged
        assert updated_config.notification_channel == initial_config.notification_channel
        assert updated_config.notifications_enabled == initial_config.notifications_enabled
        assert updated_config.timezone == initial_config.timezone
        
        # Retrieve and verify persistence
        retrieved_config = await storage.get_config(initial_config.user_id)
        assert retrieved_config is not None
        assert retrieved_config.delivery_time == new_time
        assert retrieved_config.notification_channel == initial_config.notification_channel
        
        # Cleanup
        await storage.delete_config(initial_config.user_id)
        
    finally:
        await storage.disconnect()


# Feature: slack-integration, Property 22: Configuration Persistence
@settings(max_examples=100, deadline=5000)
@given(initial_config=slack_config_strategy())
@pytest.mark.asyncio
async def test_config_toggle_notifications_persistence(initial_config):
    """
    Property 22: Configuration Persistence (Toggle Notifications)
    
    For any user configuration, toggling notifications enabled/disabled
    should persist the new value and leave other fields unchanged.
    
    Validates: Requirements 10.2
    """
    # Skip if no PostgreSQL database available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    
    try:
        await storage.connect()
        await storage.initialize_schema()
        
        # Clean up any existing config
        await storage.delete_config(initial_config.user_id)
        
        # Create initial configuration
        await storage.create_config(initial_config)
        
        # Toggle notifications (flip the boolean)
        new_enabled_state = not initial_config.notifications_enabled
        
        updated_config = await storage.update_config(
            user_id=initial_config.user_id,
            notifications_enabled=new_enabled_state
        )
        
        # Verify update was applied
        assert updated_config is not None
        assert updated_config.notifications_enabled == new_enabled_state
        
        # Verify other fields unchanged
        assert updated_config.notification_channel == initial_config.notification_channel
        assert updated_config.delivery_time == initial_config.delivery_time
        assert updated_config.timezone == initial_config.timezone
        
        # Retrieve and verify persistence
        retrieved_config = await storage.get_config(initial_config.user_id)
        assert retrieved_config is not None
        assert retrieved_config.notifications_enabled == new_enabled_state
        assert retrieved_config.notification_channel == initial_config.notification_channel
        
        # Cleanup
        await storage.delete_config(initial_config.user_id)
        
    finally:
        await storage.disconnect()


# Feature: slack-integration, Property 22: Configuration Persistence
@settings(max_examples=100, deadline=5000)
@given(
    initial_config=slack_config_strategy(),
    new_timezone=timezone_strategy()
)
@pytest.mark.asyncio
async def test_config_update_timezone_persistence(initial_config, new_timezone):
    """
    Property 22: Configuration Persistence (Update Timezone)
    
    For any user configuration, updating the timezone
    should persist the new value and leave other fields unchanged.
    
    Validates: Requirements 10.2
    """
    assume(initial_config.timezone != new_timezone)
    
    # Skip if no PostgreSQL database available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    
    try:
        await storage.connect()
        await storage.initialize_schema()
        
        # Clean up any existing config
        await storage.delete_config(initial_config.user_id)
        
        # Create initial configuration
        await storage.create_config(initial_config)
        
        # Update timezone
        updated_config = await storage.update_config(
            user_id=initial_config.user_id,
            timezone=new_timezone
        )
        
        # Verify update was applied
        assert updated_config is not None
        assert updated_config.timezone == new_timezone
        
        # Verify other fields unchanged
        assert updated_config.notification_channel == initial_config.notification_channel
        assert updated_config.delivery_time == initial_config.delivery_time
        assert updated_config.notifications_enabled == initial_config.notifications_enabled
        
        # Retrieve and verify persistence
        retrieved_config = await storage.get_config(initial_config.user_id)
        assert retrieved_config is not None
        assert retrieved_config.timezone == new_timezone
        assert retrieved_config.notification_channel == initial_config.notification_channel
        
        # Cleanup
        await storage.delete_config(initial_config.user_id)
        
    finally:
        await storage.disconnect()


# Feature: slack-integration, Property 22: Configuration Persistence
@settings(max_examples=50, deadline=5000)
@given(
    config1=slack_config_strategy(),
    config2=slack_config_strategy()
)
@pytest.mark.asyncio
async def test_config_multi_user_isolation(config1, config2):
    """
    Property 22: Configuration Persistence (Multi-User Isolation)
    
    For any two different users, their configurations should be
    stored and retrieved independently without interference.
    
    Validates: Requirements 10.2, 8.2
    """
    assume(config1.user_id != config2.user_id)
    
    # Skip if no PostgreSQL database available
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("PostgreSQL database required")
    
    storage = ConfigStorage(TEST_DATABASE_URL)
    
    try:
        await storage.connect()
        await storage.initialize_schema()
        
        # Clean up any existing configs
        await storage.delete_config(config1.user_id)
        await storage.delete_config(config2.user_id)
        
        # Create both configurations
        await storage.create_config(config1)
        await storage.create_config(config2)
        
        # Retrieve both configurations
        retrieved_config1 = await storage.get_config(config1.user_id)
        retrieved_config2 = await storage.get_config(config2.user_id)
        
        # Verify both configs exist and are correct
        assert retrieved_config1 is not None
        assert retrieved_config2 is not None
        
        # Verify config1 matches original
        assert retrieved_config1.user_id == config1.user_id
        assert retrieved_config1.notification_channel == config1.notification_channel
        assert retrieved_config1.delivery_time == config1.delivery_time
        assert retrieved_config1.notifications_enabled == config1.notifications_enabled
        
        # Verify config2 matches original
        assert retrieved_config2.user_id == config2.user_id
        assert retrieved_config2.notification_channel == config2.notification_channel
        assert retrieved_config2.delivery_time == config2.delivery_time
        assert retrieved_config2.notifications_enabled == config2.notifications_enabled
        
        # Verify configs are different (no cross-contamination)
        assert retrieved_config1.user_id != retrieved_config2.user_id
        
        # Update config1 and verify config2 is unchanged
        new_channel = "DM" if config1.notification_channel != "DM" else "C123456789"
        await storage.update_config(
            user_id=config1.user_id,
            notification_channel=new_channel
        )
        
        # Retrieve both again
        updated_config1 = await storage.get_config(config1.user_id)
        unchanged_config2 = await storage.get_config(config2.user_id)
        
        # Verify config1 was updated
        assert updated_config1.notification_channel == new_channel
        
        # Verify config2 was NOT affected
        assert unchanged_config2.notification_channel == config2.notification_channel
        assert unchanged_config2.delivery_time == config2.delivery_time
        assert unchanged_config2.notifications_enabled == config2.notifications_enabled
        
        # Cleanup
        await storage.delete_config(config1.user_id)
        await storage.delete_config(config2.user_id)
        
    finally:
        await storage.disconnect()
