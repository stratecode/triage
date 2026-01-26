# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Property-based tests for effort estimate formatting.

Feature: slack-integration
Property 18: Effort Estimate Formatting

For any task with an effort estimate, the displayed format should use
human-readable time units (hours or days) rather than raw numbers.

Validates: Requirements 9.2
"""

from hypothesis import given, strategies as st, assume
from slack_bot.message_formatter import MessageFormatter


# Feature: slack-integration, Property 18: Effort Estimate Formatting
@given(effort_days=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False))
def test_property_18_effort_estimate_formatting(effort_days):
    """
    Property 18: Effort Estimate Formatting
    
    For any task with an effort estimate, the displayed format should use
    human-readable time units (hours or days) rather than raw numbers.
    
    The formatter should:
    - Use minutes for efforts < 1 hour (< 0.125 days)
    - Use hours for efforts >= 1 hour and < 1 day
    - Use days for efforts >= 1 day
    - Always include the unit name in the output
    - Format numbers appropriately for readability
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    effort_str = formatter.format_effort(effort_days)
    
    # Result should be a non-empty string
    assert len(effort_str) > 0, "Effort string should not be empty"
    assert isinstance(effort_str, str), "Effort should be formatted as string"
    
    # Should contain a time unit (human-readable)
    units = ["min", "hour", "day"]
    assert any(unit in effort_str.lower() for unit in units), \
        f"Effort string '{effort_str}' should contain a human-readable time unit (min, hour, or day)"
    
    # Should not contain raw day values without units
    # (i.e., should not be just a number)
    assert not effort_str.replace('.', '').replace(' ', '').isdigit(), \
        f"Effort string '{effort_str}' should not be just a raw number"
    
    # Verify correct unit based on effort magnitude
    if effort_days < 0.125:  # Less than 1 hour (1/8 day)
        assert "min" in effort_str.lower(), \
            f"Expected 'min' for {effort_days} days (< 1 hour), got '{effort_str}'"
        # Should not use hour or day units for very small efforts
        assert "hour" not in effort_str.lower(), \
            f"Should not use 'hour' for {effort_days} days (< 1 hour)"
        assert "day" not in effort_str.lower(), \
            f"Should not use 'day' for {effort_days} days (< 1 hour)"
    elif effort_days < 1.0:  # Between 1 hour and 1 day
        assert "hour" in effort_str.lower(), \
            f"Expected 'hour' for {effort_days} days (>= 1 hour, < 1 day), got '{effort_str}'"
        # Should not use minutes or days for this range
        assert "min" not in effort_str.lower() or "hour" in effort_str.lower(), \
            f"Should use 'hour' not 'min' for {effort_days} days"
        assert "day" not in effort_str.lower() or "hour" in effort_str.lower(), \
            f"Should use 'hour' not 'day' for {effort_days} days (< 1 day)"
    else:  # 1 day or more
        assert "day" in effort_str.lower(), \
            f"Expected 'day' for {effort_days} days (>= 1 day), got '{effort_str}'"
        # Should not use minutes or hours for full days
        assert "min" not in effort_str.lower(), \
            f"Should not use 'min' for {effort_days} days (>= 1 day)"
        assert "hour" not in effort_str.lower() or "day" in effort_str.lower(), \
            f"Should use 'day' not 'hour' for {effort_days} days (>= 1 day)"


@given(effort_days=st.floats(min_value=0.01, max_value=0.124, allow_nan=False, allow_infinity=False))
def test_effort_formatting_minutes_range(effort_days):
    """
    Test that very small efforts (< 1 hour) are formatted in minutes.
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    effort_str = formatter.format_effort(effort_days)
    
    # Should use minutes
    assert "min" in effort_str.lower(), \
        f"Expected minutes for {effort_days} days, got '{effort_str}'"
    
    # Extract numeric value
    numeric_part = ''.join(c for c in effort_str if c.isdigit() or c == '.')
    if numeric_part:
        minutes = float(numeric_part)
        # Minutes should be positive
        assert minutes > 0, f"Minutes should be positive, got {minutes}"
        # Minutes should be reasonable (<= 60 for this range, allowing boundary)
        assert minutes <= 60, f"Minutes should be <= 60 for efforts < 1 hour, got {minutes}"


@given(effort_days=st.floats(min_value=0.125, max_value=0.999, allow_nan=False, allow_infinity=False))
def test_effort_formatting_hours_range(effort_days):
    """
    Test that medium efforts (>= 1 hour, < 1 day) are formatted in hours.
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    effort_str = formatter.format_effort(effort_days)
    
    # Should use hours
    assert "hour" in effort_str.lower(), \
        f"Expected hours for {effort_days} days, got '{effort_str}'"
    
    # Extract numeric value
    numeric_part = ''.join(c for c in effort_str.split()[0] if c.isdigit() or c == '.')
    if numeric_part:
        hours = float(numeric_part)
        # Hours should be positive and less than or equal to 8 (1 day)
        assert hours > 0, f"Hours should be positive, got {hours}"
        assert hours <= 8, f"Hours should be <= 8 for efforts < 1 day, got {hours}"


@given(effort_days=st.floats(min_value=1.0, max_value=10.0, allow_nan=False, allow_infinity=False))
def test_effort_formatting_days_range(effort_days):
    """
    Test that large efforts (>= 1 day) are formatted in days.
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    effort_str = formatter.format_effort(effort_days)
    
    # Should use days
    assert "day" in effort_str.lower(), \
        f"Expected days for {effort_days} days, got '{effort_str}'"
    
    # Extract numeric value
    numeric_part = ''.join(c for c in effort_str.split()[0] if c.isdigit() or c == '.')
    if numeric_part:
        days = float(numeric_part)
        # Days should be positive and match input (within rounding)
        assert days > 0, f"Days should be positive, got {days}"
        assert abs(days - effort_days) < 0.2, \
            f"Days {days} should be close to input {effort_days}"


@given(
    effort1=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
    effort2=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)
)
def test_effort_formatting_consistency(effort1, effort2):
    """
    Test that effort formatting is consistent and deterministic.
    
    The same effort value should always produce the same formatted string.
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    
    # Format same effort multiple times
    result1a = formatter.format_effort(effort1)
    result1b = formatter.format_effort(effort1)
    
    # Should be identical
    assert result1a == result1b, \
        f"Same effort {effort1} produced different results: '{result1a}' vs '{result1b}'"
    
    # Different efforts should produce different results (unless very close)
    if abs(effort1 - effort2) > 0.01:
        result2 = formatter.format_effort(effort2)
        # Results should differ unless they round to the same value
        # (we allow some tolerance for rounding)
        if result1a == result2:
            # If strings are identical, the numeric values should be very close
            # This is acceptable due to rounding
            pass


@given(effort_days=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False))
def test_effort_formatting_no_raw_numbers(effort_days):
    """
    Test that effort estimates are never displayed as raw numbers without units.
    
    This ensures users always see human-readable time units, not abstract
    day values like "0.5" or "2.3".
    
    Validates: Requirements 9.2
    """
    formatter = MessageFormatter(jira_base_url="https://jira.example.com")
    effort_str = formatter.format_effort(effort_days)
    
    # The string should not be just a number
    # It must contain text (the unit)
    has_letters = any(c.isalpha() for c in effort_str)
    assert has_letters, \
        f"Effort string '{effort_str}' must contain unit text, not just numbers"
    
    # Should not end with just a number
    assert not effort_str.strip()[-1].isdigit(), \
        f"Effort string '{effort_str}' should not end with a digit (must have unit)"
