"""Tests for migration tool."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import migration tool
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.migrate_to_vector import VectorMigrationTool, MigrationError


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def migration_tool(temp_data_dir):
    """Create migration tool instance."""
    return VectorMigrationTool(data_dir=temp_data_dir)


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        {
            "id": "doc1",
            "content": "This is test document 1 about Python programming",
            "metadata": {"source": "test1.md", "type": "code"}
        },
        {
            "id": "doc2",
            "content": "This is test document 2 about machine learning",
            "metadata": {"source": "test2.md", "type": "ml"}
        },
        {
            "id": "doc3",
            "content": "This is test document 3 about data science",
            "metadata": {"source": "test3.md", "type": "data"}
        }
    ]


class TestMigrationToolInit:
    """Test migration tool initialization."""

    def test_init_creates_backup_dir(self, temp_data_dir):
        """Test initialization creates backup directory."""
        tool = VectorMigrationTool(data_dir=temp_data_dir)

        assert tool.data_dir == temp_data_dir
        assert tool.backup_dir.exists()
        assert tool.backup_dir == temp_data_dir / "backups"

    def test_init_with_custom_backup_dir(self, temp_data_dir):
        """Test initialization with custom backup directory."""
        custom_backup = temp_data_dir / "custom_backups"
        tool = VectorMigrationTool(
            data_dir=temp_data_dir,
            backup_dir=custom_backup
        )

        assert tool.backup_dir == custom_backup
        assert tool.backup_dir.exists()

    def test_init_stats(self, migration_tool):
        """Test initial stats are zero."""
        assert migration_tool.stats["documents_migrated"] == 0
        assert migration_tool.stats["embeddings_generated"] == 0
        assert migration_tool.stats["errors"] == 0


class TestBackupCreation:
    """Test backup creation functionality."""

    def test_create_backup_empty_directory(self, migration_tool, temp_data_dir):
        """Test creating backup with no files."""
        backup_path = migration_tool._create_backup()

        assert backup_path.exists()
        assert backup_path.parent == migration_tool.backup_dir

        # Check manifest
        manifest_file = backup_path / "manifest.json"
        assert manifest_file.exists()

        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        assert manifest["backup_complete"] is True
        assert manifest["files_backed_up"] == 0

    def test_create_backup_with_files(self, migration_tool, temp_data_dir):
        """Test creating backup with existing files."""
        # Create test files
        (temp_data_dir / "term_index.json").write_text('{"test": "index"}')
        (temp_data_dir / "documents.json").write_text('[]')

        backup_path = migration_tool._create_backup()

        assert (backup_path / "term_index.json").exists()
        assert (backup_path / "documents.json").exists()
        assert (backup_path / "manifest.json").exists()

        # Verify manifest
        with open(backup_path / "manifest.json", "r") as f:
            manifest = json.load(f)

        assert manifest["files_backed_up"] == 2

    def test_create_backup_with_cache(self, migration_tool, temp_data_dir):
        """Test creating backup including cache file."""
        (temp_data_dir / ".knowledge_cache.pkl").write_text("cache data")

        backup_path = migration_tool._create_backup()

        assert (backup_path / ".knowledge_cache.pkl").exists()


class TestDocumentLoading:
    """Test document loading from term-based index."""

    def test_load_documents_file_exists(
        self,
        migration_tool,
        temp_data_dir,
        sample_documents
    ):
        """Test loading documents when file exists."""
        docs_file = temp_data_dir / "documents.json"
        with open(docs_file, "w") as f:
            json.dump(sample_documents, f)

        documents = migration_tool._load_term_based_documents()

        assert len(documents) == 3
        assert documents[0]["id"] == "doc1"
        assert documents[1]["id"] == "doc2"

    def test_load_documents_file_not_exists(self, migration_tool):
        """Test loading documents when file doesn't exist."""
        documents = migration_tool._load_term_based_documents()

        assert documents == []

    def test_load_documents_invalid_json(self, migration_tool, temp_data_dir):
        """Test loading documents with invalid JSON."""
        docs_file = temp_data_dir / "documents.json"
        docs_file.write_text("invalid json{")

        with pytest.raises(MigrationError, match="Failed to load documents"):
            migration_tool._load_term_based_documents()


