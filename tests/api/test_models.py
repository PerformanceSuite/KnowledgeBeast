"""Comprehensive test suite for API models with 100% coverage.

Tests all Pydantic models in knowledgebeast/api/models.py including:
- Validation rules and constraints
- Field validators and custom logic
- Serialization/deserialization
- Edge cases and error handling
- Default values and optional fields
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from knowledgebeast.api.models import (
    # Request models
    QueryRequest,
    IngestRequest,
    BatchIngestRequest,
    WarmRequest,
    CollectionRequest,
    # Response models
    QueryResult,
    QueryResponse,
    IngestResponse,
    BatchIngestResponse,
    HealthResponse,
    StatsResponse,
    HeartbeatStatusResponse,
    HeartbeatActionResponse,
    CacheClearResponse,
    WarmResponse,
    CollectionInfo,
    CollectionsResponse,
    ErrorResponse,
)


# ============================================================================
# Request Model Tests
# ============================================================================

class TestQueryRequest:
    """Test QueryRequest model validation and edge cases."""

    def test_valid_query_request_minimal(self):
        """Test minimal valid query request with defaults."""
        req = QueryRequest(query="test query")
        assert req.query == "test query"
        assert req.use_cache is True
        assert req.limit == 10
        assert req.offset == 0

    def test_valid_query_request_full(self):
        """Test query request with all fields specified."""
        req = QueryRequest(
            query="audio processing",
            use_cache=False,
            limit=50,
            offset=20
        )
        assert req.query == "audio processing"
        assert req.use_cache is False
        assert req.limit == 50
        assert req.offset == 20

    def test_query_whitespace_stripping(self):
        """Test that query whitespace is stripped."""
        req = QueryRequest(query="  test query  ")
        assert req.query == "test query"

    def test_query_min_length_validation(self):
        """Test query minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="")

        errors = exc_info.value.errors()
        # Pydantic min_length triggers before validator
        assert any(e['type'] == 'string_too_short' for e in errors)

    def test_query_whitespace_only_validation(self):
        """Test that whitespace-only queries are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="   ")

        errors = exc_info.value.errors()
        assert any("Query cannot be empty" in str(e) for e in errors)

    def test_query_max_length_validation(self):
        """Test query maximum length validation (1000 chars)."""
        long_query = "a" * 1001
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query=long_query)

        errors = exc_info.value.errors()
        assert any(e['type'] == 'string_too_long' for e in errors)

    def test_query_max_length_boundary(self):
        """Test query at exact max length (1000 chars)."""
        max_query = "a" * 1000
        req = QueryRequest(query=max_query)
        assert len(req.query) == 1000

    @pytest.mark.parametrize("dangerous_char", ['<', '>', ';', '&', '|', '$', '`', '\n', '\r'])
    def test_query_dangerous_characters(self, dangerous_char):
        """Test that dangerous characters are rejected."""
        query = f"test{dangerous_char}query"
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query=query)

        errors = exc_info.value.errors()
        # Check error type is value_error and message contains "invalid character"
        assert any(e['type'] == 'value_error' and "invalid character" in str(e) for e in errors)

    def test_limit_minimum_validation(self):
        """Test limit minimum value (1)."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="test", limit=0)

        errors = exc_info.value.errors()
        assert any(e['type'] == 'greater_than_equal' for e in errors)

    def test_limit_maximum_validation(self):
        """Test limit maximum value (100)."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="test", limit=101)

        errors = exc_info.value.errors()
        assert any(e['type'] == 'less_than_equal' for e in errors)

    def test_limit_boundaries(self):
        """Test limit at boundaries (1 and 100)."""
        req1 = QueryRequest(query="test", limit=1)
        assert req1.limit == 1

        req2 = QueryRequest(query="test", limit=100)
        assert req2.limit == 100

    def test_offset_minimum_validation(self):
        """Test offset minimum value (0)."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="test", offset=-1)

        errors = exc_info.value.errors()
        assert any(e['type'] == 'greater_than_equal' for e in errors)

    def test_offset_zero(self):
        """Test offset at minimum (0)."""
        req = QueryRequest(query="test", offset=0)
        assert req.offset == 0

    def test_offset_large_value(self):
        """Test offset with large value."""
        req = QueryRequest(query="test", offset=999999)
        assert req.offset == 999999

    def test_serialization(self):
        """Test model serialization to dict."""
        req = QueryRequest(query="test", use_cache=False, limit=20, offset=10)
        data = req.model_dump()

        # Phase 2 added re-ranking fields
        assert data == {
            "query": "test",
            "use_cache": False,
            "limit": 20,
            "offset": 10,
            "rerank": False,
            "rerank_top_k": 50,
            "diversity": None
        }

    def test_json_serialization(self):
        """Test model JSON serialization."""
        req = QueryRequest(query="test")
        json_str = req.model_dump_json()

        assert "test" in json_str
        assert "use_cache" in json_str

    def test_from_dict(self):
        """Test creating model from dict."""
        data = {"query": "test query", "limit": 25}
        req = QueryRequest(**data)

        assert req.query == "test query"
        assert req.limit == 25
        assert req.use_cache is True  # default


