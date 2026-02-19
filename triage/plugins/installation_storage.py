# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
Plugin Installation Storage

Provides database operations for storing and retrieving plugin installations
with encrypted OAuth tokens.

Validates: Requirements 7.1, 7.2, 7.3, 12.3
"""

import json
import logging
from typing import List, Optional

import asyncpg

from .encryption import TokenEncryption
from .models import PluginInstallation

logger = logging.getLogger(__name__)


class PluginInstallationStorage:
    """
    Database storage for plugin installations.

    Provides CRUD operations for PluginInstallation objects with PostgreSQL backend.
    Handles encryption/decryption of OAuth tokens transparently.

    Validates: Requirements 7.1, 7.2, 7.3, 12.3
    """

    def __init__(self, database_url: str, encryption_key: str):
        """
        Initialize plugin installation storage.

        Args:
            database_url: PostgreSQL connection URL
            encryption_key: 32-character encryption key for token encryption
        """
        self.database_url = database_url
        self.encryption = TokenEncryption(encryption_key)
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("Initialized PluginInstallationStorage")

    async def connect(self) -> None:
        """
        Create database connection pool.

        Raises:
            Exception: If connection fails
        """
        if self._pool is None:
            logger.info("Creating database connection pool for plugin installations")
            self._pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10, command_timeout=30)
            logger.info("Database connection pool created for plugin installations")

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            logger.info("Closing database connection pool for plugin installations")
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed for plugin installations")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def initialize_schema(self) -> None:
        """
        Create database schema for plugin installations.

        Creates the plugin_installations table if it doesn't exist.

        Raises:
            Exception: If schema creation fails

        Validates: Requirements 7.1, 7.2, 12.3
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        schema_sql = """
        CREATE TABLE IF NOT EXISTS plugin_installations (
            id SERIAL PRIMARY KEY,
            plugin_name VARCHAR(50) NOT NULL,
            channel_id VARCHAR(255) NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            metadata JSONB,
            installed_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_active TIMESTAMP NOT NULL DEFAULT NOW(),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE(plugin_name, channel_id)
        );

        CREATE INDEX IF NOT EXISTS idx_plugin_installations_plugin_name
        ON plugin_installations(plugin_name);

        CREATE INDEX IF NOT EXISTS idx_plugin_installations_channel_id
        ON plugin_installations(channel_id);

        CREATE INDEX IF NOT EXISTS idx_plugin_installations_active
        ON plugin_installations(is_active) WHERE is_active = TRUE;
        """

        logger.info("Initializing plugin installations database schema")

        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)

        logger.info("Plugin installations database schema initialized successfully")

    async def create_installation(self, installation: PluginInstallation) -> PluginInstallation:
        """
        Create a new plugin installation.

        Encrypts access_token and refresh_token before storage.

        Args:
            installation: PluginInstallation object to store

        Returns:
            Created PluginInstallation with id populated

        Raises:
            ValueError: If installation already exists
            Exception: If creation fails

        Validates: Requirements 7.1, 7.2, 12.3
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        # Encrypt tokens
        encrypted_access_token = self.encryption.encrypt(installation.access_token)
        encrypted_refresh_token = None
        if installation.refresh_token:
            encrypted_refresh_token = self.encryption.encrypt(installation.refresh_token)

        insert_sql = """
        INSERT INTO plugin_installations (
            plugin_name,
            channel_id,
            access_token,
            refresh_token,
            metadata,
            installed_at,
            last_active,
            is_active
        ) VALUES ($1, $2, $3, $4, $5, NOW(), NOW(), $6)
        RETURNING id, plugin_name, channel_id, access_token, refresh_token,
                  metadata, installed_at, last_active, is_active
        """

        logger.info(
            "Creating plugin installation",
            extra={"plugin_name": installation.plugin_name, "channel_id": installation.channel_id},
        )

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    insert_sql,
                    installation.plugin_name,
                    installation.channel_id,
                    encrypted_access_token,
                    encrypted_refresh_token,
                    json.dumps(installation.metadata) if installation.metadata else None,
                    installation.is_active,
                )

            # Decrypt tokens and parse metadata
            created_installation = PluginInstallation(
                id=row["id"],
                plugin_name=row["plugin_name"],
                channel_id=row["channel_id"],
                access_token=self.encryption.decrypt(row["access_token"]),
                refresh_token=self.encryption.decrypt(row["refresh_token"]) if row["refresh_token"] else None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                installed_at=row["installed_at"],
                last_active=row["last_active"],
                is_active=row["is_active"],
            )

            logger.info(
                "Plugin installation created successfully",
                extra={
                    "plugin_name": installation.plugin_name,
                    "channel_id": installation.channel_id,
                    "id": created_installation.id,
                },
            )

            return created_installation

        except asyncpg.UniqueViolationError:
            logger.error(
                "Plugin installation already exists",
                extra={"plugin_name": installation.plugin_name, "channel_id": installation.channel_id},
            )
            raise ValueError(
                f"Installation for plugin {installation.plugin_name} "
                f"in channel {installation.channel_id} already exists"
            )
        except Exception as e:
            logger.error(
                "Failed to create plugin installation",
                extra={"plugin_name": installation.plugin_name, "channel_id": installation.channel_id, "error": str(e)},
            )
            raise

    async def get_installation(self, plugin_name: str, channel_id: str) -> Optional[PluginInstallation]:
        """
        Retrieve plugin installation by plugin name and channel ID.

        Decrypts tokens before returning.

        Args:
            plugin_name: Plugin name (e.g., 'slack', 'whatsapp')
            channel_id: Channel identifier (workspace_id, phone_number, etc.)

        Returns:
            PluginInstallation if found, None otherwise

        Validates: Requirements 7.1, 7.2, 12.3
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        select_sql = """
        SELECT id, plugin_name, channel_id, access_token, refresh_token,
               metadata, installed_at, last_active, is_active
        FROM plugin_installations
        WHERE plugin_name = $1 AND channel_id = $2
        """

        logger.debug("Retrieving plugin installation", extra={"plugin_name": plugin_name, "channel_id": channel_id})

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(select_sql, plugin_name, channel_id)

            if row is None:
                logger.debug(
                    "Plugin installation not found", extra={"plugin_name": plugin_name, "channel_id": channel_id}
                )
                return None

            # Decrypt tokens
            installation = PluginInstallation(
                id=row["id"],
                plugin_name=row["plugin_name"],
                channel_id=row["channel_id"],
                access_token=self.encryption.decrypt(row["access_token"]),
                refresh_token=self.encryption.decrypt(row["refresh_token"]) if row["refresh_token"] else None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                installed_at=row["installed_at"],
                last_active=row["last_active"],
                is_active=row["is_active"],
            )

            logger.debug(
                "Plugin installation retrieved",
                extra={"plugin_name": plugin_name, "channel_id": channel_id, "id": installation.id},
            )

            return installation

        except Exception as e:
            logger.error(
                "Failed to retrieve plugin installation",
                extra={"plugin_name": plugin_name, "channel_id": channel_id, "error": str(e)},
            )
            raise

    async def get_installation_by_id(self, installation_id: int) -> Optional[PluginInstallation]:
        """
        Retrieve plugin installation by ID.

        Args:
            installation_id: Installation ID

        Returns:
            PluginInstallation if found, None otherwise
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        select_sql = """
        SELECT id, plugin_name, channel_id, access_token, refresh_token,
               metadata, installed_at, last_active, is_active
        FROM plugin_installations
        WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(select_sql, installation_id)

            if row is None:
                return None

            return PluginInstallation(
                id=row["id"],
                plugin_name=row["plugin_name"],
                channel_id=row["channel_id"],
                access_token=self.encryption.decrypt(row["access_token"]),
                refresh_token=self.encryption.decrypt(row["refresh_token"]) if row["refresh_token"] else None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                installed_at=row["installed_at"],
                last_active=row["last_active"],
                is_active=row["is_active"],
            )

        except Exception as e:
            logger.error(
                "Failed to retrieve plugin installation by ID",
                extra={"installation_id": installation_id, "error": str(e)},
            )
            raise

    async def update_installation(
        self,
        plugin_name: str,
        channel_id: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        metadata: Optional[dict] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[PluginInstallation]:
        """
        Update plugin installation.

        Only provided fields will be updated. None values are ignored.
        Tokens are encrypted before storage.

        Args:
            plugin_name: Plugin name
            channel_id: Channel identifier
            access_token: New access token (optional)
            refresh_token: New refresh token (optional)
            metadata: New metadata (optional)
            is_active: New active status (optional)

        Returns:
            Updated PluginInstallation if exists, None otherwise

        Validates: Requirements 7.2, 12.3
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = [plugin_name, channel_id]
        param_idx = 3

        if access_token is not None:
            encrypted_token = self.encryption.encrypt(access_token)
            update_fields.append(f"access_token = ${param_idx}")
            params.append(encrypted_token)
            param_idx += 1

        if refresh_token is not None:
            encrypted_token = self.encryption.encrypt(refresh_token)
            update_fields.append(f"refresh_token = ${param_idx}")
            params.append(encrypted_token)
            param_idx += 1

        if metadata is not None:
            update_fields.append(f"metadata = ${param_idx}")
            params.append(json.dumps(metadata))
            param_idx += 1

        if is_active is not None:
            update_fields.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if not update_fields:
            # No fields to update, just return current installation
            return await self.get_installation(plugin_name, channel_id)

        # Always update last_active timestamp
        update_fields.append("last_active = NOW()")

        update_sql = f"""
        UPDATE plugin_installations
        SET {', '.join(update_fields)}
        WHERE plugin_name = $1 AND channel_id = $2
        RETURNING id, plugin_name, channel_id, access_token, refresh_token,
                  metadata, installed_at, last_active, is_active
        """

        logger.info(
            "Updating plugin installation",
            extra={
                "plugin_name": plugin_name,
                "channel_id": channel_id,
                "fields": [f.split("=")[0].strip() for f in update_fields if "last_active" not in f],
            },
        )

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(update_sql, *params)

            if row is None:
                logger.warning(
                    "Plugin installation not found for update",
                    extra={"plugin_name": plugin_name, "channel_id": channel_id},
                )
                return None

            installation = PluginInstallation(
                id=row["id"],
                plugin_name=row["plugin_name"],
                channel_id=row["channel_id"],
                access_token=self.encryption.decrypt(row["access_token"]),
                refresh_token=self.encryption.decrypt(row["refresh_token"]) if row["refresh_token"] else None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                installed_at=row["installed_at"],
                last_active=row["last_active"],
                is_active=row["is_active"],
            )

            logger.info(
                "Plugin installation updated successfully", extra={"plugin_name": plugin_name, "channel_id": channel_id}
            )

            return installation

        except Exception as e:
            logger.error(
                "Failed to update plugin installation",
                extra={"plugin_name": plugin_name, "channel_id": channel_id, "error": str(e)},
            )
            raise

    async def delete_installation(self, plugin_name: str, channel_id: str) -> bool:
        """
        Delete plugin installation.

        Args:
            plugin_name: Plugin name
            channel_id: Channel identifier

        Returns:
            True if installation was deleted, False if not found

        Validates: Requirements 7.3
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        delete_sql = """
        DELETE FROM plugin_installations
        WHERE plugin_name = $1 AND channel_id = $2
        """

        logger.info("Deleting plugin installation", extra={"plugin_name": plugin_name, "channel_id": channel_id})

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(delete_sql, plugin_name, channel_id)

            # Parse result to check if row was deleted
            deleted = result.split()[-1] == "1"

            if deleted:
                logger.info(
                    "Plugin installation deleted successfully",
                    extra={"plugin_name": plugin_name, "channel_id": channel_id},
                )
            else:
                logger.warning(
                    "Plugin installation not found for deletion",
                    extra={"plugin_name": plugin_name, "channel_id": channel_id},
                )

            return deleted

        except Exception as e:
            logger.error(
                "Failed to delete plugin installation",
                extra={"plugin_name": plugin_name, "channel_id": channel_id, "error": str(e)},
            )
            raise

    async def list_plugin_installations(self, plugin_name: str, active_only: bool = True) -> List[PluginInstallation]:
        """
        List all installations for a specific plugin.

        Args:
            plugin_name: Plugin name
            active_only: If True, only return active installations

        Returns:
            List of PluginInstallation objects
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        if active_only:
            select_sql = """
            SELECT id, plugin_name, channel_id, access_token, refresh_token,
                   metadata, installed_at, last_active, is_active
            FROM plugin_installations
            WHERE plugin_name = $1 AND is_active = TRUE
            ORDER BY installed_at DESC
            """
        else:
            select_sql = """
            SELECT id, plugin_name, channel_id, access_token, refresh_token,
                   metadata, installed_at, last_active, is_active
            FROM plugin_installations
            WHERE plugin_name = $1
            ORDER BY installed_at DESC
            """

        logger.debug("Listing plugin installations", extra={"plugin_name": plugin_name, "active_only": active_only})

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(select_sql, plugin_name)

            installations = [
                PluginInstallation(
                    id=row["id"],
                    plugin_name=row["plugin_name"],
                    channel_id=row["channel_id"],
                    access_token=self.encryption.decrypt(row["access_token"]),
                    refresh_token=self.encryption.decrypt(row["refresh_token"]) if row["refresh_token"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    installed_at=row["installed_at"],
                    last_active=row["last_active"],
                    is_active=row["is_active"],
                )
                for row in rows
            ]

            logger.debug(
                "Retrieved plugin installations", extra={"plugin_name": plugin_name, "count": len(installations)}
            )

            return installations

        except Exception as e:
            logger.error("Failed to list plugin installations", extra={"plugin_name": plugin_name, "error": str(e)})
            raise

    async def list_all_installations(self, active_only: bool = True) -> List[PluginInstallation]:
        """
        List all plugin installations across all plugins.

        Args:
            active_only: If True, only return active installations

        Returns:
            List of PluginInstallation objects
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        if active_only:
            select_sql = """
            SELECT id, plugin_name, channel_id, access_token, refresh_token,
                   metadata, installed_at, last_active, is_active
            FROM plugin_installations
            WHERE is_active = TRUE
            ORDER BY plugin_name, installed_at DESC
            """
        else:
            select_sql = """
            SELECT id, plugin_name, channel_id, access_token, refresh_token,
                   metadata, installed_at, last_active, is_active
            FROM plugin_installations
            ORDER BY plugin_name, installed_at DESC
            """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(select_sql)

            installations = [
                PluginInstallation(
                    id=row["id"],
                    plugin_name=row["plugin_name"],
                    channel_id=row["channel_id"],
                    access_token=self.encryption.decrypt(row["access_token"]),
                    refresh_token=self.encryption.decrypt(row["refresh_token"]) if row["refresh_token"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    installed_at=row["installed_at"],
                    last_active=row["last_active"],
                    is_active=row["is_active"],
                )
                for row in rows
            ]

            return installations

        except Exception as e:
            logger.error("Failed to list all plugin installations", extra={"error": str(e)})
            raise
