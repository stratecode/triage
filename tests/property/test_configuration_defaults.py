# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""Property-based tests for plugin configuration defaults.

Feature: plugin-architecture
"""

import os
import tempfile

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from triage.plugins.config_loader import ConfigLoader


# Custom strategies for generating test data
@st.composite
def schema_with_defaults_strategy(draw):
    """Generate JSON schemas with default values."""
    num_properties = draw(st.integers(min_value=1, max_value=5))
    properties = {}
    defaults_map = {}

    for i in range(num_properties):
        prop_name = f"prop_{i}"
        prop_type = draw(st.sampled_from(["string", "integer", "number", "boolean"]))

        prop_schema = {"type": prop_type}

        # Always add a default value for this test
        if prop_type == "string":
            default_val = draw(st.text(min_size=1, max_size=20))
            prop_schema["default"] = default_val
            defaults_map[prop_name] = default_val
        elif prop_type == "integer":
            default_val = draw(st.integers(min_value=0, max_value=100))
            prop_schema["default"] = default_val
            defaults_map[prop_name] = default_val
        elif prop_type == "number":
            default_val = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            prop_schema["default"] = default_val
            defaults_map[prop_name] = default_val
        elif prop_type == "boolean":
            default_val = draw(st.booleans())
            prop_schema["default"] = default_val
            defaults_map[prop_name] = default_val

        properties[prop_name] = prop_schema

    schema = {"type": "object", "properties": properties}

    return schema, defaults_map


@st.composite
def schema_with_mixed_defaults_strategy(draw):
    """Generate JSON schemas with some properties having defaults and some not."""
    num_properties = draw(st.integers(min_value=2, max_value=6))
    properties = {}
    defaults_map = {}
    required = []

    for i in range(num_properties):
        prop_name = f"prop_{i}"
        prop_type = draw(st.sampled_from(["string", "integer", "number", "boolean"]))

        prop_schema = {"type": prop_type}

        # Randomly decide if this property has a default
        has_default = draw(st.booleans())

        if has_default:
            if prop_type == "string":
                default_val = draw(st.text(min_size=1, max_size=20))
                prop_schema["default"] = default_val
                defaults_map[prop_name] = default_val
            elif prop_type == "integer":
                default_val = draw(st.integers(min_value=0, max_value=100))
                prop_schema["default"] = default_val
                defaults_map[prop_name] = default_val
            elif prop_type == "number":
                default_val = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
                prop_schema["default"] = default_val
                defaults_map[prop_name] = default_val
            elif prop_type == "boolean":
                default_val = draw(st.booleans())
                prop_schema["default"] = default_val
                defaults_map[prop_name] = default_val
        else:
            # Properties without defaults should not be required
            # (otherwise validation would fail)
            pass

        properties[prop_name] = prop_schema

    schema = {"type": "object", "properties": properties}

    # Only make properties with defaults potentially required
    if defaults_map and draw(st.booleans()):
        # Pick some properties with defaults to be required
        required_candidates = list(defaults_map.keys())
        if required_candidates:
            num_required = draw(st.integers(min_value=0, max_value=len(required_candidates)))
            required = draw(
                st.lists(
                    st.sampled_from(required_candidates), min_size=num_required, max_size=num_required, unique=True
                )
            )
            if required:
                schema["required"] = required

    return schema, defaults_map


# Property 19: Configuration Defaults
@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
    schema_data=schema_with_defaults_strategy(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_defaults_applied_when_missing(plugin_name: str, version: str, schema_data):
    """Property 19: Configuration Defaults - Defaults applied

    For any missing optional configuration value that has a default in the schema,
    the Plugin_Registry should use the default value from the schema.

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    schema, expected_defaults = schema_data

    # Create a temporary config directory (empty, no config files)
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = ConfigLoader(config_dir=tmpdir)

        # Clear any environment variables that might interfere
        env_prefix = f"PLUGIN_{plugin_name.upper()}_"
        original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith(env_prefix):
                original_env[key] = os.environ.pop(key)

        try:
            # Load config without providing any values
            # (should use defaults from schema)
            config = loader.load_plugin_config(plugin_name, version, schema)

            # Verify all defaults were applied
            for key, expected_value in expected_defaults.items():
                assert key in config.config, f"Default for '{key}' should be present"
                actual_value = config.config[key]

                # Handle floating point comparison
                if isinstance(expected_value, float):
                    assert (
                        abs(actual_value - expected_value) < 0.0001
                    ), f"Default for '{key}' should be {expected_value}, got {actual_value}"
                else:
                    assert (
                        actual_value == expected_value
                    ), f"Default for '{key}' should be {expected_value}, got {actual_value}"

        finally:
            # Restore environment variables
            os.environ.update(original_env)


