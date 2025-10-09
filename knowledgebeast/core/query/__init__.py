"""Query expansion and semantic search module.

This module provides query expansion, reformulation, and semantic caching
capabilities to improve search recall and reduce latency.
"""

from knowledgebeast.core.query.expander import QueryExpander
from knowledgebeast.core.query.semantic_cache import SemanticCache

__all__ = ['QueryExpander', 'SemanticCache']

# Attempt to import reformulator (depends on optional spaCy)
try:
    from knowledgebeast.core.query.reformulator import QueryReformulator
    __all__.append('QueryReformulator')
except ImportError:
    pass