class TestIngestRequest:
    """Test IngestRequest model validation and security."""

    def test_valid_ingest_request_minimal(self, tmp_path):
        """Test minimal valid ingest request."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        req = IngestRequest(file_path=str(test_file))
        assert req.file_path == str(test_file.resolve())
        assert req.metadata is None

    def test_valid_ingest_request_with_metadata(self, tmp_path):
        """Test ingest request with metadata."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        metadata = {"category": "audio", "tags": ["test"]}
        req = IngestRequest(file_path=str(test_file), metadata=metadata)

        assert req.metadata == metadata

    @pytest.mark.parametrize("extension", ['.md', '.txt', '.pdf', '.docx', '.html', '.htm'])
    def test_allowed_file_extensions(self, tmp_path, extension):
        """Test all allowed file extensions."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text("content")

        req = IngestRequest(file_path=str(test_file))
        assert req.file_path == str(test_file.resolve())

    @pytest.mark.parametrize("extension", ['.exe', '.sh', '.bat', '.py', '.js'])
    def test_disallowed_file_extensions(self, tmp_path, extension):
        """Test that disallowed file extensions are rejected."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text("content")

        with pytest.raises(ValidationError) as exc_info:
            IngestRequest(file_path=str(test_file))

        errors = exc_info.value.errors()
        assert any("Unsupported file type" in str(e) for e in errors)

    def test_path_traversal_attack_prevention(self, tmp_path):
        """Test that path traversal attacks are prevented."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        # Try path traversal
        malicious_path = f"{test_file.parent}/../test.md"

        with pytest.raises(ValidationError) as exc_info:
            IngestRequest(file_path=malicious_path)

        errors = exc_info.value.errors()
        assert any("Path traversal detected" in str(e) for e in errors)

    def test_nonexistent_file_validation(self, tmp_path):
        """Test that nonexistent files pass model validation.

        Note: File existence is validated in the route handler (returns 404),
        not in the model validator (would return 422). This allows proper
        REST error codes: 404 for missing resources, 422 for validation errors.
        """
        nonexistent = tmp_path / "nonexistent.md"

        # Model validation should PASS (only checks extension and path traversal)
        req = IngestRequest(file_path=str(nonexistent))
        assert req.file_path == str(nonexistent)

    def test_directory_path_validation(self, tmp_path):
        """Test that directory paths pass model validation.

        Note: The is_file() check is performed in the route handler,
        not in the model validator. This allows proper REST error codes:
        400 for bad requests (directory instead of file), 422 for validation errors.
        """
        # Create a directory with .md extension to test the "is_file" check
        dir_with_ext = tmp_path / "fake.md"
        dir_with_ext.mkdir()

        # Model validation should PASS (only checks extension and path traversal)
        req = IngestRequest(file_path=str(dir_with_ext))
        assert req.file_path == str(dir_with_ext)

    def test_invalid_path_validation(self):
        """Test that paths with invalid characters pass model validation.

        Note: The model validator only checks file extensions and path traversal.
        Other path validity checks (null bytes, special characters, etc.) are
        deferred to the route handler where they'll fail during actual file operations.
        This is intentional - the model focuses on security (traversal) and business
        logic (file types), not filesystem-specific validation.
        """
        # Null bytes are accepted by Path() and will fail later in route handler
        req = IngestRequest(file_path="\x00invalid.md")
        assert req.file_path == "\x00invalid.md"

    def test_path_resolution(self, tmp_path):
        """Test that paths are properly resolved to absolute paths."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        req = IngestRequest(file_path=str(test_file))
        assert Path(req.file_path).is_absolute()
        assert Path(req.file_path).resolve() == test_file.resolve()

    def test_case_insensitive_extensions(self, tmp_path):
        """Test that file extensions are case-insensitive."""
        test_file = tmp_path / "test.MD"
        test_file.write_text("content")

        req = IngestRequest(file_path=str(test_file))
        assert req.file_path == str(test_file.resolve())


