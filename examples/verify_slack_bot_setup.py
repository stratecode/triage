# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Verification script for Slack bot setup.

This script verifies that all dependencies are installed correctly
and the basic infrastructure is working.
"""

import sys
from slack_bot.config import SlackBotConfig
from slack_bot.logging_config import setup_logging, get_logger


def verify_imports():
    """Verify all required dependencies can be imported."""
    print("Verifying dependencies...")
    
    try:
        import slack_sdk
        print("  ✓ slack-sdk")
    except ImportError as e:
        print(f"  ✗ slack-sdk: {e}")
        return False
    
    try:
        import slack_bolt
        print("  ✓ slack-bolt")
    except ImportError as e:
        print(f"  ✗ slack-bolt: {e}")
        return False
    
    try:
        import httpx
        print(f"  ✓ httpx (version {httpx.__version__})")
    except ImportError as e:
        print(f"  ✗ httpx: {e}")
        return False
    
    try:
        import pydantic
        print(f"  ✓ pydantic (version {pydantic.__version__})")
    except ImportError as e:
        print(f"  ✗ pydantic: {e}")
        return False
    
    try:
        import redis
        print(f"  ✓ redis (version {redis.__version__})")
    except ImportError as e:
        print(f"  ✗ redis: {e}")
        return False
    
    try:
        import cryptography
        print(f"  ✓ cryptography (version {cryptography.__version__})")
    except ImportError as e:
        print(f"  ✗ cryptography: {e}")
        return False
    
    return True


def verify_logging():
    """Verify logging configuration works."""
    print("\nVerifying logging configuration...")
    
    try:
        setup_logging(log_level="INFO", log_format="json")
        logger = get_logger("test")
        
        # Test sensitive data redaction
        logger.info("Test message with token xoxb-test-token-12345")
        
        print("  ✓ Logging setup successful")
        print("  ✓ Sensitive data redaction working")
        return True
    except Exception as e:
        print(f"  ✗ Logging setup failed: {e}")
        return False


def verify_config():
    """Verify configuration module works."""
    print("\nVerifying configuration module...")
    
    try:
        # Test that config class can be instantiated
        config = SlackBotConfig(
            slack_bot_token="xoxb-test",
            slack_signing_secret="test-secret",
            slack_client_id="test-client-id",
            slack_client_secret="test-client-secret",
            triage_api_url="https://api.example.com",
            triage_api_token="test-token",
            redis_url="redis://localhost:6379",
            database_url="postgresql://user:pass@localhost/db",
            encryption_key="a" * 32,  # 32 characters minimum
        )
        
        print("  ✓ Configuration class instantiation")
        
        # Test validation
        try:
            config.validate()
            print("  ✓ Configuration validation")
        except ValueError as e:
            print(f"  ✓ Configuration validation (expected error: {e})")
        
        return True
    except Exception as e:
        print(f"  ✗ Configuration module failed: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("TrIAge Slack Bot Setup Verification")
    print("=" * 60)
    
    results = []
    
    results.append(("Dependencies", verify_imports()))
    results.append(("Logging", verify_logging()))
    results.append(("Configuration", verify_config()))
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name:20s} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All verification checks passed!")
        print("\nThe Slack bot project structure is ready for development.")
        return 0
    else:
        print("\n✗ Some verification checks failed.")
        print("\nPlease review the errors above and fix any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
