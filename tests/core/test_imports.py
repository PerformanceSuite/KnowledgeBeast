"""Test that imports are correct and no duplicate classes exist."""

import pytest
import sys
from pathlib import Path


class TestImports:
    """Test correct imports after removing duplicate KnowledgeBase stub."""

    def test_knowledge_base_imports_from_engine(self):
        """Test that KnowledgeBase can be imported from engine.py."""
        from knowledgebeast.core.engine import KnowledgeBase

        assert KnowledgeBase is not None
        assert hasattr(KnowledgeBase, '__init__')
        assert hasattr(KnowledgeBase, 'query')
        assert hasattr(KnowledgeBase, 'from_config')

    def test_knowledge_base_stub_does_not_exist(self):
        """Test that the old knowledge_base.py stub file is deleted."""
        stub_path = Path(__file__).parent.parent.parent / 'knowledgebeast' / 'core' / 'knowledge_base.py'
        assert not stub_path.exists(), f"Stub file still exists at {stub_path}"

    def test_no_duplicate_knowledge_base_import(self):
        """Test that importing from knowledge_base module fails (file should not exist)."""
        with pytest.raises(ModuleNotFoundError):
            from knowledgebeast.core.knowledge_base import KnowledgeBase  # noqa: F401

    def test_from_config_classmethod_exists(self):
        """Test that from_config classmethod exists in the engine implementation."""
        from knowledgebeast.core.engine import KnowledgeBase

        assert hasattr(KnowledgeBase, 'from_config')
        assert callable(getattr(KnowledgeBase, 'from_config'))

        # Verify it's a classmethod
        import inspect
        assert isinstance(inspect.getattr_static(KnowledgeBase, 'from_config'), classmethod)

    def test_engine_implementation_is_complete(self):
        """Test that the engine implementation has all required methods."""
        from knowledgebeast.core.engine import KnowledgeBase

        required_methods = [
            '__init__',
            'from_config',
            'warm_up',
            'ingest_all',
            'query',
            'get_answer',
            'get_stats',
            'clear_cache',
            'rebuild_index',
            '__enter__',
            '__exit__',
        ]

        for method in required_methods:
            assert hasattr(KnowledgeBase, method), f"Missing method: {method}"
            assert callable(getattr(KnowledgeBase, method)), f"Method {method} is not callable"

    def test_server_uses_correct_import(self):
        """Test that server.py uses the correct import from engine."""
        server_file = Path(__file__).parent.parent.parent / 'knowledgebeast' / 'api' / 'server.py'

        if server_file.exists():
            content = server_file.read_text()

            # Should import from engine
            assert 'from knowledgebeast.core.engine import KnowledgeBase' in content, \
                "server.py should import from engine"

            # Should NOT import from knowledge_base
            assert 'from knowledgebeast.core.knowledge_base import' not in content, \
                "server.py should not import from knowledge_base stub"