class TestBatchIngestRequest:
    """Test BatchIngestRequest model validation."""

    def test_valid_batch_ingest_minimal(self, tmp_path):
        """Test minimal valid batch ingest request."""
        files = []
        for i in range(3):
            f = tmp_path / f"test{i}.md"
            f.write_text(f"content {i}")
            files.append(str(f))

        req = BatchIngestRequest(file_paths=files)
        assert len(req.file_paths) == 3
        assert req.metadata is None

    def test_batch_ingest_with_metadata(self, tmp_path):
        """Test batch ingest with metadata."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        metadata = {"batch": "test-batch"}
        req = BatchIngestRequest(file_paths=[str(test_file)], metadata=metadata)

        assert req.metadata == metadata

    def test_empty_file_list_validation(self):
        """Test that empty file list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BatchIngestRequest(file_paths=[])

        errors = exc_info.value.errors()
        assert any(e['type'] == 'too_short' for e in errors)

    def test_max_file_list_validation(self, tmp_path):
        """Test maximum file list size (100)."""
        # Create 101 files
        files = []
        for i in range(101):
            f = tmp_path / f"test{i}.md"
            f.write_text("content")
            files.append(str(f))

        with pytest.raises(ValidationError) as exc_info:
            BatchIngestRequest(file_paths=files)

        errors = exc_info.value.errors()
        assert any(e['type'] == 'too_long' for e in errors)

    def test_max_file_list_boundary(self, tmp_path):
        """Test at exactly 100 files."""
        files = []
        for i in range(100):
            f = tmp_path / f"test{i}.md"
            f.write_text("content")
            files.append(str(f))

        req = BatchIngestRequest(file_paths=files)
        assert len(req.file_paths) == 100


class TestWarmRequest:
    """Test WarmRequest model."""

    def test_warm_request_default(self):
        """Test warm request with default values."""
        req = WarmRequest()
        assert req.force_rebuild is False

    def test_warm_request_force_rebuild(self):
        """Test warm request with force_rebuild=True."""
        req = WarmRequest(force_rebuild=True)
        assert req.force_rebuild is True

    def test_warm_request_explicit_false(self):
        """Test warm request with explicit force_rebuild=False."""
        req = WarmRequest(force_rebuild=False)
        assert req.force_rebuild is False


class TestCollectionRequest:
    """Test CollectionRequest model validation."""

    def test_valid_collection_name(self):
        """Test valid collection name."""
        req = CollectionRequest(name="my-collection")
        assert req.name == "my-collection"

    def test_collection_name_with_underscores(self):
        """Test collection name with underscores."""
        req = CollectionRequest(name="my_collection_123")
        assert req.name == "my_collection_123"

    def test_collection_name_alphanumeric(self):
        """Test collection name with alphanumeric characters."""
        req = CollectionRequest(name="collection123")
        assert req.name == "collection123"

    def test_collection_name_min_length(self):
        """Test collection name minimum length."""
        with pytest.raises(ValidationError) as exc_info:
            CollectionRequest(name="")

        errors = exc_info.value.errors()
        assert any(e['type'] == 'string_too_short' for e in errors)

    def test_collection_name_max_length(self):
        """Test collection name maximum length (100)."""
        long_name = "a" * 101
        with pytest.raises(ValidationError) as exc_info:
            CollectionRequest(name=long_name)

        errors = exc_info.value.errors()
        assert any(e['type'] == 'string_too_long' for e in errors)

    def test_collection_name_invalid_characters(self):
        """Test that invalid characters are rejected."""
        invalid_names = ["my collection", "my@collection", "my/collection", "my.collection"]

        for name in invalid_names:
            with pytest.raises(ValidationError):
                CollectionRequest(name=name)

    def test_collection_name_pattern_validation(self):
        """Test collection name pattern (alphanumeric, dash, underscore only)."""
        valid_names = ["test", "test-123", "test_abc", "TEST-COLLECTION_123"]

        for name in valid_names:
            req = CollectionRequest(name=name)
            assert req.name == name


