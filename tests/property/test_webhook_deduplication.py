# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for webhook deduplication.

Tests universal properties of webhook event deduplication using
Hypothesis for comprehensive validation across many inputs.

Feature: slack-integration, Property 13: Webhook Deduplication
Validates: Requirements 7.4
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timezone

from slack_bot.webhook_handler import WebhookDeduplicator


# Custom strategies for generating test data

@st.composite
def event_id(draw):
    """Generate valid event IDs."""
    # Event IDs can be UUIDs, timestamps, or custom identifiers
    id_type = draw(st.sampled_from(['uuid', 'timestamp', 'custom']))
    
    if id_type == 'uuid':
        import uuid
        return str(uuid.uuid4())
    elif id_type == 'timestamp':
        return str(draw(st.integers(min_value=1000000000, max_value=9999999999)))
    else:
        return draw(st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                min_codepoint=33,
                max_codepoint=126
            ),
            min_size=10,
            max_size=50
        ))


@st.composite
def ttl_seconds(draw):
    """Generate valid TTL values."""
    return draw(st.integers(min_value=60, max_value=3600))


class TestWebhookDeduplicationProperties:
    """
    Property-based tests for webhook deduplication.
    
    Feature: slack-integration, Property 13: Webhook Deduplication
    
    For any webhook event ID, if the same event ID is received multiple times,
    only the first occurrence should be processed.
    
    Validates: Requirements 7.4
    """
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_first_event_not_duplicate(self, event_id, ttl):
        """
        Property: For any event ID seen for the first time, is_duplicate
        should return False.
        
        This validates that new events are not incorrectly marked as duplicates.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        result = await deduplicator.is_duplicate(event_id)
        
        assert result is False
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_second_event_is_duplicate(self, event_id, ttl):
        """
        Property: For any event ID, after marking it as processed, subsequent
        checks should return True (duplicate).
        
        This validates that duplicate detection works correctly.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # First check - not duplicate
        first_check = await deduplicator.is_duplicate(event_id)
        assert first_check is False
        
        # Mark as processed
        await deduplicator.mark_processed(event_id)
        
        # Second check - should be duplicate
        second_check = await deduplicator.is_duplicate(event_id)
        assert second_check is True
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_multiple_duplicate_checks_consistent(self, event_id, ttl):
        """
        Property: For any processed event, multiple duplicate checks should
        consistently return True.
        
        This validates that duplicate status is stable.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # Mark as processed
        await deduplicator.mark_processed(event_id)
        
        # Multiple checks should all return True
        results = []
        for _ in range(5):
            result = await deduplicator.is_duplicate(event_id)
            results.append(result)
        
        assert all(results), "All duplicate checks should return True"
    
    @given(event_id1=event_id(), event_id2=event_id(), ttl=ttl_seconds())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_different_events_independent(self, event_id1, event_id2, ttl):
        """
        Property: For any two different event IDs, marking one as processed
        should not affect the other.
        
        This validates that events are tracked independently.
        """
        assume(event_id1 != event_id2)
        
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # Mark first event as processed
        await deduplicator.mark_processed(event_id1)
        
        # First event should be duplicate
        assert await deduplicator.is_duplicate(event_id1) is True
        
        # Second event should not be duplicate
        assert await deduplicator.is_duplicate(event_id2) is False
    
    @given(event_ids=st.lists(event_id(), min_size=1, max_size=20, unique=True), ttl=ttl_seconds())
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_multiple_events_tracked_independently(self, event_ids, ttl):
        """
        Property: For any list of unique event IDs, each should be tracked
        independently without interference.
        
        This validates that the deduplicator can handle multiple events.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # Mark all events as processed
        for event_id in event_ids:
            await deduplicator.mark_processed(event_id)
        
        # All should be marked as duplicates
        for event_id in event_ids:
            result = await deduplicator.is_duplicate(event_id)
            assert result is True, f"Event {event_id} should be duplicate"
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_mark_processed_idempotent(self, event_id, ttl):
        """
        Property: For any event ID, marking it as processed multiple times
        should have the same effect as marking it once.
        
        This validates that mark_processed is idempotent.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # Mark as processed multiple times
        await deduplicator.mark_processed(event_id)
        await deduplicator.mark_processed(event_id)
        await deduplicator.mark_processed(event_id)
        
        # Should still be duplicate
        result = await deduplicator.is_duplicate(event_id)
        assert result is True
    
    @given(event_id=event_id())
    @settings(max_examples=15, deadline=None)
    @pytest.mark.asyncio
    async def test_ttl_expiration_removes_event(self, event_id):
        """
        Property: For any event ID with a short TTL, after the TTL expires,
        the event should no longer be marked as duplicate.
        
        This validates that TTL-based expiration works correctly.
        """
        # Use very short TTL for testing (1 second)
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=1)
        
        # Mark as processed
        await deduplicator.mark_processed(event_id)
        
        # Should be duplicate immediately
        assert await deduplicator.is_duplicate(event_id) is True
        
        # Wait for TTL to expire
        await asyncio.sleep(1.5)
        
        # Clean expired entries
        deduplicator._clean_expired()
        
        # Should no longer be duplicate
        result = await deduplicator.is_duplicate(event_id)
        assert result is False
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_concurrent_duplicate_checks(self, event_id, ttl):
        """
        Property: For any event ID, concurrent duplicate checks should all
        return consistent results.
        
        This validates thread-safety of duplicate checking.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # Mark as processed
        await deduplicator.mark_processed(event_id)
        
        # Perform concurrent duplicate checks
        tasks = [deduplicator.is_duplicate(event_id) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All should return True
        assert all(results), "All concurrent checks should return True"
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_check_before_mark_sequence(self, event_id, ttl):
        """
        Property: For any event ID, the sequence check -> mark -> check
        should produce False -> (mark) -> True.
        
        This validates the typical usage pattern.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # First check - not duplicate
        first = await deduplicator.is_duplicate(event_id)
        assert first is False
        
        # Mark as processed
        await deduplicator.mark_processed(event_id)
        
        # Second check - duplicate
        second = await deduplicator.is_duplicate(event_id)
        assert second is True


class TestMemoryCacheCleanupProperties:
    """
    Property-based tests for memory cache cleanup.
    
    Feature: slack-integration, Property 13: Webhook Deduplication
    
    Validates that expired entries are properly cleaned from memory cache.
    
    Validates: Requirements 7.4
    """
    
    @given(event_ids=st.lists(event_id(), min_size=5, max_size=20, unique=True))
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_only(self, event_ids):
        """
        Property: For any set of events with different ages, cleanup should
        remove only expired events.
        
        This validates selective cleanup based on TTL.
        """
        # Use short TTL for testing
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=2)
        
        # Mark first half as processed
        half = len(event_ids) // 2
        for event_id in event_ids[:half]:
            await deduplicator.mark_processed(event_id)
        
        # Wait for first half to expire
        await asyncio.sleep(2.5)
        
        # Mark second half as processed (these should not expire)
        for event_id in event_ids[half:]:
            await deduplicator.mark_processed(event_id)
        
        # Clean expired
        deduplicator._clean_expired()
        
        # First half should not be duplicates (expired)
        for event_id in event_ids[:half]:
            result = await deduplicator.is_duplicate(event_id)
            assert result is False, f"Expired event {event_id} should not be duplicate"
        
        # Second half should still be duplicates (not expired)
        for event_id in event_ids[half:]:
            result = await deduplicator.is_duplicate(event_id)
            assert result is True, f"Non-expired event {event_id} should be duplicate"
    
    @given(event_id=event_id())
    @settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_cleanup_idempotent(self, event_id):
        """
        Property: For any deduplicator state, calling cleanup multiple times
        should be safe and produce the same result.
        
        This validates that cleanup is idempotent.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=1)
        
        # Mark event as processed
        await deduplicator.mark_processed(event_id)
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Multiple cleanups should be safe
        deduplicator._clean_expired()
        deduplicator._clean_expired()
        deduplicator._clean_expired()
        
        # Event should not be duplicate
        result = await deduplicator.is_duplicate(event_id)
        assert result is False


