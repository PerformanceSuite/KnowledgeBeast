#!/usr/bin/env python3
"""
Security tests for KnowledgeBeast cache system.

Tests verify:
- Pickle deserialization is completely removed (RCE vulnerability fix)
- JSON cache loading works correctly
- Graceful failure for invalid/missing cache files
- No pickle imports anywhere in the codebase
"""

import json
import pytest
import tempfile
from pathlib import Path
import subprocess
import sys


class TestCacheSecurityPickleRemoval:
    """Test suite verifying pickle deserialization has been completely removed."""

    def test_no_pickle_imports_in_codebase(self):
        """Verify no pickle imports exist anywhere in knowledgebeast package."""
        # Get the project root (should be parent of tests directory)
        tests_dir = Path(__file__).parent.parent
        project_root = tests_dir.parent
        kb_package = project_root / "knowledgebeast"

        assert kb_package.exists(), f"Package directory not found: {kb_package}"

        # Search for any pickle imports in Python files
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "import pickle", str(kb_package)],
            capture_output=True,
            text=True
        )

        # grep returns 1 when no matches found, which is what we want
        assert result.returncode == 1, (
            f"Found pickle imports in codebase:\n{result.stdout}\n"
            "Pickle has been removed due to RCE vulnerability!"
        )

    def test_no_pickle_load_calls_in_codebase(self):
        """Verify no pickle.load() or pickle.loads() calls exist."""
        tests_dir = Path(__file__).parent.parent
        project_root = tests_dir.parent
        kb_package = project_root / "knowledgebeast"

        assert kb_package.exists(), f"Package directory not found: {kb_package}"

        # Search for pickle.load calls
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "pickle.load", str(kb_package)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 1, (
            f"Found pickle.load calls in codebase:\n{result.stdout}\n"
            "Pickle deserialization has been removed due to RCE vulnerability!"
        )

    def test_json_cache_loads_successfully(self, tmp_path):
        """Test that valid JSON cache files load correctly."""
        from knowledgebeast.core.engine import KnowledgeBase
        from knowledgebeast.core.config import KnowledgeBeastConfig

        # Create test knowledge directory with a markdown file
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        test_file = kb_dir / "test.md"
        test_file.write_text("# Test Document\n\nThis is a test document for security testing.")

        # Create a valid JSON cache file
        cache_file = tmp_path / "cache.json"
        cache_data = {
            "documents": {
                "test_doc": {
                    "path": str(test_file),
                    "content": "# Test Document\n\nThis is a test.",
                    "name": "test.md",
                    "kb_dir": str(kb_dir)
                }
            },
            "index": {
                "test": ["test_doc"],
                "document": ["test_doc"]
            }
        }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)

        # Initialize KnowledgeBase with this cache
        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Verify cache was loaded
        assert len(kb.documents) > 0, "Cache should have loaded documents"
        assert len(kb.index) > 0, "Cache should have loaded index"

    def test_invalid_json_cache_triggers_rebuild(self, tmp_path):
        """Test that invalid JSON cache files trigger graceful rebuild."""
        from knowledgebeast.core.engine import KnowledgeBase
        from knowledgebeast.core.config import KnowledgeBeastConfig

        # Create test knowledge directory
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        test_file = kb_dir / "test.md"
        test_file.write_text("# Test Document\n\nThis is a test document.")

        # Create an invalid JSON cache file
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("{ invalid json syntax here }")

        # Initialize KnowledgeBase - should rebuild gracefully
        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)

        # This should not raise an exception - should rebuild
        kb.ingest_all()

        # Verify documents were loaded from source, not cache
        assert len(kb.documents) > 0, "Should have rebuilt index from source files"
        assert len(kb.index) > 0, "Should have rebuilt index from source files"

    def test_missing_cache_file_builds_index(self, tmp_path):
        """Test that missing cache file triggers index build."""
        from knowledgebeast.core.engine import KnowledgeBase
        from knowledgebeast.core.config import KnowledgeBeastConfig

        # Create test knowledge directory
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        test_file = kb_dir / "test.md"
        test_file.write_text("# Test Document\n\nThis is a test document.")

        # Use non-existent cache file path
        cache_file = tmp_path / "nonexistent_cache.json"

        # Initialize KnowledgeBase
        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Verify index was built from source
        assert len(kb.documents) > 0, "Should have built index from source files"
        assert len(kb.index) > 0, "Should have built index from source files"

        # Verify cache file was created
        assert cache_file.exists(), "Cache file should have been created"

        # Verify cache is valid JSON
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)

        assert 'documents' in cached_data, "Cache should contain documents"
        assert 'index' in cached_data, "Cache should contain index"

    def test_legacy_pickle_cache_triggers_rebuild(self, tmp_path):
        """Test that legacy pickle cache files trigger rebuild instead of RCE vulnerability."""
        from knowledgebeast.core.engine import KnowledgeBase
        from knowledgebeast.core.config import KnowledgeBeastConfig

        # Create test knowledge directory
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        test_file = kb_dir / "test.md"
        test_file.write_text("# Test Document\n\nThis is a test document.")

        # Create a fake "pickle" cache file (just binary garbage)
        # We don't actually use pickle.dump to avoid the vulnerability entirely
        cache_file = tmp_path / "cache.json"
        cache_file.write_bytes(b'\x80\x04\x95')  # Pickle protocol header

        # Initialize KnowledgeBase
        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)

        # This should gracefully rebuild, not try to load pickle
        kb.ingest_all()

        # Verify documents were loaded from source, not cache
        assert len(kb.documents) > 0, "Should have rebuilt index from source files"
        assert len(kb.index) > 0, "Should have rebuilt index from source files"

        # Verify cache was overwritten with JSON
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)

        assert 'documents' in cached_data, "Cache should now be JSON format"

    def test_cache_format_is_json_only(self, tmp_path):
        """Verify that saved caches are always JSON, never pickle."""
        from knowledgebeast.core.engine import KnowledgeBase
        from knowledgebeast.core.config import KnowledgeBeastConfig

        # Create test knowledge directory
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        test_file = kb_dir / "test.md"
        test_file.write_text("# Test Document\n\nThis is a test document.")

        cache_file = tmp_path / "cache.json"

        # Initialize and build cache
        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)
        kb.ingest_all()

        # Verify cache file exists and is valid JSON
        assert cache_file.exists(), "Cache file should exist"

        # Read and parse as JSON
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)

        assert isinstance(cached_data, dict), "Cache should be a JSON object"
        assert 'documents' in cached_data, "Cache should contain documents"
        assert 'index' in cached_data, "Cache should contain index"

        # Verify it's NOT pickle format (pickle files start with specific bytes)
        with open(cache_file, 'rb') as f:
            first_bytes = f.read(10)

        # Pickle protocol markers (we should NOT see these)
        pickle_markers = [b'\x80\x03', b'\x80\x04', b'\x80\x05']
        for marker in pickle_markers:
            assert not first_bytes.startswith(marker), (
                f"Cache file appears to be pickle format! First bytes: {first_bytes}"
            )


class TestCacheSecurityBehavior:
    """Test security-related behavior of cache system."""

    def test_cache_staleness_check_handles_corrupt_cache(self, tmp_path):
        """Verify cache staleness check handles corrupt cache gracefully."""
        from knowledgebeast.core.engine import KnowledgeBase
        from knowledgebeast.core.config import KnowledgeBeastConfig

        # Create knowledge directory
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        test_file = kb_dir / "test.md"
        test_file.write_text("# Test\n\nContent")

        # Create corrupt cache
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("corrupt{{{")

        config = KnowledgeBeastConfig(
            knowledge_dirs=[kb_dir],
            cache_file=str(cache_file),
            auto_warm=False,
            verbose=False
        )

        kb = KnowledgeBase(config)

        # Should handle gracefully and rebuild
        kb.ingest_all()

        assert len(kb.documents) > 0, "Should rebuild successfully"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