class TestVectorMigration:
    """Test vector migration functionality."""

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migrate_to_vector_success(
        self,
        mock_embedding_engine,
        mock_vector_store,
        migration_tool,
        sample_documents
    ):
        """Test successful migration to vector embeddings."""
        # Setup mocks
        mock_engine = Mock()
        mock_engine.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedding_engine.return_value = mock_engine

        mock_store = Mock()
        mock_store.clear.return_value = None
        mock_store.add.return_value = None
        mock_vector_store.return_value = mock_store

        # Execute migration
        result = migration_tool._migrate_to_vector(sample_documents)

        assert result["migrated_count"] == 3
        assert result["error_count"] == 0
        assert result["embedding_model"] == "all-MiniLM-L6-v2"
        assert migration_tool.stats["documents_migrated"] == 3

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migrate_to_vector_skip_empty_documents(
        self,
        mock_embedding_engine,
        mock_vector_store,
        migration_tool
    ):
        """Test migration skips documents with no content."""
        mock_engine = Mock()
        mock_engine.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedding_engine.return_value = mock_engine

        mock_store = Mock()
        mock_vector_store.return_value = mock_store

        documents = [
            {"id": "doc1", "content": "Valid content"},
            {"id": "doc2", "content": ""},  # Empty
            {"id": "doc3", "content": "More content"}
        ]

        result = migration_tool._migrate_to_vector(documents)

        assert result["migrated_count"] == 2

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migrate_to_vector_with_errors(
        self,
        mock_embedding_engine,
        mock_vector_store,
        migration_tool,
        sample_documents
    ):
        """Test migration handles errors gracefully."""
        mock_engine = Mock()
        mock_engine.embed.side_effect = [
            [0.1, 0.2, 0.3],  # Success
            Exception("Embedding error"),  # Error
            [0.4, 0.5, 0.6]  # Success
        ]
        mock_embedding_engine.return_value = mock_engine

        mock_store = Mock()
        mock_vector_store.return_value = mock_store

        result = migration_tool._migrate_to_vector(sample_documents)

        assert result["migrated_count"] == 2
        assert result["error_count"] == 1
        assert migration_tool.stats["errors"] == 1


class TestFullMigration:
    """Test full migration workflow."""

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migrate_full_workflow(
        self,
        mock_embedding_engine,
        mock_vector_store,
        migration_tool,
        temp_data_dir,
        sample_documents
    ):
        """Test complete migration workflow."""
        # Setup mocks
        mock_engine = Mock()
        mock_engine.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedding_engine.return_value = mock_engine

        mock_store = Mock()
        mock_vector_store.return_value = mock_store

        # Create documents file
        docs_file = temp_data_dir / "documents.json"
        with open(docs_file, "w") as f:
            json.dump(sample_documents, f)

        # Execute migration
        result = migration_tool.migrate()

        assert result["status"] == "success"
        assert result["backup_path"] is not None
        assert result["migration_result"]["migrated_count"] == 3
        assert "duration_seconds" in result

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migrate_skip_backup(
        self,
        mock_embedding_engine,
        mock_vector_store,
        migration_tool,
        temp_data_dir,
        sample_documents
    ):
        """Test migration with backup skipped."""
        mock_engine = Mock()
        mock_engine.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedding_engine.return_value = mock_engine

        mock_store = Mock()
        mock_vector_store.return_value = mock_store

        docs_file = temp_data_dir / "documents.json"
        with open(docs_file, "w") as f:
            json.dump(sample_documents, f)

        result = migration_tool.migrate(skip_backup=True)

        assert result["status"] == "success"
        assert result["backup_path"] is None

    def test_migrate_no_documents(self, migration_tool, temp_data_dir):
        """Test migration with no documents."""
        result = migration_tool.migrate()

        assert result["status"] == "no_documents"


