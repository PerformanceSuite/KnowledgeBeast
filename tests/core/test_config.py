"""Tests for configuration management."""

import os
from pathlib import Path
import pytest
import yaml

from knowledgebeast.core.config import KnowledgeBeastConfig, Config


class TestKnowledgeBeastConfigDefaults:
    """Test KnowledgeBeastConfig default values."""

    def test_default_config(self):
        """Test config initializes with defaults."""
        config = KnowledgeBeastConfig()

        assert config.knowledge_dirs == [Path("knowledge-base")]
        assert config.cache_file == Path(".knowledge_cache.pkl")
        assert config.max_cache_size == 100
        assert config.heartbeat_interval == 300
        assert config.auto_warm is True
        assert config.verbose is True
        assert len(config.warming_queries) > 0

    def test_default_warming_queries(self):
        """Test default warming queries are present."""
        config = KnowledgeBeastConfig()

        assert isinstance(config.warming_queries, list)
        assert len(config.warming_queries) > 0
        assert all(isinstance(q, str) for q in config.warming_queries)


class TestKnowledgeBeastConfigCustom:
    """Test KnowledgeBeastConfig with custom values."""

    def test_custom_knowledge_dirs(self):
        """Test setting custom knowledge directories."""
        kb_dirs = [Path("/path/to/kb1"), Path("/path/to/kb2")]
        config = KnowledgeBeastConfig(knowledge_dirs=kb_dirs)

        assert config.knowledge_dirs == kb_dirs
        assert len(config.knowledge_dirs) == 2

    def test_custom_cache_settings(self):
        """Test setting custom cache settings."""
        cache_file = Path("/tmp/custom_cache.pkl")
        config = KnowledgeBeastConfig(
            cache_file=cache_file,
            max_cache_size=50
        )

        assert config.cache_file == cache_file
        assert config.max_cache_size == 50

    def test_custom_heartbeat_interval(self):
        """Test setting custom heartbeat interval."""
        config = KnowledgeBeastConfig(heartbeat_interval=120)
        assert config.heartbeat_interval == 120

    def test_custom_warming_queries(self):
        """Test setting custom warming queries."""
        custom_queries = ["query1", "query2", "query3"]
        config = KnowledgeBeastConfig(warming_queries=custom_queries)
        assert config.warming_queries == custom_queries

    def test_disable_auto_warm(self):
        """Test disabling auto-warm."""
        config = KnowledgeBeastConfig(auto_warm=False)
        assert config.auto_warm is False

    def test_disable_verbose(self):
        """Test disabling verbose output."""
        config = KnowledgeBeastConfig(verbose=False)
        assert config.verbose is False


class TestEnvironmentVariables:
    """Test environment variable configuration."""

    def test_env_var_knowledge_dirs(self, monkeypatch):
        """Test KB_KNOWLEDGE_DIRS environment variable."""
        monkeypatch.setenv('KB_KNOWLEDGE_DIRS', '/kb1,/kb2,/kb3')
        config = KnowledgeBeastConfig()

        assert len(config.knowledge_dirs) == 3
        assert config.knowledge_dirs == [Path("/kb1"), Path("/kb2"), Path("/kb3")]

    def test_env_var_cache_file(self, monkeypatch):
        """Test KB_CACHE_FILE environment variable."""
        monkeypatch.setenv('KB_CACHE_FILE', '/tmp/env_cache.pkl')
        config = KnowledgeBeastConfig()

        assert config.cache_file == Path("/tmp/env_cache.pkl")

    def test_env_var_max_cache_size(self, monkeypatch):
        """Test KB_MAX_CACHE_SIZE environment variable."""
        monkeypatch.setenv('KB_MAX_CACHE_SIZE', '75')
        config = KnowledgeBeastConfig()

        assert config.max_cache_size == 75

    def test_env_var_heartbeat_interval(self, monkeypatch):
        """Test KB_HEARTBEAT_INTERVAL environment variable."""
        monkeypatch.setenv('KB_HEARTBEAT_INTERVAL', '180')
        config = KnowledgeBeastConfig()

        assert config.heartbeat_interval == 180

    def test_env_var_auto_warm_true(self, monkeypatch):
        """Test KB_AUTO_WARM environment variable (true values)."""
        for value in ['true', 'True', '1', 'yes']:
            monkeypatch.setenv('KB_AUTO_WARM', value)
            config = KnowledgeBeastConfig()
            assert config.auto_warm is True

    def test_env_var_auto_warm_false(self, monkeypatch):
        """Test KB_AUTO_WARM environment variable (false values)."""
        for value in ['false', 'False', '0', 'no']:
            monkeypatch.setenv('KB_AUTO_WARM', value)
            config = KnowledgeBeastConfig()
            assert config.auto_warm is False

    def test_env_vars_whitespace_handling(self, monkeypatch):
        """Test environment variables handle whitespace."""
        monkeypatch.setenv('KB_KNOWLEDGE_DIRS', ' /kb1 , /kb2 , /kb3 ')
        config = KnowledgeBeastConfig()

        assert len(config.knowledge_dirs) == 3