# ============================================================================
# Response Model Tests
# ============================================================================

class TestQueryResult:
    """Test QueryResult model."""

    def test_valid_query_result(self):
        """Test valid query result creation."""
        result = QueryResult(
            doc_id="kb/doc.md",
            content="Test content",
            name="Test Doc",
            path="/path/to/doc.md",
            kb_dir="/kb"
        )

        assert result.doc_id == "kb/doc.md"
        assert result.content == "Test content"
        assert result.name == "Test Doc"
        assert result.path == "/path/to/doc.md"
        assert result.kb_dir == "/kb"

    def test_query_result_empty_content(self):
        """Test query result with empty content."""
        result = QueryResult(
            doc_id="kb/doc.md",
            content="",
            name="Empty Doc",
            path="/path/to/doc.md",
            kb_dir="/kb"
        )

        assert result.content == ""

    def test_query_result_serialization(self):
        """Test query result serialization."""
        result = QueryResult(
            doc_id="kb/doc.md",
            content="content",
            name="name",
            path="/path",
            kb_dir="/kb"
        )

        data = result.model_dump()
        assert data == {
            "doc_id": "kb/doc.md",
            "content": "content",
            "name": "name",
            "path": "/path",
            "kb_dir": "/kb",
            "vector_score": None,
            "rerank_score": None,
            "final_score": None,
            "rank": None
        }


class TestQueryResponse:
    """Test QueryResponse model."""

    def test_valid_query_response(self):
        """Test valid query response."""
        results = [
            QueryResult(
                doc_id="doc1",
                content="content1",
                name="Doc 1",
                path="/path1",
                kb_dir="/kb"
            )
        ]

        response = QueryResponse(
            results=results,
            count=1,
            cached=True,
            query="test query"
        )

        assert len(response.results) == 1
        assert response.count == 1
        assert response.cached is True
        assert response.query == "test query"

    def test_query_response_empty_results(self):
        """Test query response with empty results."""
        response = QueryResponse(
            results=[],
            count=0,
            cached=False,
            query="no results"
        )

        assert len(response.results) == 0
        assert response.count == 0
        assert response.cached is False

    def test_query_response_large_results(self):
        """Test query response with many results."""
        results = [
            QueryResult(
                doc_id=f"doc{i}",
                content=f"content{i}",
                name=f"Doc {i}",
                path=f"/path{i}",
                kb_dir="/kb"
            )
            for i in range(100)
        ]

        response = QueryResponse(
            results=results,
            count=100,
            cached=False,
            query="large query"
        )

        assert len(response.results) == 100
        assert response.count == 100


class TestIngestResponse:
    """Test IngestResponse model."""

    def test_ingest_response_success(self):
        """Test successful ingest response."""
        response = IngestResponse(
            success=True,
            file_path="/path/to/file.md",
            doc_id="kb/file.md",
            message="Successfully ingested"
        )

        assert response.success is True
        assert response.file_path == "/path/to/file.md"
        assert response.doc_id == "kb/file.md"
        assert response.message == "Successfully ingested"

    def test_ingest_response_failure(self):
        """Test failed ingest response."""
        response = IngestResponse(
            success=False,
            file_path="/path/to/file.md",
            doc_id="",
            message="Ingestion failed"
        )

        assert response.success is False
        assert response.message == "Ingestion failed"


