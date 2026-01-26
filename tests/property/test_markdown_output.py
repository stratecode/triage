# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for long description truncation.

Feature: slack-integration
Property 20: Long Description Truncation

For any task description exceeding 200 characters, the displayed text
should be truncated with an ellipsis and provide an option to expand.

Validates: Requirements 9.4
"""

from hypothesis import given, strategies as st, assume
from slack_bot.message_formatter import MessageFormatter


# Feature: slack-integration, Property 20: Long Description Truncation
@given(
    text=st.text(min_size=1, max_size=1000),
    max_length=st.integers(min_value=10, max_value=500)
)
def test_property_20_long_description_truncation(text, max_length):
    """
    Property 20: Long Description Truncation
    
    For any task description exceeding the maximum length, the displayed
    text should be truncated with an ellipsis.
    
    The truncation should:
    - Never exceed max_length characters
    - End with "..." if text was truncated
    - Preserve original text if within limit
    - Be a prefix of the original text (minus ellipsis)
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    truncated = formatter.truncate_text(text, max_length)
    
    # Truncated text should never exceed max_length
    assert len(truncated) <= max_length, \
        f"Truncated text length {len(truncated)} exceeds max {max_length}"
    
    if len(text) <= max_length:
        # Text should be unchanged if within limit
        assert truncated == text, \
            f"Text within limit should not be modified: expected '{text}', got '{truncated}'"
    else:
        # Text should be truncated with ellipsis
        assert truncated.endswith("..."), \
            f"Truncated text should end with '...', got '{truncated}'"
        
        # Truncated text should be exactly max_length characters
        assert len(truncated) == max_length, \
            f"Truncated text should be exactly {max_length} chars, got {len(truncated)}"
        
        # Truncated text (minus ellipsis) should be prefix of original
        truncated_content = truncated[:-3]  # Remove "..."
        assert text.startswith(truncated_content), \
            f"Truncated text should be a prefix of original text"
        
        # The ellipsis should replace at least 1 character
        assert len(truncated_content) < len(text), \
            "Truncation should remove at least some characters"


@given(text=st.text(min_size=201, max_size=1000))
def test_truncation_default_length_200(text):
    """
    Test that default truncation length is 200 characters.
    
    For any text exceeding 200 characters, truncation with default
    parameters should produce a 200-character result.
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Use default max_length (200)
    truncated = formatter.truncate_text(text)
    
    # Should be truncated to 200 characters
    assert len(truncated) == 200, \
        f"Default truncation should produce 200 chars, got {len(truncated)}"
    
    # Should end with ellipsis
    assert truncated.endswith("..."), \
        f"Truncated text should end with '...'"
    
    # Content before ellipsis should be 197 characters
    assert len(truncated[:-3]) == 197, \
        f"Content before ellipsis should be 197 chars"


@given(text=st.text(min_size=1, max_size=200))
def test_no_truncation_within_limit(text):
    """
    Test that text within the limit is not truncated.
    
    For any text of 200 characters or less, no truncation should occur.
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Use default max_length (200)
    truncated = formatter.truncate_text(text)
    
    # Should be unchanged
    assert truncated == text, \
        f"Text within limit should not be modified"
    
    # Should not end with ellipsis (unless original text did)
    if not text.endswith("..."):
        assert not truncated.endswith("...") or truncated == text, \
            "Text within limit should not have ellipsis added"


@given(
    text=st.text(min_size=50, max_size=1000),
    max_length=st.integers(min_value=20, max_value=100)
)
def test_truncation_preserves_prefix(text, max_length):
    """
    Test that truncation preserves the beginning of the text.
    
    Users should be able to read the start of the description even
    when truncated.
    
    Validates: Requirements 9.4
    """
    assume(len(text) > max_length)  # Only test when truncation occurs
    
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    truncated = formatter.truncate_text(text, max_length)
    
    # Extract content before ellipsis
    content = truncated[:-3] if truncated.endswith("...") else truncated
    
    # Content should be the exact prefix of original text
    assert text.startswith(content), \
        f"Truncated content should be exact prefix of original"
    
    # No characters should be skipped or modified
    for i, char in enumerate(content):
        assert char == text[i], \
            f"Character at position {i} should match: expected '{text[i]}', got '{char}'"


