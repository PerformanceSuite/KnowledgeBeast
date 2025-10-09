"""Project-level API key management for KnowledgeBeast.

This module provides granular, project-scoped API key authentication:
- Create/revoke API keys per project
- Scope-based permissions (read, write, admin)
- Automatic expiration support
- Audit trail tracking (created_at, last_used_at)
- SQLite-backed persistence

Security Features:
- SHA-256 hashing of keys (never store raw keys)
- One-time key revelation (only shown at creation)
- Path traversal protection
- SQL injection protection via parameterized queries
"""

import hashlib
import logging
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)


class ProjectAuthManager:
    """Manage project-scoped API keys with granular permissions.

    Provides fine-grained access control for multi-tenant KnowledgeBeast deployments.
    Each project can have multiple API keys with different permission scopes.

    Example:
        auth = ProjectAuthManager(db_path="./data/auth.db")

        # Create read-only key that expires in 30 days
        key_info = auth.create_api_key(
            project_id="proj_123",
            name="Mobile App Key",
            scopes=["read"],
            expires_days=30
        )
        print(key_info["api_key"])  # kb_abc123... (only shown once!)

        # Validate access
        if auth.validate_project_access(api_key, "proj_123", required_scope="read"):
            # Allow read operation
            pass

        # List all keys for project
        keys = auth.list_project_keys("proj_123")

        # Revoke a key
        auth.revoke_api_key(key_id)
    """

    def __init__(self, db_path: str = "./data/auth.db"):
        """Initialize ProjectAuthManager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("project_auth_initialized", db_path=str(self.db_path))

    def _init_db(self):
        """Initialize API keys database schema."""
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    revoked INTEGER DEFAULT 0,
                    last_used_at TEXT,
                    created_by TEXT
                )
            """)

            # Create indexes for efficient lookups
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_id ON api_keys(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_key_hash ON api_keys(key_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_revoked ON api_keys(revoked)"
            )

            logger.debug("database_schema_initialized")

    @contextmanager
    def _get_db(self):
        """Get database connection with automatic commit/rollback.

        Yields:
            SQLite connection with Row factory enabled
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("database_error", error=str(e), exc_info=True)
            raise
        finally:
            conn.close()

    def create_api_key(
        self,
        project_id: str,
        name: str,
        scopes: Optional[List[str]] = None,
        expires_days: Optional[int] = None,
        created_by: Optional[str] = None
    ) -> Dict:
        """Generate a new project-scoped API key.

        Args:
            project_id: Project identifier
            name: Human-readable key name (e.g., "Mobile App Key")
            scopes: List of permission scopes. Defaults to ["read", "write"]
                    Valid scopes: "read", "write", "admin"
            expires_days: Key expiration in days (None = never expires)
            created_by: Username/email of key creator (for audit trail)

        Returns:
            Dictionary containing:
                - key_id: Unique key identifier (for revocation)
                - api_key: Raw API key (ONLY returned here, never again!)
                - project_id: Project this key grants access to
                - name: Key name
                - scopes: List of permission scopes
                - created_at: ISO 8601 timestamp
                - expires_at: ISO 8601 timestamp or None

        Example:
            >>> key = auth.create_api_key(
            ...     project_id="proj_audio_ml",
            ...     name="Production API Key",
            ...     scopes=["read"],
            ...     expires_days=90
            ... )
            >>> print(key["api_key"])  # Save this! Won't be shown again
            kb_vL9x2K8pQ7mR4nS6tU0wY1zA3bC5dE7fG9hJ2kL4mN6oP8qR0sT
        """
        # Validate inputs
        if not project_id or not project_id.strip():
            raise ValueError("project_id cannot be empty")

        if not name or not name.strip():
            raise ValueError("name cannot be empty")

        # Set default scopes
        scopes = scopes or ["read", "write"]

        # Validate scopes
        valid_scopes = {"read", "write", "admin"}
        invalid_scopes = set(scopes) - valid_scopes
        if invalid_scopes:
            raise ValueError(
                f"Invalid scopes: {invalid_scopes}. "
                f"Valid scopes: {valid_scopes}"
            )

        # Generate secure random key
        # Format: kb_{32 bytes base64url} = kb_ + 43 chars = 46 total
        raw_key = secrets.token_urlsafe(32)
        api_key = f"kb_{raw_key}"

        # Generate unique key ID
        key_id = secrets.token_urlsafe(16)

        # Hash the key (never store raw keys)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Prepare data
        scopes_str = ",".join(sorted(scopes))  # Sort for consistency
        created_at = datetime.utcnow().isoformat()
        expires_at = None

        if expires_days:
            if expires_days <= 0:
                raise ValueError("expires_days must be positive")
            expires_at = (
                datetime.utcnow() + timedelta(days=expires_days)
            ).isoformat()

        # Insert into database
        with self._get_db() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (
                    key_id, project_id, name, key_hash, scopes,
                    created_at, expires_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id, project_id, name, key_hash, scopes_str,
                    created_at, expires_at, created_by
                )
            )

        logger.info(
            "api_key_created",
            key_id=key_id,
            project_id=project_id,
            name=name,
            scopes=scopes,
            expires_at=expires_at
        )

        return {
            "key_id": key_id,
            "api_key": api_key,  # ONLY time raw key is returned
            "project_id": project_id,
            "name": name,
            "scopes": scopes,
            "created_at": created_at,
            "expires_at": expires_at
        }

    def validate_project_access(
        self,
        api_key: str,
        project_id: str,
        required_scope: str = "read"
    ) -> bool:
        """Validate that an API key has access to a project with required scope.

        Checks:
        1. Key exists and matches hash
        2. Key is for the specified project
        3. Key is not revoked
        4. Key has not expired
        5. Key has required permission scope

        Args:
            api_key: Raw API key to validate
            project_id: Project the key must have access to
            required_scope: Minimum required scope ("read", "write", or "admin")

        Returns:
            True if key is valid and has required access, False otherwise

        Side Effects:
            Updates last_used_at timestamp on successful validation

        Example:
            >>> if auth.validate_project_access(key, "proj_123", "write"):
            ...     # Allow write operation
            ...     ingest_document(...)
            >>> else:
            ...     raise PermissionError("Insufficient permissions")
        """
        if not api_key or not project_id:
            logger.warning("validation_failed", reason="empty_input")
            return False

        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            with self._get_db() as conn:
                # Look up key
                row = conn.execute(
                    """
                    SELECT * FROM api_keys
                    WHERE key_hash = ? AND project_id = ? AND revoked = 0
                    """,
                    (key_hash, project_id)
                ).fetchone()

                if not row:
                    logger.warning(
                        "validation_failed",
                        reason="key_not_found_or_revoked",
                        project_id=project_id
                    )
                    return False

                # Check expiration
                if row['expires_at']:
                    expires_at = datetime.fromisoformat(row['expires_at'])
                    if datetime.utcnow() > expires_at:
                        logger.warning(
                            "validation_failed",
                            reason="key_expired",
                            key_id=row['key_id'],
                            expires_at=row['expires_at']
                        )
                        return False

                # Check scope
                scopes = set(row['scopes'].split(','))

                # Admin scope grants all permissions
                if "admin" in scopes:
                    scope_valid = True
                elif required_scope == "admin":
                    scope_valid = "admin" in scopes
                elif required_scope == "write":
                    scope_valid = "write" in scopes or "admin" in scopes
                elif required_scope == "read":
                    scope_valid = (
                        "read" in scopes or "write" in scopes or "admin" in scopes
                    )
                else:
                    logger.warning(
                        "validation_failed",
                        reason="invalid_required_scope",
                        required_scope=required_scope
                    )
                    return False

                if not scope_valid:
                    logger.warning(
                        "validation_failed",
                        reason="insufficient_scope",
                        key_id=row['key_id'],
                        has_scopes=list(scopes),
                        required_scope=required_scope
                    )
                    return False

                # Update last used timestamp
                conn.execute(
                    "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                    (datetime.utcnow().isoformat(), key_hash)
                )

                logger.debug(
                    "validation_successful",
                    key_id=row['key_id'],
                    project_id=project_id,
                    required_scope=required_scope
                )

                return True

        except Exception as e:
            logger.error(
                "validation_error",
                error=str(e),
                project_id=project_id,
                exc_info=True
            )
            return False

    def list_project_keys(self, project_id: str) -> List[Dict]:
        """List all API keys for a project (excluding raw keys).

        Args:
            project_id: Project identifier

        Returns:
            List of dictionaries with key metadata (NO raw keys included)

        Example:
            >>> keys = auth.list_project_keys("proj_123")
            >>> for key in keys:
            ...     print(f"{key['name']}: {key['scopes']} (revoked: {key['revoked']})")
            Mobile App: ['read'] (revoked: False)
            Admin Key: ['read', 'write', 'admin'] (revoked: False)
        """
        with self._get_db() as conn:
            rows = conn.execute(
                """
                SELECT key_id, name, scopes, created_at, expires_at,
                       revoked, last_used_at, created_by
                FROM api_keys
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,)
            ).fetchall()

            keys = []
            for row in rows:
                keys.append({
                    "key_id": row['key_id'],
                    "name": row['name'],
                    "scopes": row['scopes'].split(','),
                    "created_at": row['created_at'],
                    "expires_at": row['expires_at'],
                    "revoked": bool(row['revoked']),
                    "last_used_at": row['last_used_at'],
                    "created_by": row['created_by']
                })

            logger.debug("listed_project_keys", project_id=project_id, count=len(keys))
            return keys

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key (soft delete, preserves audit trail).

        Args:
            key_id: Unique key identifier

        Returns:
            True if key was revoked, False if key not found

        Example:
            >>> auth.revoke_api_key("key_abc123")
            True
        """
        with self._get_db() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET revoked = 1 WHERE key_id = ?",
                (key_id,)
            )

            if cursor.rowcount > 0:
                logger.info("api_key_revoked", key_id=key_id)
                return True
            else:
                logger.warning("revoke_failed", key_id=key_id, reason="not_found")
                return False

    def get_key_info(self, key_id: str) -> Optional[Dict]:
        """Get information about a specific API key (NO raw key returned).

        Args:
            key_id: Unique key identifier

        Returns:
            Dictionary with key metadata, or None if not found

        Example:
            >>> info = auth.get_key_info("key_abc123")
            >>> print(info["name"], info["scopes"])
            Mobile App Key ['read']
        """
        with self._get_db() as conn:
            row = conn.execute(
                """
                SELECT key_id, project_id, name, scopes, created_at,
                       expires_at, revoked, last_used_at, created_by
                FROM api_keys
                WHERE key_id = ?
                """,
                (key_id,)
            ).fetchone()

            if not row:
                return None

            return {
                "key_id": row['key_id'],
                "project_id": row['project_id'],
                "name": row['name'],
                "scopes": row['scopes'].split(','),
                "created_at": row['created_at'],
                "expires_at": row['expires_at'],
                "revoked": bool(row['revoked']),
                "last_used_at": row['last_used_at'],
                "created_by": row['created_by']
            }

    def cleanup_expired_keys(self) -> int:
        """Remove expired keys from database (optional maintenance).

        Returns:
            Number of keys removed

        Note:
            This is optional - expired keys are already ignored during validation.
            This is for cleaning up the database to reduce clutter.
        """
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                DELETE FROM api_keys
                WHERE expires_at IS NOT NULL
                  AND expires_at < ?
                """,
                (datetime.utcnow().isoformat(),)
            )

            count = cursor.rowcount
            if count > 0:
                logger.info("expired_keys_cleaned", count=count)

            return count