class TestBatchIngestResponse:
    """Test BatchIngestResponse model."""

    def test_batch_ingest_response_all_success(self):
        """Test batch ingest response with all successes."""
        response = BatchIngestResponse(
            success=True,
            total_files=10,
            successful=10,
            failed=0,
            failed_files=[],
            message="All successful"
        )

        assert response.success is True
        assert response.total_files == 10
        assert response.successful == 10
        assert response.failed == 0
        assert len(response.failed_files) == 0

    def test_batch_ingest_response_partial_success(self):
        """Test batch ingest response with partial success."""
        response = BatchIngestResponse(
            success=False,
            total_files=10,
            successful=7,
            failed=3,
            failed_files=["/path1.md", "/path2.md", "/path3.md"],
            message="Partial success"
        )

        assert response.success is False
        assert response.total_files == 10
        assert response.successful == 7
        assert response.failed == 3
        assert len(response.failed_files) == 3

    def test_batch_ingest_response_default_failed_files(self):
        """Test batch ingest response with default empty failed_files."""
        response = BatchIngestResponse(
            success=True,
            total_files=5,
            successful=5,
            failed=0,
            message="All good"
        )

        assert response.failed_files == []


class TestHealthResponse:
    """Test HealthResponse model."""

    def test_health_response_healthy(self):
        """Test healthy health response."""
        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            kb_initialized=True,
            timestamp="2025-10-05T12:00:00Z"
        )

        assert response.status == "healthy"
        assert response.version == "0.1.0"
        assert response.kb_initialized is True
        assert response.timestamp == "2025-10-05T12:00:00Z"

    def test_health_response_degraded(self):
        """Test degraded health response."""
        response = HealthResponse(
            status="degraded",
            version="0.1.0",
            kb_initialized=True,
            timestamp="2025-10-05T12:00:00Z"
        )

        assert response.status == "degraded"

    def test_health_response_unhealthy(self):
        """Test unhealthy health response."""
        response = HealthResponse(
            status="unhealthy",
            version="0.1.0",
            kb_initialized=False,
            timestamp="2025-10-05T12:00:00Z"
        )

        assert response.status == "unhealthy"
        assert response.kb_initialized is False


class TestStatsResponse:
    """Test StatsResponse model."""

    def test_stats_response_complete(self):
        """Test complete stats response."""
        response = StatsResponse(
            queries=100,
            cache_hits=80,
            cache_misses=20,
            cache_hit_rate="80.0%",
            warm_queries=5,
            last_warm_time=2.5,
            total_documents=50,
            total_terms=1000,
            documents=50,
            terms=1000,
            cached_queries=30,
            last_access_age="5s ago",
            knowledge_dirs=["/kb"],
            total_queries=100
        )

        assert response.queries == 100
        assert response.cache_hits == 80
        assert response.cache_misses == 20
        assert response.cache_hit_rate == "80.0%"
        assert response.warm_queries == 5
        assert response.last_warm_time == 2.5
        assert response.total_documents == 50
        assert response.cached_queries == 30

    def test_stats_response_no_warm_time(self):
        """Test stats response with None warm time."""
        response = StatsResponse(
            queries=10,
            cache_hits=5,
            cache_misses=5,
            cache_hit_rate="50.0%",
            warm_queries=0,
            last_warm_time=None,
            total_documents=10,
            total_terms=100,
            documents=10,
            terms=100,
            cached_queries=5,
            last_access_age="1s ago",
            knowledge_dirs=["/kb"],
            total_queries=10
        )

        assert response.last_warm_time is None

    def test_stats_response_multiple_kb_dirs(self):
        """Test stats response with multiple knowledge directories."""
        response = StatsResponse(
            queries=50,
            cache_hits=25,
            cache_misses=25,
            cache_hit_rate="50.0%",
            warm_queries=2,
            last_warm_time=1.5,
            total_documents=100,
            total_terms=2000,
            documents=100,
            terms=2000,
            cached_queries=20,
            last_access_age="2s ago",
            knowledge_dirs=["/kb1", "/kb2", "/kb3"],
            total_queries=50
        )

        assert len(response.knowledge_dirs) == 3
        assert "/kb1" in response.knowledge_dirs


