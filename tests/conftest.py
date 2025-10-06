"""Pytest fixtures for KnowledgeBeast tests."""

import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.api.app import app


@pytest.fixture
def temp_kb_dir() -> Generator[Path, None, None]:
    """Create temporary knowledge base directory with sample documents.

    Yields:
        Path to temporary KB directory with test .md files
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_path = Path(tmpdir) / "knowledge-base"
        kb_path.mkdir(parents=True)

        # Create sample markdown documents
        (kb_path / "audio_processing.md").write_text("""
# Audio Processing Guide

This document covers audio processing techniques.

## Librosa
Librosa is a Python library for audio analysis.

## Key Features
- Beat detection
- Tempo estimation
- Spectral analysis
""")

        (kb_path / "juce_framework.md").write_text("""
# JUCE Framework

JUCE is a C++ framework for audio applications.

## Real-time Processing
Process audio in real-time with low latency.

## Audio Plugins
Create VST, AU, and AAX plugins.
""")

        (kb_path / "music_theory.md").write_text("""
# Music Theory Basics

Understanding music theory fundamentals.

## Chord Progressions
Common chord progressions in popular music.

## Scales
Major and minor scales explained.
""")

        yield kb_path


@pytest.fixture
def kb_config(temp_kb_dir: Path) -> KnowledgeBeastConfig:
    """Create test KnowledgeBeastConfig.

    Args:
        temp_kb_dir: Temporary KB directory fixture

    Returns:
        Configured KnowledgeBeastConfig for testing
    """
    cache_path = temp_kb_dir.parent / ".test_cache.pkl"
    return KnowledgeBeastConfig(
        knowledge_dirs=[temp_kb_dir],
        cache_file=cache_path,
        max_cache_size=10,
        heartbeat_interval=10,
        auto_warm=False,  # Disable auto-warm for faster tests
        verbose=False,  # Reduce noise in test output
        warming_queries=["audio processing", "juce framework"]
    )


@pytest.fixture
def kb_instance(kb_config: KnowledgeBeastConfig) -> Generator[KnowledgeBase, None, None]:
    """Create KnowledgeBase instance for testing.

    Args:
        kb_config: Test configuration fixture

    Yields:
        Initialized KnowledgeBase instance
    """
    kb = KnowledgeBase(kb_config)
    yield kb
    # Cleanup
    if kb_config.cache_file.exists():
        kb_config.cache_file.unlink()


@pytest.fixture
def kb_instance_warmed(kb_config: KnowledgeBeastConfig) -> Generator[KnowledgeBase, None, None]:
    """Create pre-warmed KnowledgeBase instance.

    Args:
        kb_config: Test configuration fixture

    Yields:
        Warmed KnowledgeBase instance
    """
    config = KnowledgeBeastConfig(
        knowledge_dirs=kb_config.knowledge_dirs,
        cache_file=kb_config.cache_file,
        max_cache_size=kb_config.max_cache_size,
        heartbeat_interval=kb_config.heartbeat_interval,
        auto_warm=True,  # Enable warming
        verbose=False,
        warming_queries=kb_config.warming_queries
    )
    kb = KnowledgeBase(config)
    yield kb
    # Cleanup
    if config.cache_file.exists():
        config.cache_file.unlink()


@pytest.fixture
def test_documents() -> dict[str, str]:
    """Sample test documents for ingestion.

    Returns:
        Dictionary of document names to content
    """
    return {
        "test_doc1.md": """# Test Document 1
This is a test document about Python programming.
It covers various topics like functions and classes.
""",
        "test_doc2.txt": """Test Document 2
This is a plain text document.
It contains information about testing.
""",
        "test_doc3.md": """# Advanced Topics
Deep dive into advanced programming concepts.
Including async/await and concurrency.
"""
    }


@pytest.fixture
def api_client() -> TestClient:
    """FastAPI test client.

    Returns:
        TestClient for API endpoint testing
    """
    return TestClient(app)


@pytest.fixture
def sample_cache_path(temp_kb_dir: Path) -> Path:
    """Path for cache file testing.

    Args:
        temp_kb_dir: Temporary KB directory

    Returns:
        Path for cache file
    """
    return temp_kb_dir.parent / ".test_cache.pkl"


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables before each test.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    # Set test API key for authentication
    monkeypatch.setenv('KB_API_KEY', 'test-api-key-12345')

    # Clear any other KB_ environment variables
    env_vars = [
        'KB_KNOWLEDGE_DIRS',
        'KB_CACHE_FILE',
        'KB_MAX_CACHE_SIZE',
        'KB_HEARTBEAT_INTERVAL',
        'KB_AUTO_WARM'
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_progress_callback():
    """Mock progress callback for testing.

    Returns:
        Callable that records progress updates
    """
    calls = []

    def callback(message: str, current: int, total: int) -> None:
        calls.append((message, current, total))

    callback.calls = calls
    return callback