class TestDeduplicationIntegrationProperties:
    """
    Integration property tests for deduplication with webhook handler.
    
    Feature: slack-integration, Property 13: Webhook Deduplication
    
    Validates end-to-end deduplication behavior.
    
    Validates: Requirements 7.4
    """
    
    @given(event_id=event_id(), ttl=ttl_seconds())
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_deduplication_workflow(self, event_id, ttl):
        """
        Property: For any event, the typical workflow of check -> process -> check
        should correctly identify duplicates.
        
        This validates the complete deduplication workflow.
        """
        deduplicator = WebhookDeduplicator(redis_client=None, ttl_seconds=ttl)
        
        # Simulate webhook handler workflow
        
        # 1. Check if duplicate (first time)
        is_dup_1 = await deduplicator.is_duplicate(event_id)
        assert is_dup_1 is False, "First check should not be duplicate"
        
        # 2. Process event (mark as processed)
        await deduplicator.mark_processed(event_id)
        
        # 3. Check if duplicate (second time - duplicate webhook)
        is_dup_2 = await deduplicator.is_duplicate(event_id)
        assert is_dup_2 is True, "Second check should be duplicate"
        
        # 4. Third attempt should also be duplicate
        is_dup_3 = await deduplicator.is_duplicate(event_id)
        assert is_dup_3 is True, "Third check should be duplicate"