class TestHeartbeatStatusResponse:
    """Test HeartbeatStatusResponse model."""

    def test_heartbeat_status_running(self):
        """Test heartbeat status when running."""
        response = HeartbeatStatusResponse(
            running=True,
            interval=300,
            heartbeat_count=10,
            last_heartbeat="30s ago"
        )

        assert response.running is True
        assert response.interval == 300
        assert response.heartbeat_count == 10
        assert response.last_heartbeat == "30s ago"

    def test_heartbeat_status_not_running(self):
        """Test heartbeat status when not running."""
        response = HeartbeatStatusResponse(
            running=False,
            interval=300,
            heartbeat_count=0,
            last_heartbeat=None
        )

        assert response.running is False
        assert response.heartbeat_count == 0
        assert response.last_heartbeat is None


class TestHeartbeatActionResponse:
    """Test HeartbeatActionResponse model."""

    def test_heartbeat_start_success(self):
        """Test successful heartbeat start response."""
        response = HeartbeatActionResponse(
            success=True,
            message="Heartbeat started",
            running=True
        )

        assert response.success is True
        assert response.message == "Heartbeat started"
        assert response.running is True

    def test_heartbeat_stop_success(self):
        """Test successful heartbeat stop response."""
        response = HeartbeatActionResponse(
            success=True,
            message="Heartbeat stopped",
            running=False
        )

        assert response.success is True
        assert response.running is False

    def test_heartbeat_action_failure(self):
        """Test failed heartbeat action."""
        response = HeartbeatActionResponse(
            success=False,
            message="Failed to start heartbeat",
            running=False
        )

        assert response.success is False


class TestCacheClearResponse:
    """Test CacheClearResponse model."""

    def test_cache_clear_success(self):
        """Test successful cache clear."""
        response = CacheClearResponse(
            success=True,
            cleared_count=50,
            message="Cache cleared: 50 entries"
        )

        assert response.success is True
        assert response.cleared_count == 50
        assert "50" in response.message

    def test_cache_clear_empty(self):
        """Test cache clear with no entries."""
        response = CacheClearResponse(
            success=True,
            cleared_count=0,
            message="Cache was already empty"
        )

        assert response.success is True
        assert response.cleared_count == 0


class TestWarmResponse:
    """Test WarmResponse model."""

    def test_warm_response_success(self):
        """Test successful warm response."""
        response = WarmResponse(
            success=True,
            warm_time=2.5,
            queries_executed=7,
            documents_loaded=42,
            message="Warmed in 2.5s"
        )

        assert response.success is True
        assert response.warm_time == 2.5
        assert response.queries_executed == 7
        assert response.documents_loaded == 42

    def test_warm_response_failure(self):
        """Test failed warm response."""
        response = WarmResponse(
            success=False,
            warm_time=0.0,
            queries_executed=0,
            documents_loaded=0,
            message="Warming failed"
        )

        assert response.success is False
        assert response.warm_time == 0.0

    def test_warm_response_large_dataset(self):
        """Test warm response with large dataset."""
        response = WarmResponse(
            success=True,
            warm_time=15.75,
            queries_executed=100,
            documents_loaded=10000,
            message="Large dataset warmed"
        )

        assert response.documents_loaded == 10000
        assert response.queries_executed == 100


class TestCollectionInfo:
    """Test CollectionInfo model."""

    def test_collection_info_basic(self):
        """Test basic collection info."""
        info = CollectionInfo(
            name="test-collection",
            document_count=50,
            term_count=1000,
            cache_size=25
        )

        assert info.name == "test-collection"
        assert info.document_count == 50
        assert info.term_count == 1000
        assert info.cache_size == 25

    def test_collection_info_empty(self):
        """Test collection info for empty collection."""
        info = CollectionInfo(
            name="empty-collection",
            document_count=0,
            term_count=0,
            cache_size=0
        )

        assert info.document_count == 0
        assert info.term_count == 0
        assert info.cache_size == 0


