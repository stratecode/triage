# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Token Encryption for Plugin System

Handles AES-256 encryption and decryption of OAuth tokens and sensitive
plugin data. Uses AES-256-CBC with PKCS7 padding for secure storage.

Validates: Requirements 7.1, 7.2, 12.3
"""

import base64
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class TokenEncryption:
    """
    Handles AES-256 encryption and decryption of OAuth tokens.

    Uses AES-256-CBC with PKCS7 padding for secure token storage.
    Each encryption operation uses a unique IV for security.

    Validates: Requirements 12.3
    """

    def __init__(self, encryption_key: str):
        """
        Initialize token encryption with a 32-byte key.

        Args:
            encryption_key: Base64-encoded 32-byte encryption key

        Raises:
            ValueError: If encryption key is invalid
        """
        if len(encryption_key) < 32:
            raise ValueError("Encryption key must be at least 32 characters")

        # Use first 32 bytes of key for AES-256
        self.key = encryption_key[:32].encode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext token using AES-256-CBC.

        Args:
            plaintext: Token to encrypt

        Returns:
            Base64-encoded encrypted token with IV prepended
        """
        # Generate random IV (16 bytes for AES)
        iv = os.urandom(16)

        # Create cipher
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Pad plaintext to block size (16 bytes)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode("utf-8")) + padder.finalize()

        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Prepend IV to ciphertext and encode as base64
        encrypted = iv + ciphertext
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted token using AES-256-CBC.

        Args:
            encrypted: Base64-encoded encrypted token with IV

        Returns:
            Decrypted plaintext token

        Raises:
            ValueError: If decryption fails
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted)

            # Extract IV (first 16 bytes) and ciphertext
            iv = encrypted_bytes[:16]
            ciphertext = encrypted_bytes[16:]

            # Create cipher
            cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()

            # Decrypt
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Unpad
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

            return plaintext.decode("utf-8")

        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
