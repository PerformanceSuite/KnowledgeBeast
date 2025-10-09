"""FastAPI dependency for project-level API key authentication.

This module provides middleware-style dependencies for validating project-scoped
API keys in FastAPI routes.

Usage:
    from knowledgebeast.api.project_auth_middleware import verify_project_api_key

    @router_v2.post("/{project_id}/query")
    async def project_query(
        project_id: str,
        query_request: QueryRequest,
        api_key: str = Depends(verify_project_api_key)
    ):
        # api_key is validated and has access to project_id
        ...
"""

import logging
import os
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from knowledgebeast.core.project_auth import ProjectAuthManager

logger = structlog.get_logger(__name__)

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

# Singleton auth manager
_auth_manager: Optional[ProjectAuthManager] = None


def get_auth_manager() -> ProjectAuthManager:
    """Get or create the singleton ProjectAuthManager instance.

    Returns:
        ProjectAuthManager instance
    """
    global _auth_manager

    if _auth_manager is None:
        db_path = os.getenv("KB_AUTH_DB_PATH", "./data/auth.db")
        _auth_manager = ProjectAuthManager(db_path=db_path)
        logger.info("project_auth_manager_initialized", db_path=db_path)

    return _auth_manager


async def verify_project_api_key(
    request: Request,
    api_key: str = Security(api_key_header)
) -> str:
    """FastAPI dependency for project-level API key authentication.

    Validates that the provided API key has access to the project specified
    in the request path.

    Supports two authentication modes:
    1. Global admin key (KB_API_KEY env var) - grants access to all projects
    2. Project-specific keys - grants access only to specific project

    Args:
        request: FastAPI request object (to extract project_id from path)
        api_key: API key from X-API-Key header

    Returns:
        Validated API key

    Raises:
        HTTPException 401: If API key is invalid
        HTTPException 403: If API key doesn't have access to project
        HTTPException 500: If project_id not found in path params

    Example:
        @router_v2.post("/{project_id}/query")
        async def project_query(
            project_id: str,
            query: QueryRequest,
            api_key: str = Depends(verify_project_api_key)
        ):
            # Key is validated and has access to project_id
            results = await query_project(project_id, query)
            return results
    """
    # Extract project_id from path params
    project_id = request.path_params.get("project_id")

    if not project_id:
        logger.error(
            "auth_error",
            reason="no_project_id_in_path",
            path=request.url.path
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project ID not found in request path"
        )

    # Check if it's the global admin key (for backwards compatibility)
    global_key = os.getenv("KB_API_KEY")

    if global_key and api_key == global_key:
        logger.debug(
            "auth_success_global",
            project_id=project_id,
            auth_type="global_admin_key"
        )
        return api_key

    # Validate project-specific key
    auth_manager = get_auth_manager()

    # Determine required scope from request method
    # POST/PUT/DELETE = write, GET = read
    required_scope = "write" if request.method in ["POST", "PUT", "DELETE", "PATCH"] else "read"

    if not auth_manager.validate_project_access(api_key, project_id, required_scope):
        # Record failed validation
        from knowledgebeast.utils.metrics import record_project_api_key_validation
        record_project_api_key_validation(project_id, "failure")

        logger.warning(
            "auth_failed",
            project_id=project_id,
            required_scope=required_scope,
            method=request.method
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have {required_scope} access to project {project_id}",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Record successful validation
    from knowledgebeast.utils.metrics import record_project_api_key_validation
    record_project_api_key_validation(project_id, "success")

    logger.debug(
        "auth_success_project",
        project_id=project_id,
        auth_type="project_scoped_key",
        required_scope=required_scope
    )

    return api_key


async def verify_project_admin_key(
    request: Request,
    api_key: str = Security(api_key_header)
) -> str:
    """Verify API key has admin access to project.

    Like verify_project_api_key but requires 'admin' scope.

    Args:
        request: FastAPI request
        api_key: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If not admin access

    Example:
        @router_v2.delete("/{project_id}")
        async def delete_project(
            project_id: str,
            api_key: str = Depends(verify_project_admin_key)
        ):
            # Only admin keys can delete projects
            ...
    """
    project_id = request.path_params.get("project_id")

    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project ID not found in request path"
        )

    # Global admin key always has access
    global_key = os.getenv("KB_API_KEY")
    if global_key and api_key == global_key:
        logger.debug(
            "auth_success_global_admin",
            project_id=project_id,
            auth_type="global_admin_key"
        )
        return api_key

    # Validate project-specific admin key
    auth_manager = get_auth_manager()

    if not auth_manager.validate_project_access(api_key, project_id, required_scope="admin"):
        logger.warning(
            "auth_failed_admin_required",
            project_id=project_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required for project {project_id}",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    logger.debug(
        "auth_success_project_admin",
        project_id=project_id,
        auth_type="project_admin_key"
    )

    return api_key