class TestCollectionsResponse:
    """Test CollectionsResponse model."""

    def test_collections_response_single(self):
        """Test collections response with single collection."""
        collections = [
            CollectionInfo(
                name="kb",
                document_count=42,
                term_count=1500,
                cache_size=20
            )
        ]

        response = CollectionsResponse(
            collections=collections,
            count=1
        )

        assert len(response.collections) == 1
        assert response.count == 1

    def test_collections_response_multiple(self):
        """Test collections response with multiple collections."""
        collections = [
            CollectionInfo(name=f"kb{i}", document_count=i*10, term_count=i*100, cache_size=i)
            for i in range(5)
        ]

        response = CollectionsResponse(
            collections=collections,
            count=5
        )

        assert len(response.collections) == 5
        assert response.count == 5

    def test_collections_response_empty(self):
        """Test collections response with no collections."""
        response = CollectionsResponse(
            collections=[],
            count=0
        )

        assert len(response.collections) == 0
        assert response.count == 0


class TestErrorResponse:
    """Test ErrorResponse model."""

    def test_error_response_basic(self):
        """Test basic error response."""
        response = ErrorResponse(
            error="ValidationError",
            message="Invalid input",
            status_code=400
        )

        assert response.error == "ValidationError"
        assert response.message == "Invalid input"
        assert response.detail is None
        assert response.status_code == 400

    def test_error_response_with_detail(self):
        """Test error response with detail."""
        response = ErrorResponse(
            error="NotFoundError",
            message="Resource not found",
            detail="Document ID 'xyz' does not exist",
            status_code=404
        )

        assert response.error == "NotFoundError"
        assert response.message == "Resource not found"
        assert response.detail == "Document ID 'xyz' does not exist"
        assert response.status_code == 404

    @pytest.mark.parametrize("status_code,error_type", [
        (400, "BadRequest"),
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (404, "NotFound"),
        (500, "InternalServerError"),
        (503, "ServiceUnavailable")
    ])
    def test_error_response_status_codes(self, status_code, error_type):
        """Test error response with various status codes."""
        response = ErrorResponse(
            error=error_type,
            message="Error occurred",
            status_code=status_code
        )

        assert response.status_code == status_code
        assert response.error == error_type

    def test_error_response_serialization(self):
        """Test error response serialization."""
        response = ErrorResponse(
            error="TestError",
            message="Test message",
            detail="Test detail",
            status_code=500
        )

        data = response.model_dump()
        assert data == {
            "error": "TestError",
            "message": "Test message",
            "detail": "Test detail",
            "status_code": 500
        }


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestModelIntegration:
    """Test model integration and edge cases."""

    def test_query_request_json_schema(self):
        """Test that model has proper JSON schema."""
        schema = QueryRequest.model_json_schema()

        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "example" in schema

    def test_all_models_serializable(self):
        """Test that all models can be serialized to JSON."""
        # This ensures model_dump_json() works for all models
        models = [
            QueryRequest(query="test"),
            WarmRequest(),
            CollectionRequest(name="test"),
        ]

        for model in models:
            json_str = model.model_dump_json()
            assert isinstance(json_str, str)
            assert len(json_str) > 0

    def test_response_models_from_dict(self):
        """Test creating response models from dictionaries."""
        data = {
            "success": True,
            "warm_time": 2.5,
            "queries_executed": 7,
            "documents_loaded": 42,
            "message": "Success"
        }

        response = WarmResponse(**data)
        assert response.success is True
        assert response.warm_time == 2.5

    def test_nested_model_serialization(self):
        """Test serialization of nested models."""
        query_result = QueryResult(
            doc_id="test",
            content="content",
            name="name",
            path="/path",
            kb_dir="/kb"
        )

        response = QueryResponse(
            results=[query_result],
            count=1,
            cached=True,
            query="test"
        )

        data = response.model_dump()
        assert isinstance(data["results"], list)
        assert isinstance(data["results"][0], dict)
        assert data["results"][0]["doc_id"] == "test"

    def test_model_config_examples(self):
        """Test that model configs have examples."""
        models_with_examples = [
            QueryRequest,
            IngestRequest,
            BatchIngestRequest,
            WarmRequest,
            CollectionRequest,
            QueryResponse,
            IngestResponse,
            BatchIngestResponse,
            HealthResponse,
            StatsResponse,
        ]

        for model_class in models_with_examples:
            schema = model_class.model_json_schema()
            assert "example" in schema or "examples" in str(schema)
