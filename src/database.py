"""Database setup and management for the cleanup system."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = """
-- User table - keyed by email address
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,  -- Company email address
    name TEXT,  -- Optional display name
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PAT storage with rotation support and multi-platform
CREATE TABLE IF NOT EXISTS user_pats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT REFERENCES users(email),
    encrypted_pat TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'cloudbees',  -- 'cloudbees' or 'github'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Resource sessions tied to user email
CREATE TABLE IF NOT EXISTS resource_sessions (
    id TEXT PRIMARY KEY,
    email TEXT REFERENCES users(email),
    scenario_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- NULL = no expiration
    parameters JSON
);

-- Resources linked to sessions
CREATE TABLE IF NOT EXISTS resources (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES resource_sessions(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,  -- 'github_repo', 'cloudbees_component', etc.
    resource_id TEXT NOT NULL,    -- GitHub repo full_name, CloudBees UUID, etc.
    resource_name TEXT NOT NULL,
    platform TEXT NOT NULL,      -- 'github' or 'cloudbees'
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'delete_pending', 'deleted', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON                 -- platform-specific data for cleanup
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_pats_platform ON user_pats(email, platform, is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resources_session ON resources(session_id);
CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status); -- For finding resources to clean up
CREATE INDEX IF NOT EXISTS idx_sessions_user ON resource_sessions(email);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON resource_sessions(expires_at);
"""


class Database:
    """Database manager for the cleanup system."""

    def __init__(self, db_path: str = "mimic.db"):
        self.db_path = db_path
        self._connection = None

    async def initialize(self) -> None:
        """Initialize the database with schema and WAL mode."""
        try:
            # Create database file if it doesn't exist
            os.makedirs(
                os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".",
                exist_ok=True,
            )

            async with aiosqlite.connect(self.db_path) as db:
                # Enable WAL mode for better concurrency
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA foreign_keys=ON")

                # Create tables and indexes
                await db.executescript(CREATE_TABLES_SQL)
                await db.commit()

                logger.info(f"Database initialized at {self.db_path} with WAL mode")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection]:
        """Get a database connection with proper cleanup."""
        conn = await aiosqlite.connect(self.db_path)
        try:
            # Enable row factory for easier access
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            await conn.close()

    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a query without returning results."""
        async with self.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Fetch a single row."""
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            result = await cursor.fetchall()
            return list(result)

    async def create_user(self, email: str, name: str | None = None) -> None:
        """Create or update a user record."""
        await self.execute(
            """
            INSERT INTO users (email, name, first_seen, last_active)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                name = COALESCE(?, name),
                last_active = CURRENT_TIMESTAMP
            """,
            (email, name, name),
        )

    async def store_pat(
        self, email: str, encrypted_pat: str, platform: str = "cloudbees"
    ) -> int:
        """Store an encrypted PAT for a user."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO user_pats (email, encrypted_pat, platform, created_at, last_used, is_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, true)
                """,
                (email, encrypted_pat, platform),
            )
            await conn.commit()
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    async def get_user_pats(
        self, email: str, platform: str = "cloudbees"
    ) -> list[aiosqlite.Row]:
        """Get all active PATs for a user and platform, ordered by creation date (newest first)."""
        return await self.fetchall(
            """
            SELECT id, encrypted_pat, platform, created_at, last_used, is_active
            FROM user_pats
            WHERE email = ? AND platform = ? AND is_active = true
            ORDER BY id DESC
            """,
            (email, platform),
        )

    async def mark_pat_inactive(self, pat_id: int) -> None:
        """Mark a PAT as inactive."""
        await self.execute(
            "UPDATE user_pats SET is_active = false WHERE id = ?", (pat_id,)
        )

    async def create_session(
        self,
        session_id: str,
        email: str,
        scenario_id: str,
        expires_at: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Create a new resource session."""
        import json

        await self.execute(
            """
            INSERT INTO resource_sessions (id, email, scenario_id, created_at, expires_at, parameters)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            """,
            (
                session_id,
                email,
                scenario_id,
                expires_at,
                json.dumps(parameters) if parameters else None,
            ),
        )

    async def register_resource(
        self,
        resource_id: str,
        session_id: str,
        resource_type: str,
        resource_name: str,
        platform: str,
        resource_ref: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a created resource to a session."""
        import json

        await self.execute(
            """
            INSERT INTO resources (id, session_id, resource_type, resource_id, resource_name,
                                 platform, status, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, ?)
            """,
            (
                resource_id,
                session_id,
                resource_type,
                resource_ref,
                resource_name,
                platform,
                json.dumps(metadata) if metadata else None,
            ),
        )

    async def get_user_sessions(self, email: str) -> list[aiosqlite.Row]:
        """Get all sessions for a user with resource counts."""
        return await self.fetchall(
            """
            SELECT s.*, COUNT(r.id) as resource_count
            FROM resource_sessions s
            LEFT JOIN resources r ON s.id = r.session_id AND r.status = 'active'
            WHERE s.email = ?
            GROUP BY s.id, s.email, s.scenario_id, s.created_at, s.expires_at, s.parameters
            ORDER BY s.created_at DESC
            """,
            (email,),
        )

    async def get_session_resources(self, session_id: str) -> list[aiosqlite.Row]:
        """Get all resources for a session."""
        return await self.fetchall(
            """
            SELECT * FROM resources
            WHERE session_id = ? AND status = 'active'
            ORDER BY created_at DESC
            """,
            (session_id,),
        )

    async def mark_resources_for_deletion(self) -> int:
        """Mark resources in expired sessions for deletion. Returns count of marked resources."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE resources
                SET status = 'delete_pending'
                WHERE session_id IN (
                    SELECT id FROM resource_sessions
                    WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                ) AND status = 'active'
                """
            )
            await conn.commit()
            return cursor.rowcount

    async def get_resources_pending_deletion(self) -> list[aiosqlite.Row]:
        """Get all resources marked for deletion with their user email."""
        return await self.fetchall(
            """
            SELECT r.*, s.email
            FROM resources r
            JOIN resource_sessions s ON r.session_id = s.id
            WHERE r.status = 'delete_pending'
            ORDER BY r.created_at ASC
            """
        )

    async def mark_resource_deleted(self, resource_id: str) -> None:
        """Mark a resource as successfully deleted."""
        await self.execute(
            "UPDATE resources SET status = 'deleted' WHERE id = ?", (resource_id,)
        )

    async def mark_resource_failed(self, resource_id: str) -> None:
        """Mark a resource cleanup as failed."""
        await self.execute(
            "UPDATE resources SET status = 'failed' WHERE id = ?", (resource_id,)
        )


# Global database instance
_db = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


async def initialize_database() -> None:
    """Initialize the global database instance."""
    db = get_database()
    await db.initialize()