@given(text=st.text(min_size=1, max_size=1000))
def test_truncation_idempotent(text):
    """
    Test that truncating already-truncated text doesn't change it.
    
    Truncation should be idempotent - truncating twice should give
    the same result as truncating once.
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    max_length = 200
    
    # Truncate once
    truncated_once = formatter.truncate_text(text, max_length)
    
    # Truncate again
    truncated_twice = formatter.truncate_text(truncated_once, max_length)
    
    # Should be identical
    assert truncated_once == truncated_twice, \
        f"Truncation should be idempotent"


@given(
    text=st.text(min_size=1, max_size=1000),
    max_length1=st.integers(min_value=20, max_value=200),
    max_length2=st.integers(min_value=20, max_value=200)
)
def test_truncation_length_ordering(text, max_length1, max_length2):
    """
    Test that shorter max_length produces shorter or equal result.
    
    Truncating to a shorter length should never produce a longer result
    than truncating to a longer length.
    
    Validates: Requirements 9.4
    """
    assume(max_length1 < max_length2)
    
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    truncated1 = formatter.truncate_text(text, max_length1)
    truncated2 = formatter.truncate_text(text, max_length2)
    
    # Shorter max_length should produce shorter or equal result
    assert len(truncated1) <= len(truncated2), \
        f"Truncating to {max_length1} should not be longer than truncating to {max_length2}"
    
    # If both are truncated, shorter one should be prefix of longer one
    if len(text) > max_length2:
        # Both are truncated
        content1 = truncated1[:-3] if truncated1.endswith("...") else truncated1
        content2 = truncated2[:-3] if truncated2.endswith("...") else truncated2
        
        # Shorter content should be prefix of longer content
        assert content2.startswith(content1), \
            f"Shorter truncation should be prefix of longer truncation"


@given(text=st.text(min_size=1, max_size=1000))
def test_truncation_never_adds_length(text):
    """
    Test that truncation never makes text longer.
    
    The truncated result should always be less than or equal to the
    original text length.
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    max_length = 200
    
    truncated = formatter.truncate_text(text, max_length)
    
    # Truncated text should never be longer than original
    assert len(truncated) <= len(text), \
        f"Truncation should not make text longer: original {len(text)}, truncated {len(truncated)}"


@given(
    text=st.text(min_size=1, max_size=1000),
    max_length=st.integers(min_value=10, max_value=500)
)
def test_truncation_ellipsis_only_when_needed(text, max_length):
    """
    Test that ellipsis is only added when text is actually truncated.
    
    Text that fits within the limit should not have ellipsis added.
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    truncated = formatter.truncate_text(text, max_length)
    
    if len(text) <= max_length:
        # Text fits, should not have ellipsis (unless original had it)
        if not text.endswith("..."):
            assert not truncated.endswith("..."), \
                f"Should not add ellipsis to text that fits"
    else:
        # Text doesn't fit, should have ellipsis
        assert truncated.endswith("..."), \
            f"Should add ellipsis to truncated text"


@given(max_length=st.integers(min_value=4, max_value=10))
def test_truncation_minimum_length(max_length):
    """
    Test that truncation works even with very short max_length.
    
    Even with short limits, truncation should produce valid results
    with ellipsis.
    
    Validates: Requirements 9.4
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Create text longer than max_length
    text = "A" * (max_length + 10)
    
    truncated = formatter.truncate_text(text, max_length)
    
    # Should be exactly max_length
    assert len(truncated) == max_length, \
        f"Should truncate to exactly {max_length} chars"
    
    # Should end with ellipsis
    assert truncated.endswith("..."), \
        f"Should end with ellipsis"
    
    # Should have at least 1 character before ellipsis
    assert len(truncated) >= 4, \
        f"Should have at least 4 chars (1 char + '...')"