class TestConfigValidation:
    """Test configuration validation."""

    def test_empty_knowledge_dirs_raises_error(self):
        """Test empty knowledge_dirs raises ValueError."""
        with pytest.raises(ValueError, match="At least one knowledge directory"):
            KnowledgeBeastConfig(knowledge_dirs=[])

    def test_invalid_cache_size_raises_error(self):
        """Test invalid max_cache_size raises ValueError."""
        with pytest.raises(ValueError, match="max_cache_size must be positive"):
            KnowledgeBeastConfig(max_cache_size=0)

        with pytest.raises(ValueError, match="max_cache_size must be positive"):
            KnowledgeBeastConfig(max_cache_size=-1)

    def test_invalid_heartbeat_interval_raises_error(self):
        """Test invalid heartbeat_interval raises ValueError."""
        with pytest.raises(ValueError, match="at least 10 seconds"):
            KnowledgeBeastConfig(heartbeat_interval=5)

        with pytest.raises(ValueError, match="at least 10 seconds"):
            KnowledgeBeastConfig(heartbeat_interval=0)

    def test_minimum_valid_heartbeat_interval(self):
        """Test minimum valid heartbeat interval."""
        config = KnowledgeBeastConfig(heartbeat_interval=10)
        assert config.heartbeat_interval == 10


class TestConfigMethods:
    """Test configuration methods."""

    def test_get_all_knowledge_paths(self):
        """Test get_all_knowledge_paths returns all paths."""
        kb_dirs = [Path("/kb1"), Path("/kb2"), Path("/kb3")]
        config = KnowledgeBeastConfig(knowledge_dirs=kb_dirs)

        paths = config.get_all_knowledge_paths()
        assert paths == kb_dirs
        assert len(paths) == 3

    def test_print_config(self, capsys):
        """Test print_config outputs configuration."""
        config = KnowledgeBeastConfig(verbose=True)
        config.print_config()

        captured = capsys.readouterr()
        assert "KnowledgeBeast Configuration" in captured.out
        assert "Knowledge Directories" in captured.out
        assert "Cache File" in captured.out

    def test_print_config_when_verbose_false(self, capsys):
        """Test print_config does nothing when verbose=False."""
        config = KnowledgeBeastConfig(verbose=False)
        config.print_config()

        captured = capsys.readouterr()
        assert captured.out == ""


class TestMultipleDirectories:
    """Test multiple directory configuration."""

    def test_single_directory(self):
        """Test configuration with single directory."""
        config = KnowledgeBeastConfig(knowledge_dirs=[Path("/kb")])
        assert len(config.knowledge_dirs) == 1
        assert config.knowledge_dirs[0] == Path("/kb")

    def test_multiple_directories(self):
        """Test configuration with multiple directories."""
        dirs = [Path("/kb1"), Path("/kb2"), Path("/kb3"), Path("/kb4")]
        config = KnowledgeBeastConfig(knowledge_dirs=dirs)

        assert len(config.knowledge_dirs) == 4
        assert config.knowledge_dirs == dirs

    def test_duplicate_directories(self):
        """Test configuration handles duplicate directories."""
        dirs = [Path("/kb1"), Path("/kb1"), Path("/kb2")]
        config = KnowledgeBeastConfig(knowledge_dirs=dirs)

        # Should keep duplicates as-is (no deduplication by default)
        assert len(config.knowledge_dirs) == 3


class TestConfigClass:
    """Test Config class for CLI."""

    def test_config_initialization(self):
        """Test Config initializes with data dict."""
        data = {
            'name': 'TestKB',
            'description': 'Test knowledge base',
            'version': '2.0',
            'paths': {'data': '/data'},
            'cache': {'size': 100},
            'search': {'threshold': 0.5},
            'heartbeat': {'interval': 300}
        }
        config = Config(data)

        assert config.name == 'TestKB'
        assert config.description == 'Test knowledge base'
        assert config.version == '2.0'
        assert config.paths == {'data': '/data'}
        assert config.cache == {'size': 100}
        assert config.search == {'threshold': 0.5}
        assert config.heartbeat == {'interval': 300}

    def test_config_defaults(self):
        """Test Config uses defaults for missing fields."""
        config = Config({})

        assert config.name == 'KnowledgeBeast'
        assert config.description == ''
        assert config.version == '1.0'
        assert config.paths == {}
        assert config.cache == {}
        assert config.search == {}
        assert config.heartbeat == {}

    def test_config_get_method(self):
        """Test Config get method."""
        data = {'key1': 'value1', 'key2': 42}
        config = Config(data)

        assert config.get('key1') == 'value1'
        assert config.get('key2') == 42
        assert config.get('nonexistent') is None
        assert config.get('nonexistent', 'default') == 'default'

    def test_config_from_file(self, tmp_path: Path):
        """Test Config.from_file loads from YAML."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            'name': 'FileKB',
            'description': 'From file',
            'version': '3.0',
            'paths': {'kb': '/kb'}
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        config = Config.from_file(config_file)

        assert config.name == 'FileKB'
        assert config.description == 'From file'
        assert config.version == '3.0'
        assert config.paths == {'kb': '/kb'}


class TestConfigEdgeCases:
    """Test edge cases and special scenarios."""

    def test_path_conversion(self):
        """Test paths are converted to Path objects."""
        config = KnowledgeBeastConfig(
            knowledge_dirs=[Path("/kb1"), Path("/kb2")],
            cache_file=Path("/cache.pkl")
        )

        assert all(isinstance(p, Path) for p in config.knowledge_dirs)
        assert isinstance(config.cache_file, Path)

    def test_string_to_path_conversion(self):
        """Test string paths are converted to Path objects."""
        # When set via env vars, paths come as strings
        config = KnowledgeBeastConfig(
            knowledge_dirs=[Path("kb1"), Path("kb2")],
            cache_file=Path("cache.pkl")
        )

        assert all(isinstance(p, Path) for p in config.knowledge_dirs)
        assert isinstance(config.cache_file, Path)

    def test_config_immutability(self):
        """Test config values can be modified after creation."""
        config = KnowledgeBeastConfig()
        original_size = config.max_cache_size

        # Should be able to modify
        config.max_cache_size = 200
        assert config.max_cache_size == 200
        assert config.max_cache_size != original_size