@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
    schema_data=schema_with_defaults_strategy(),
    override_value=st.text(min_size=1, max_size=30, alphabet=st.characters(blacklist_characters='"\\')),
)
@settings(max_examples=100, deadline=None)
def test_property_19_explicit_values_override_defaults(
    plugin_name: str, version: str, schema_data, override_value: str
):
    """Property 19: Configuration Defaults - Explicit values override

    For any configuration value explicitly provided (via env var or config file),
    the explicit value should override the default value from the schema.

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    schema, expected_defaults = schema_data

    # Skip if no defaults
    assume(len(expected_defaults) > 0)

    # Pick a property to override (prefer string properties for this test)
    properties = list(expected_defaults.keys())
    override_key = properties[0]

    # Get the property type from schema
    prop_type = schema.get("properties", {}).get(override_key, {}).get("type", "string")

    # Only test with string properties to avoid type conversion issues
    assume(prop_type == "string")

    # Create a temporary config directory (empty)
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = ConfigLoader(config_dir=tmpdir)

        # Set environment variable to override the default
        env_key = f"PLUGIN_{plugin_name.upper()}_{override_key.upper()}"
        original_value = os.environ.get(env_key)

        # Use JSON encoding for the value
        import json

        os.environ[env_key] = json.dumps(override_value)

        try:
            # Load config
            config = loader.load_plugin_config(plugin_name, version, schema)

            # Verify the override was applied
            assert override_key in config.config, f"Key '{override_key}' should be present"
            assert (
                config.config[override_key] == override_value
            ), f"Override value should be '{override_value}', got '{config.config[override_key]}'"

            # Verify other defaults were still applied
            for key, expected_value in expected_defaults.items():
                if key != override_key:
                    assert key in config.config, f"Default for '{key}' should still be present"

        finally:
            # Restore environment
            if original_value is not None:
                os.environ[env_key] = original_value
            else:
                os.environ.pop(env_key, None)


@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
    schema_data=schema_with_mixed_defaults_strategy(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_only_properties_with_defaults_get_defaults(plugin_name: str, version: str, schema_data):
    """Property 19: Configuration Defaults - Only declared defaults applied

    For any schema with mixed properties (some with defaults, some without),
    only properties that declare defaults should receive default values.

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    schema, expected_defaults = schema_data

    # Get all properties from schema
    all_properties = set(schema.get("properties", {}).keys())
    properties_with_defaults = set(expected_defaults.keys())
    properties_without_defaults = all_properties - properties_with_defaults

    # Skip if all properties have defaults or none do
    assume(len(properties_without_defaults) > 0)
    assume(len(properties_with_defaults) > 0)

    # Create a temporary config directory (empty)
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = ConfigLoader(config_dir=tmpdir)

        # Clear any environment variables
        env_prefix = f"PLUGIN_{plugin_name.upper()}_"
        original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith(env_prefix):
                original_env[key] = os.environ.pop(key)

        try:
            # Load config
            config = loader.load_plugin_config(plugin_name, version, schema)

            # Verify properties with defaults received their defaults
            for key in properties_with_defaults:
                assert key in config.config, f"Property '{key}' with default should be present"

            # Verify properties without defaults are NOT present
            # (unless they were required, which would cause validation to fail)
            for key in properties_without_defaults:
                # If the property is not required, it should not be in config
                required = schema.get("required", [])
                if key not in required:
                    assert key not in config.config, f"Property '{key}' without default should not be present"

        finally:
            # Restore environment
            os.environ.update(original_env)


