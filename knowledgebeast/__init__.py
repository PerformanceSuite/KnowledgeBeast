"""KnowledgeBeast - A production-ready knowledge management system with RAG capabilities.

Ported and enhanced from Performia knowledge_rag_v2.py with battle-tested code.

Features:
- Multi-directory knowledge base support
- Automatic cache warming for reduced latency
- LRU query caching with configurable size
- Background heartbeat for health monitoring
- Stale cache detection and auto-rebuild
- Progress callbacks for long operations
- Environment variable configuration
- Production-ready error handling
"""

__version__ = "0.1.0"
__author__ = "Daniel Connolly"
__license__ = "MIT"
__description__ = "High-performance RAG knowledge base with intelligent caching and warming"

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.heartbeat import KnowledgeBaseHeartbeat
from knowledgebeast.core.cache import LRUCache

__all__ = [
    "KnowledgeBase",
    "KnowledgeBeastConfig",
    "KnowledgeBaseHeartbeat",
    "LRUCache",
    "__version__",
    "__description__"
]
