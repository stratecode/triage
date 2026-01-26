# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
User configuration storage for Slack integration.

This module provides database operations for storing and retrieving
user-specific Slack configuration and preferences.

Validates: Requirements 10.2
"""

import logging
from typing import Optional
from datetime import datetime

import asyncpg
from slack_bot.models import SlackConfig


logger = logging.getLogger(__name__)


class ConfigStorage:
    """
    Database storage for user Slack configurations.
    
    Provides CRUD operations for SlackConfig objects with PostgreSQL backend.
    
    Validates: Requirements 10.2
    """
    
    def __init__(self, database_url: str):
        """
        Initialize configuration storage.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
        
        logger.info("Initialized ConfigStorage")
    
    async def connect(self) -> None:
        """
        Create database connection pool.
        
        Raises:
            Exception: If connection fails
        """
        if self._pool is None:
            logger.info("Creating database connection pool")
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            logger.info("Database connection pool created")
    
    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            logger.info("Closing database connection pool")
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def initialize_schema(self) -> None:
        """
        Create database schema for user configurations.
        
        Creates the slack_user_config table if it doesn't exist.
        
        Raises:
            Exception: If schema creation fails
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        schema_sql = """
        CREATE TABLE IF NOT EXISTS slack_user_config (
            user_id VARCHAR(255) PRIMARY KEY,
            notification_channel VARCHAR(255) NOT NULL,
            delivery_time VARCHAR(5) NOT NULL DEFAULT '09:00',
            notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_slack_user_config_notifications 
        ON slack_user_config(notifications_enabled);
        """
        
        logger.info("Initializing database schema")
        
        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)
        
        logger.info("Database schema initialized successfully")
    
    async def create_config(self, config: SlackConfig) -> SlackConfig:
        """
        Create a new user configuration.
        
        Args:
            config: SlackConfig object to store
            
        Returns:
            Created SlackConfig
            
        Raises:
            Exception: If creation fails or user already exists
            
        Validates: Requirements 10.2
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        insert_sql = """
        INSERT INTO slack_user_config (
            user_id,
            notification_channel,
            delivery_time,
            notifications_enabled,
            timezone,
            created_at,
            updated_at
        ) VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        RETURNING user_id, notification_channel, delivery_time, 
                  notifications_enabled, timezone
        """
        
        logger.info(
            "Creating user config",
            extra={"user_id": config.user_id}
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    insert_sql,
                    config.user_id,
                    config.notification_channel,
                    config.delivery_time,
                    config.notifications_enabled,
                    config.timezone
                )
            
            created_config = SlackConfig(
                user_id=row['user_id'],
                notification_channel=row['notification_channel'],
                delivery_time=row['delivery_time'],
                notifications_enabled=row['notifications_enabled'],
                timezone=row['timezone']
            )
            
            logger.info(
                "User config created successfully",
                extra={"user_id": config.user_id}
            )
            
            return created_config
            
        except asyncpg.UniqueViolationError:
            logger.error(
                "User config already exists",
                extra={"user_id": config.user_id}
            )
            raise ValueError(f"Configuration for user {config.user_id} already exists")
        except Exception as e:
            logger.error(
                "Failed to create user config",
                extra={"user_id": config.user_id, "error": str(e)}
            )
            raise
    
    async def get_config(self, user_id: str) -> Optional[SlackConfig]:
        """
        Retrieve user configuration by user ID.
        
        Args:
            user_id: TrIAge user ID
            
        Returns:
            SlackConfig if found, None otherwise
            
        Validates: Requirements 10.2
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        select_sql = """
        SELECT user_id, notification_channel, delivery_time,
               notifications_enabled, timezone
        FROM slack_user_config
        WHERE user_id = $1
        """
        
        logger.debug(
            "Retrieving user config",
            extra={"user_id": user_id}
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(select_sql, user_id)
            
            if row is None:
                logger.debug(
                    "User config not found",
                    extra={"user_id": user_id}
                )
                return None
            
            config = SlackConfig(
                user_id=row['user_id'],
                notification_channel=row['notification_channel'],
                delivery_time=row['delivery_time'],
                notifications_enabled=row['notifications_enabled'],
                timezone=row['timezone']
            )
            
            logger.debug(
                "User config retrieved",
                extra={"user_id": user_id}
            )
            
            return config
            
        except Exception as e:
            logger.error(
                "Failed to retrieve user config",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def update_config(
        self,
        user_id: str,
        notification_channel: Optional[str] = None,
        delivery_time: Optional[str] = None,
        notifications_enabled: Optional[bool] = None,
        timezone: Optional[str] = None
    ) -> Optional[SlackConfig]:
        """
        Update user configuration.
        
        Only provided fields will be updated. None values are ignored.
        
        Args:
            user_id: TrIAge user ID
            notification_channel: New notification channel (optional)
            delivery_time: New delivery time (optional)
            notifications_enabled: New notification status (optional)
            timezone: New timezone (optional)
            
        Returns:
            Updated SlackConfig if user exists, None otherwise
            
        Validates: Requirements 10.2
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = [user_id]
        param_idx = 2
        
        if notification_channel is not None:
            update_fields.append(f"notification_channel = ${param_idx}")
            params.append(notification_channel)
            param_idx += 1
        
        if delivery_time is not None:
            update_fields.append(f"delivery_time = ${param_idx}")
            params.append(delivery_time)
            param_idx += 1
        
        if notifications_enabled is not None:
            update_fields.append(f"notifications_enabled = ${param_idx}")
            params.append(notifications_enabled)
            param_idx += 1
        
        if timezone is not None:
            update_fields.append(f"timezone = ${param_idx}")
            params.append(timezone)
            param_idx += 1
        
        if not update_fields:
            # No fields to update, just return current config
            return await self.get_config(user_id)
        
        # Always update updated_at timestamp
        update_fields.append("updated_at = NOW()")
        
        update_sql = f"""
        UPDATE slack_user_config
        SET {', '.join(update_fields)}
        WHERE user_id = $1
        RETURNING user_id, notification_channel, delivery_time,
                  notifications_enabled, timezone
        """
        
        logger.info(
            "Updating user config",
            extra={
                "user_id": user_id,
                "fields": [f.split('=')[0].strip() for f in update_fields if 'updated_at' not in f]
            }
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(update_sql, *params)
            
            if row is None:
                logger.warning(
                    "User config not found for update",
                    extra={"user_id": user_id}
                )
                return None
            
            config = SlackConfig(
                user_id=row['user_id'],
                notification_channel=row['notification_channel'],
                delivery_time=row['delivery_time'],
                notifications_enabled=row['notifications_enabled'],
                timezone=row['timezone']
            )
            
            logger.info(
                "User config updated successfully",
                extra={"user_id": user_id}
            )
            
            return config
            
        except Exception as e:
            logger.error(
                "Failed to update user config",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def delete_config(self, user_id: str) -> bool:
        """
        Delete user configuration.
        
        Args:
            user_id: TrIAge user ID
            
        Returns:
            True if config was deleted, False if not found
            
        Validates: Requirements 10.2
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        delete_sql = """
        DELETE FROM slack_user_config
        WHERE user_id = $1
        """
        
        logger.info(
            "Deleting user config",
            extra={"user_id": user_id}
        )
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(delete_sql, user_id)
            
            # Parse result to check if row was deleted
            deleted = result.split()[-1] == '1'
            
            if deleted:
                logger.info(
                    "User config deleted successfully",
                    extra={"user_id": user_id}
                )
            else:
                logger.warning(
                    "User config not found for deletion",
                    extra={"user_id": user_id}
                )
            
            return deleted
            
        except Exception as e:
            logger.error(
                "Failed to delete user config",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def list_configs_with_notifications_enabled(self) -> list[SlackConfig]:
        """
        List all user configurations with notifications enabled.
        
        Useful for batch notification delivery.
        
        Returns:
            List of SlackConfig objects with notifications enabled
            
        Validates: Requirements 10.5
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        select_sql = """
        SELECT user_id, notification_channel, delivery_time,
               notifications_enabled, timezone
        FROM slack_user_config
        WHERE notifications_enabled = TRUE
        ORDER BY user_id
        """
        
        logger.debug("Listing configs with notifications enabled")
        
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(select_sql)
            
            configs = [
                SlackConfig(
                    user_id=row['user_id'],
                    notification_channel=row['notification_channel'],
                    delivery_time=row['delivery_time'],
                    notifications_enabled=row['notifications_enabled'],
                    timezone=row['timezone']
                )
                for row in rows
            ]
            
            logger.debug(
                "Retrieved configs with notifications enabled",
                extra={"count": len(configs)}
            )
            
            return configs
            
        except Exception as e:
            logger.error(
                "Failed to list configs",
                extra={"error": str(e)}
            )
            raise
