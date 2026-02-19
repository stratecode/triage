# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Unit tests for plugin token encryption.

Tests the AES-256-CBC encryption and decryption of OAuth tokens.
"""

import pytest

from triage.plugins.encryption import TokenEncryption


class TestTokenEncryption:
    """Test suite for TokenEncryption class."""

    def test_encryption_key_validation(self):
        """Test that encryption key must be at least 32 characters."""
        # Valid key
        TokenEncryption("a" * 32)

        # Invalid key (too short)
        with pytest.raises(ValueError, match="at least 32 characters"):
            TokenEncryption("short")

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are inverse operations."""
        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        plaintext = "xoxb-test-slack-token-12345"
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext  # Ensure it's actually encrypted

    def test_encrypted_tokens_are_different(self):
        """Test that encrypting the same token twice produces different ciphertext."""
        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        plaintext = "xoxb-test-token"
        encrypted1 = encryption.encrypt(plaintext)
        encrypted2 = encryption.encrypt(plaintext)

        # Different ciphertext due to random IV
        assert encrypted1 != encrypted2

        # But both decrypt to the same plaintext
        assert encryption.decrypt(encrypted1) == plaintext
        assert encryption.decrypt(encrypted2) == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        encryption1 = TokenEncryption("key-one-has-32-characters-min-11")
        encryption2 = TokenEncryption("key-two-has-32-characters-min-22")

        plaintext = "xoxb-test-token"
        encrypted = encryption1.encrypt(plaintext)

        # Decryption with wrong key should fail
        with pytest.raises(ValueError, match="Decryption failed"):
            encryption2.decrypt(encrypted)

    def test_decrypt_invalid_data_fails(self):
        """Test that decrypting invalid data fails gracefully."""
        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        with pytest.raises(ValueError, match="Decryption failed"):
            encryption.decrypt("invalid-base64-data")

    def test_encrypt_empty_string(self):
        """Test encrypting and decrypting empty string."""
        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        plaintext = ""
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_long_token(self):
        """Test encrypting and decrypting a long token."""
        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        # Simulate a long OAuth token
        plaintext = "xoxb-" + "a" * 500
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_unicode_characters(self):
        """Test encrypting and decrypting unicode characters."""
        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        plaintext = "token-with-unicode-émojis-🔐-test"
        encrypted = encryption.encrypt(plaintext)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypted_output_is_base64(self):
        """Test that encrypted output is valid base64."""
        import base64

        encryption = TokenEncryption("test-encryption-key-32-chars-min")

        plaintext = "xoxb-test-token"
        encrypted = encryption.encrypt(plaintext)

        # Should be valid base64
        try:
            base64.b64decode(encrypted)
        except Exception:
            pytest.fail("Encrypted output is not valid base64")