@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
)
@settings(max_examples=100, deadline=None)
def test_property_19_empty_schema_no_defaults(plugin_name: str, version: str):
    """Property 19: Configuration Defaults - Empty schema behavior

    For any schema with no properties or no defaults, the configuration
    should be empty (no spurious defaults added).

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    # Schema with no properties
    schema = {"type": "object", "properties": {}}

    # Create a temporary config directory (empty)
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = ConfigLoader(config_dir=tmpdir)

        # Clear any environment variables
        env_prefix = f"PLUGIN_{plugin_name.upper()}_"
        original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith(env_prefix):
                original_env[key] = os.environ.pop(key)

        try:
            # Load config
            config = loader.load_plugin_config(plugin_name, version, schema)

            # Config should be empty (no defaults to apply)
            assert len(config.config) == 0, "Config should be empty when schema has no properties with defaults"

        finally:
            # Restore environment
            os.environ.update(original_env)


@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
    default_timeout=st.integers(min_value=1, max_value=300),
    default_retries=st.integers(min_value=0, max_value=10),
    default_enabled=st.booleans(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_common_default_patterns(
    plugin_name: str, version: str, default_timeout: int, default_retries: int, default_enabled: bool
):
    """Property 19: Configuration Defaults - Common default patterns

    For any schema with common configuration patterns (timeout, retries),
    the defaults should be applied correctly for various data types.

    Note: 'enabled' is handled specially by load_plugin_config and stored
    in PluginConfig.enabled, not in PluginConfig.config.

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    # Schema with common configuration patterns
    schema = {
        "type": "object",
        "properties": {
            "timeout": {"type": "integer", "default": default_timeout},
            "retries": {"type": "integer", "default": default_retries},
            "enabled": {"type": "boolean", "default": default_enabled},
            "api_key": {
                "type": "string"
                # No default - must be provided
            },
        },
        "required": [],  # Nothing required for this test
    }

    # Create a temporary config directory (empty)
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = ConfigLoader(config_dir=tmpdir)

        # Clear any environment variables
        env_prefix = f"PLUGIN_{plugin_name.upper()}_"
        original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith(env_prefix):
                original_env[key] = os.environ.pop(key)

        try:
            # Load config
            config = loader.load_plugin_config(plugin_name, version, schema)

            # Verify defaults were applied
            assert config.config["timeout"] == default_timeout, f"Default timeout should be {default_timeout}"
            assert config.config["retries"] == default_retries, f"Default retries should be {default_retries}"

            # Note: 'enabled' is handled specially and stored in config.enabled
            # not in config.config, so we check it there
            assert config.enabled == default_enabled, f"Default enabled should be {default_enabled}"

            # Verify api_key is not present (no default)
            assert "api_key" not in config.config, "api_key should not be present (no default)"

        finally:
            # Restore environment
            os.environ.update(original_env)


@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
    schema_data=schema_with_defaults_strategy(),
)
@settings(max_examples=100, deadline=None)
def test_property_19_defaults_extracted_correctly(plugin_name: str, version: str, schema_data):
    """Property 19: Configuration Defaults - Extraction correctness

    For any schema with defaults, the _extract_defaults_from_schema method
    should correctly extract all default values.

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    schema, expected_defaults = schema_data

    loader = ConfigLoader()

    # Extract defaults
    extracted_defaults = loader._extract_defaults_from_schema(schema)

    # Verify all expected defaults were extracted
    assert len(extracted_defaults) == len(
        expected_defaults
    ), f"Should extract {len(expected_defaults)} defaults, got {len(extracted_defaults)}"

    for key, expected_value in expected_defaults.items():
        assert key in extracted_defaults, f"Default for '{key}' should be extracted"
        actual_value = extracted_defaults[key]

        # Handle floating point comparison
        if isinstance(expected_value, float):
            assert (
                abs(actual_value - expected_value) < 0.0001
            ), f"Extracted default for '{key}' should be {expected_value}, got {actual_value}"
        else:
            assert (
                actual_value == expected_value
            ), f"Extracted default for '{key}' should be {expected_value}, got {actual_value}"


@given(
    plugin_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    version=st.text(min_size=1, max_size=10),
    default_list=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
)
@settings(max_examples=100, deadline=None)
def test_property_19_complex_default_types(plugin_name: str, version: str, default_list: list):
    """Property 19: Configuration Defaults - Complex default types

    For any schema with complex default types (arrays, objects),
    the defaults should be applied correctly.

    Feature: plugin-architecture, Property 19: Configuration Defaults
    Validates: Requirements 9.7
    """
    # Schema with array default
    schema = {"type": "object", "properties": {"allowed_channels": {"type": "array", "default": default_list}}}

    # Create a temporary config directory (empty)
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = ConfigLoader(config_dir=tmpdir)

        # Clear any environment variables
        env_prefix = f"PLUGIN_{plugin_name.upper()}_"
        original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith(env_prefix):
                original_env[key] = os.environ.pop(key)

        try:
            # Load config
            config = loader.load_plugin_config(plugin_name, version, schema)

            # Verify array default was applied
            assert "allowed_channels" in config.config, "Array property with default should be present"
            assert (
                config.config["allowed_channels"] == default_list
            ), f"Default array should be {default_list}, got {config.config['allowed_channels']}"

        finally:
            # Restore environment
            os.environ.update(original_env)