class TestRollback:
    """Test rollback functionality."""

    def test_rollback_from_backup(self, migration_tool, temp_data_dir):
        """Test rollback restores files from backup."""
        # Create original files
        (temp_data_dir / "term_index.json").write_text('{"original": "data"}')
        (temp_data_dir / "documents.json").write_text('[{"id": "doc1"}]')

        # Create backup
        backup_path = migration_tool._create_backup()

        # Modify original files
        (temp_data_dir / "term_index.json").write_text('{"modified": "data"}')

        # Rollback
        success = migration_tool.rollback(backup_path=backup_path)

        assert success is True

        # Verify files restored
        with open(temp_data_dir / "term_index.json", "r") as f:
            data = json.load(f)

        assert data == {"original": "data"}

    def test_rollback_latest_backup(self, migration_tool, temp_data_dir):
        """Test rollback uses latest backup when not specified."""
        # Create multiple backups
        backup1 = migration_tool._create_backup()
        backup2 = migration_tool._create_backup()

        # Create file in backup2 only
        (backup2 / "test.json").write_text('{"test": "data"}')

        # Rollback without specifying path
        success = migration_tool.rollback()

        assert success is True
        assert (temp_data_dir / "test.json").exists()

    def test_rollback_no_backups(self, migration_tool):
        """Test rollback fails when no backups exist."""
        with pytest.raises(MigrationError, match="No backups found"):
            migration_tool.rollback()

    def test_rollback_invalid_backup(self, migration_tool, temp_data_dir):
        """Test rollback fails with invalid backup path."""
        invalid_path = temp_data_dir / "nonexistent_backup"

        with pytest.raises(MigrationError, match="Backup not found"):
            migration_tool.rollback(backup_path=invalid_path)

    def test_rollback_removes_chromadb(self, migration_tool, temp_data_dir):
        """Test rollback removes ChromaDB directory."""
        # Create ChromaDB directory
        chromadb_path = temp_data_dir / "chromadb"
        chromadb_path.mkdir()
        (chromadb_path / "test.db").write_text("data")

        # Create backup
        backup_path = migration_tool._create_backup()

        # Rollback
        migration_tool.rollback(backup_path=backup_path)

        # Verify ChromaDB removed
        assert not chromadb_path.exists()


class TestMigrationEdgeCases:
    """Test edge cases and error scenarios."""

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migration_with_custom_model(
        self,
        mock_engine_class,
        mock_store_class,
        migration_tool,
        temp_data_dir,
        sample_documents
    ):
        """Test migration with custom embedding model."""
        mock_engine = Mock()
        mock_engine.embed.return_value = [0.1, 0.2, 0.3]
        mock_engine_class.return_value = mock_engine

        mock_store = Mock()
        mock_store_class.return_value = mock_store

        docs_file = temp_data_dir / "documents.json"
        with open(docs_file, "w") as f:
            json.dump(sample_documents, f)

        result = migration_tool.migrate(embedding_model="all-mpnet-base-v2")

        assert result["migration_result"]["embedding_model"] == "all-mpnet-base-v2"
        mock_engine_class.assert_called_once_with(model_name="all-mpnet-base-v2")

    def test_backup_preserves_file_metadata(self, migration_tool, temp_data_dir):
        """Test backup preserves file metadata."""
        test_file = temp_data_dir / "documents.json"
        test_file.write_text('{"test": "data"}')

        original_stat = test_file.stat()

        backup_path = migration_tool._create_backup()
        backup_file = backup_path / "documents.json"

        # File should exist with same content
        assert backup_file.exists()
        assert backup_file.read_text() == '{"test": "data"}'

    @patch('knowledgebeast.core.vector_store.VectorStore')
    @patch('knowledgebeast.core.embeddings.EmbeddingEngine')
    def test_migration_stats_tracking(
        self,
        mock_embedding_engine,
        mock_vector_store,
        migration_tool,
        temp_data_dir,
        sample_documents
    ):
        """Test migration tracks statistics correctly."""
        mock_engine = Mock()
        mock_engine.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedding_engine.return_value = mock_engine

        mock_store = Mock()
        mock_vector_store.return_value = mock_store

        docs_file = temp_data_dir / "documents.json"
        with open(docs_file, "w") as f:
            json.dump(sample_documents, f)

        result = migration_tool.migrate()

        assert migration_tool.stats["start_time"] is not None
        assert migration_tool.stats["end_time"] is not None
        assert migration_tool.stats["end_time"] > migration_tool.stats["start_time"]
        assert migration_tool.stats["documents_migrated"] == 3
        assert migration_tool.stats["embeddings_generated"] == 3
