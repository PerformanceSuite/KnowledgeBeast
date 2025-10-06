"""FastAPI integration helpers for KnowledgeBeast."""

from typing import Optional

from fastapi import Depends

from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.engine import KnowledgeBase

# Global engine instance
_engine: Optional[KnowledgeBeast] = None


def get_engine(config: Optional[KnowledgeBeastConfig] = None) -> KnowledgeBeast:
    """Get or create the global KnowledgeBeast engine instance.
    
    This function can be used as a FastAPI dependency.
    
    Args:
        config: Optional configuration. Only used on first call.
        
    Returns:
        Global KnowledgeBeast engine instance
        
    Example:
        ```python
        from fastapi import FastAPI, Depends
        from knowledgebeast.integrations.fastapi import get_engine
        from knowledgebeast.core.engine import KnowledgeBase
        
        app = FastAPI()
        
        @app.get("/query")
        def query(q: str, kb: KnowledgeBeast = Depends(get_engine)):
            return kb.query(q)
        ```
    """
    global _engine
    if _engine is None:
        _engine = KnowledgeBase(config)
    return _engine


def reset_engine() -> None:
    """Reset the global engine instance (useful for testing)."""
    global _engine
    if _engine is not None:
        _engine.shutdown()
        _engine = None
