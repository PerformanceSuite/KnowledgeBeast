"""Flask integration helpers for KnowledgeBeast (stub for future implementation)."""

from typing import Optional

from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.engine import KnowledgeBase


class KnowledgeBeastFlask:
    """Flask extension for KnowledgeBeast.
    
    Example:
        ```python
        from flask import Flask
        from knowledgebeast.integrations.flask import KnowledgeBeastFlask
        
        app = Flask(__name__)
        kb = KnowledgeBeastFlask(app)
        
        @app.route("/query")
        def query():
            results = kb.query(request.args.get("q"))
            return {"results": results}
        ```
    """
    
    def __init__(
        self,
        app=None,
        config: Optional[KnowledgeBeastConfig] = None
    ) -> None:
        """Initialize Flask extension.
        
        Args:
            app: Flask application instance
            config: Optional KnowledgeBeast configuration
        """
        self.config = config
        self._engine: Optional[KnowledgeBeast] = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app) -> None:
        """Initialize extension with Flask app.
        
        Args:
            app: Flask application instance
        """
        self._engine = KnowledgeBase(self.config)
        
        # Store reference in app extensions
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["knowledgebeast"] = self
    
    @property
    def engine(self) -> KnowledgeBeast:
        """Get the KnowledgeBeast engine instance."""
        if self._engine is None:
            self._engine = KnowledgeBase(self.config)
        return self._engine
    
    def query(self, *args, **kwargs):
        """Proxy to engine.query()."""
        return self.engine.query(*args, **kwargs)
    
    def ingest_document(self, *args, **kwargs):
        """Proxy to engine.ingest_document()."""
        return self.engine.ingest_document(*args, **kwargs)
    
    def get_stats(self, *args, **kwargs):
        """Proxy to engine.get_stats()."""
        return self.engine.get_stats(*args, **kwargs)
