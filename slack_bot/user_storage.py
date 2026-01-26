# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

"""
User mapping storage for Slack integration.

This module provides database operations for storing and retrieving
Slack-to-TrIAge user mappings.

Validates: Requirements 8.1
"""

import logging
from typing import Optional
from datetime import datetime

import asyncpg
from slack_bot.models import SlackUser


logger = logging.getLogger(__name__)


class UserMappingStorage:
    """
    Database storage for Slack user mappings.
    
    Provides CRUD operations for SlackUser objects with PostgreSQL backend.
    
    Validates: Requirements 8.1
    """
    
    def __init__(self, database_url: str):
        """
        Initialize user mapping storage.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
        
        logger.info("Initialized UserMappingStorage")
    
    async def connect(self) -> None:
        """
        Create database connection pool.
        
        Raises:
            Exception: If connection fails
        """
        if self._pool is None:
            logger.info("Creating database connection pool for user mappings")
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            logger.info("Database connection pool created for user mappings")
    
    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            logger.info("Closing database connection pool for user mappings")
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed for user mappings")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def initialize_schema(self) -> None:
        """
        Create database schema for user mappings.
        
        Creates the slack_user_mapping table if it doesn't exist.
        
        Raises:
            Exception: If schema creation fails
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        schema_sql = """
        CREATE TABLE IF NOT EXISTS slack_user_mapping (
            slack_user_id VARCHAR(20) NOT NULL,
            slack_team_id VARCHAR(20) NOT NULL,
            triage_user_id VARCHAR(255) NOT NULL,
            jira_email VARCHAR(255) NOT NULL,
            display_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (slack_user_id, slack_team_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_slack_user_mapping_triage_user 
        ON slack_user_mapping(triage_user_id);
        
        CREATE INDEX IF NOT EXISTS idx_slack_user_mapping_team 
        ON slack_user_mapping(slack_team_id);
        
        CREATE INDEX IF NOT EXISTS idx_slack_user_mapping_jira_email 
        ON slack_user_mapping(jira_email);
        """
        
        logger.info("Initializing user mapping database schema")
        
        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)
        
        logger.info("User mapping database schema initialized successfully")
    
    async def create_mapping(self, slack_user: SlackUser) -> SlackUser:
        """
        Create a new user mapping.
        
        Args:
            slack_user: SlackUser object to store
            
        Returns:
            Created SlackUser
            
        Raises:
            ValueError: If mapping already exists
            Exception: If creation fails
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        insert_sql = """
        INSERT INTO slack_user_mapping (
            slack_user_id,
            slack_team_id,
            triage_user_id,
            jira_email,
            display_name,
            created_at,
            updated_at
        ) VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        RETURNING slack_user_id, slack_team_id, triage_user_id, 
                  jira_email, display_name
        """
        
        logger.info(
            "Creating user mapping",
            extra={
                "slack_user_id": slack_user.slack_user_id,
                "slack_team_id": slack_user.slack_team_id,
                "triage_user_id": slack_user.triage_user_id
            }
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    insert_sql,
                    slack_user.slack_user_id,
                    slack_user.slack_team_id,
                    slack_user.triage_user_id,
                    slack_user.jira_email,
                    slack_user.display_name
                )
            
            created_user = SlackUser(
                slack_user_id=row['slack_user_id'],
                slack_team_id=row['slack_team_id'],
                triage_user_id=row['triage_user_id'],
                jira_email=row['jira_email'],
                display_name=row['display_name']
            )
            
            logger.info(
                "User mapping created successfully",
                extra={
                    "slack_user_id": slack_user.slack_user_id,
                    "slack_team_id": slack_user.slack_team_id
                }
            )
            
            return created_user
            
        except asyncpg.UniqueViolationError:
            logger.error(
                "User mapping already exists",
                extra={
                    "slack_user_id": slack_user.slack_user_id,
                    "slack_team_id": slack_user.slack_team_id
                }
            )
            raise ValueError(
                f"Mapping for user {slack_user.slack_user_id} "
                f"in team {slack_user.slack_team_id} already exists"
            )
        except Exception as e:
            logger.error(
                "Failed to create user mapping",
                extra={
                    "slack_user_id": slack_user.slack_user_id,
                    "slack_team_id": slack_user.slack_team_id,
                    "error": str(e)
                }
            )
            raise
    
    async def get_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str
    ) -> Optional[SlackUser]:
        """
        Retrieve user mapping by Slack user ID and team ID.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            
        Returns:
            SlackUser if found, None otherwise
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        select_sql = """
        SELECT slack_user_id, slack_team_id, triage_user_id,
               jira_email, display_name
        FROM slack_user_mapping
        WHERE slack_user_id = $1 AND slack_team_id = $2
        """
        
        logger.debug(
            "Retrieving user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id
            }
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(select_sql, slack_user_id, slack_team_id)
            
            if row is None:
                logger.debug(
                    "User mapping not found",
                    extra={
                        "slack_user_id": slack_user_id,
                        "slack_team_id": slack_team_id
                    }
                )
                return None
            
            slack_user = SlackUser(
                slack_user_id=row['slack_user_id'],
                slack_team_id=row['slack_team_id'],
                triage_user_id=row['triage_user_id'],
                jira_email=row['jira_email'],
                display_name=row['display_name']
            )
            
            logger.debug(
                "User mapping retrieved",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id,
                    "triage_user_id": slack_user.triage_user_id
                }
            )
            
            return slack_user
            
        except Exception as e:
            logger.error(
                "Failed to retrieve user mapping",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id,
                    "error": str(e)
                }
            )
            raise
    
    async def get_by_triage_user_id(
        self,
        triage_user_id: str
    ) -> Optional[SlackUser]:
        """
        Retrieve user mapping by TrIAge user ID.
        
        Args:
            triage_user_id: TrIAge internal user ID
            
        Returns:
            SlackUser if found, None otherwise
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        select_sql = """
        SELECT slack_user_id, slack_team_id, triage_user_id,
               jira_email, display_name
        FROM slack_user_mapping
        WHERE triage_user_id = $1
        LIMIT 1
        """
        
        logger.debug(
            "Retrieving user mapping by TrIAge user ID",
            extra={"triage_user_id": triage_user_id}
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(select_sql, triage_user_id)
            
            if row is None:
                logger.debug(
                    "User mapping not found by TrIAge user ID",
                    extra={"triage_user_id": triage_user_id}
                )
                return None
            
            slack_user = SlackUser(
                slack_user_id=row['slack_user_id'],
                slack_team_id=row['slack_team_id'],
                triage_user_id=row['triage_user_id'],
                jira_email=row['jira_email'],
                display_name=row['display_name']
            )
            
            logger.debug(
                "User mapping retrieved by TrIAge user ID",
                extra={
                    "triage_user_id": triage_user_id,
                    "slack_user_id": slack_user.slack_user_id
                }
            )
            
            return slack_user
            
        except Exception as e:
            logger.error(
                "Failed to retrieve user mapping by TrIAge user ID",
                extra={"triage_user_id": triage_user_id, "error": str(e)}
            )
            raise
    
    async def update_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str,
        jira_email: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> Optional[SlackUser]:
        """
        Update user mapping.
        
        Only provided fields will be updated. None values are ignored.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            jira_email: New JIRA email (optional)
            display_name: New display name (optional)
            
        Returns:
            Updated SlackUser if user exists, None otherwise
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = [slack_user_id, slack_team_id]
        param_idx = 3
        
        if jira_email is not None:
            update_fields.append(f"jira_email = ${param_idx}")
            params.append(jira_email)
            param_idx += 1
        
        if display_name is not None:
            update_fields.append(f"display_name = ${param_idx}")
            params.append(display_name)
            param_idx += 1
        
        if not update_fields:
            # No fields to update, just return current mapping
            return await self.get_mapping(slack_user_id, slack_team_id)
        
        # Always update updated_at timestamp
        update_fields.append("updated_at = NOW()")
        
        update_sql = f"""
        UPDATE slack_user_mapping
        SET {', '.join(update_fields)}
        WHERE slack_user_id = $1 AND slack_team_id = $2
        RETURNING slack_user_id, slack_team_id, triage_user_id,
                  jira_email, display_name
        """
        
        logger.info(
            "Updating user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id,
                "fields": [f.split('=')[0].strip() for f in update_fields if 'updated_at' not in f]
            }
        )
        
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(update_sql, *params)
            
            if row is None:
                logger.warning(
                    "User mapping not found for update",
                    extra={
                        "slack_user_id": slack_user_id,
                        "slack_team_id": slack_team_id
                    }
                )
                return None
            
            slack_user = SlackUser(
                slack_user_id=row['slack_user_id'],
                slack_team_id=row['slack_team_id'],
                triage_user_id=row['triage_user_id'],
                jira_email=row['jira_email'],
                display_name=row['display_name']
            )
            
            logger.info(
                "User mapping updated successfully",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id
                }
            )
            
            return slack_user
            
        except Exception as e:
            logger.error(
                "Failed to update user mapping",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id,
                    "error": str(e)
                }
            )
            raise
    
    async def delete_mapping(
        self,
        slack_user_id: str,
        slack_team_id: str
    ) -> bool:
        """
        Delete user mapping.
        
        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack workspace/team ID
            
        Returns:
            True if mapping was deleted, False if not found
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        delete_sql = """
        DELETE FROM slack_user_mapping
        WHERE slack_user_id = $1 AND slack_team_id = $2
        """
        
        logger.info(
            "Deleting user mapping",
            extra={
                "slack_user_id": slack_user_id,
                "slack_team_id": slack_team_id
            }
        )
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(delete_sql, slack_user_id, slack_team_id)
            
            # Parse result to check if row was deleted
            deleted = result.split()[-1] == '1'
            
            if deleted:
                logger.info(
                    "User mapping deleted successfully",
                    extra={
                        "slack_user_id": slack_user_id,
                        "slack_team_id": slack_team_id
                    }
                )
            else:
                logger.warning(
                    "User mapping not found for deletion",
                    extra={
                        "slack_user_id": slack_user_id,
                        "slack_team_id": slack_team_id
                    }
                )
            
            return deleted
            
        except Exception as e:
            logger.error(
                "Failed to delete user mapping",
                extra={
                    "slack_user_id": slack_user_id,
                    "slack_team_id": slack_team_id,
                    "error": str(e)
                }
            )
            raise
    
    async def list_workspace_mappings(self, slack_team_id: str) -> list[SlackUser]:
        """
        List all user mappings for a workspace.
        
        Args:
            slack_team_id: Slack workspace/team ID
            
        Returns:
            List of SlackUser mappings for the workspace
            
        Validates: Requirements 8.1
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        select_sql = """
        SELECT slack_user_id, slack_team_id, triage_user_id,
               jira_email, display_name
        FROM slack_user_mapping
        WHERE slack_team_id = $1
        ORDER BY slack_user_id
        """
        
        logger.debug(
            "Listing workspace user mappings",
            extra={"slack_team_id": slack_team_id}
        )
        
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(select_sql, slack_team_id)
            
            mappings = [
                SlackUser(
                    slack_user_id=row['slack_user_id'],
                    slack_team_id=row['slack_team_id'],
                    triage_user_id=row['triage_user_id'],
                    jira_email=row['jira_email'],
                    display_name=row['display_name']
                )
                for row in rows
            ]
            
            logger.debug(
                "Retrieved workspace user mappings",
                extra={
                    "slack_team_id": slack_team_id,
                    "count": len(mappings)
                }
            )
            
            return mappings
            
        except Exception as e:
            logger.error(
                "Failed to list workspace user mappings",
                extra={"slack_team_id": slack_team_id, "error": str(e)}
            )
            raise
    
    async def delete_workspace_mappings(self, slack_team_id: str) -> int:
        """
        Delete all user mappings for a workspace.
        
        Useful when a workspace uninstalls the bot.
        
        Args:
            slack_team_id: Slack workspace/team ID
            
        Returns:
            Number of mappings deleted
            
        Validates: Requirements 8.1, 12.5
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        delete_sql = """
        DELETE FROM slack_user_mapping
        WHERE slack_team_id = $1
        """
        
        logger.info(
            "Deleting all workspace user mappings",
            extra={"slack_team_id": slack_team_id}
        )
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(delete_sql, slack_team_id)
            
            # Parse result to get count
            count = int(result.split()[-1])
            
            logger.info(
                "Workspace user mappings deleted successfully",
                extra={
                    "slack_team_id": slack_team_id,
                    "count": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(
                "Failed to delete workspace user mappings",
                extra={"slack_team_id": slack_team_id, "error": str(e)}
            )
            raise
