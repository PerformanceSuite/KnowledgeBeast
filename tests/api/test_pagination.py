"""Comprehensive tests for query result pagination.

Tests cover:
- Basic pagination functionality
- Edge cases (empty results, page overflow, invalid params)
- Pagination metadata accuracy
- Backward compatibility with legacy endpoint
- Cache behavior with pagination
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from knowledgebeast.api.app import app


@pytest.fixture
def client():
    """Create FastAPI test client with authentication."""
    client = TestClient(app)
    client.headers.update({"X-API-Key": "test-api-key-12345"})
    return client


@pytest.fixture
def mock_kb():
    """Create mock KnowledgeBase instance with 10 test documents."""
    kb = Mock()

    # Create 10 mock documents (all contain "audio")
    kb.documents = {
        f"doc{i}": {
            "content": f"Document {i} - audio content",
            "name": f"Document {i}",
            "path": f"/kb/doc{i}.md",
            "kb_dir": "/kb"
        }
        for i in range(1, 11)
    }

    kb.index = {"audio": [f"doc{i}" for i in range(1, 11)]}

    # Mock cache
    kb.query_cache = Mock()
    kb.query_cache._cache = {}
    kb.query_cache.__contains__ = Mock(return_value=False)
    kb.query_cache.__len__ = Mock(return_value=0)

    # Mock _generate_cache_key
    kb._generate_cache_key = Mock(return_value="test_cache_key")

    # Mock query method to return all 10 docs for "audio"
    def mock_query(query, use_cache=True):
        if "audio" in query.lower():
            return [(doc_id, doc) for doc_id, doc in sorted(kb.documents.items())]
        elif "synthesis" in query.lower():
            return [("doc4", kb.documents["doc4"])]
        else:
            return []

    kb.query = Mock(side_effect=mock_query)

    # Mock other attributes
    kb.stats = {"queries": 0, "cache_hits": 0, "cache_misses": 0}
    kb.config = Mock()
    kb.config.heartbeat_interval = 300

    return kb


class TestBasicPagination:
    """Test basic pagination functionality."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_first_page(self, mock_get_kb, client, mock_kb):
        """Test requesting first page of results."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1, "page_size": 5}
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "results" in data
        assert "count" in data
        assert "cached" in data
        assert "query" in data
        assert "pagination" in data

        # Check results
        assert len(data["results"]) <= 5
        assert data["count"] == len(data["results"])
        assert data["query"] == "audio"

        # Check pagination metadata
        pagination = data["pagination"]
        assert pagination["current_page"] == 1
        assert pagination["page_size"] == 5
        assert pagination["total_results"] == 10  # All docs have "audio"
        assert pagination["total_pages"] == 2  # 10 results / 5 per page
        assert pagination["has_next"] is True
        assert pagination["has_previous"] is False

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_second_page(self, mock_get_kb, client, mock_kb):
        """Test requesting second page of results."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 2, "page_size": 5}
        )

        assert response.status_code == 200
        data = response.json()

        # Check results
        assert len(data["results"]) <= 5
        assert data["count"] == len(data["results"])

        # Check pagination metadata
        pagination = data["pagination"]
        assert pagination["current_page"] == 2
        assert pagination["page_size"] == 5
        assert pagination["has_next"] is False
        assert pagination["has_previous"] is True

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_default_page_size(self, mock_get_kb, client, mock_kb):
        """Test default page_size is 10."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1}  # No page_size specified
        )

        assert response.status_code == 200
        data = response.json()

        pagination = data["pagination"]
        assert pagination["page_size"] == 10

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_default_page_number(self, mock_get_kb, client, mock_kb):
        """Test default page is 1."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio"}  # No page specified
        )

        assert response.status_code == 200
        data = response.json()

        pagination = data["pagination"]
        assert pagination["current_page"] == 1


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_empty_results(self, mock_get_kb, client, mock_kb):
        """Test pagination with no matching results."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "nonexistent", "page": 1, "page_size": 10}
        )

        assert response.status_code == 200
        data = response.json()

        # Check empty results
        assert len(data["results"]) == 0
        assert data["count"] == 0

        # Check pagination metadata
        pagination = data["pagination"]
        assert pagination["total_results"] == 0
        assert pagination["total_pages"] == 1  # At least 1 page even with no results
        assert pagination["current_page"] == 1
        assert pagination["has_next"] is False
        assert pagination["has_previous"] is False

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_page_overflow(self, mock_get_kb, client, mock_kb):
        """Test requesting page beyond total pages."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 999, "page_size": 10}
        )

        # Should return 400 Bad Request for page overflow
        assert response.status_code == 400
        assert "exceeds total pages" in response.json()["detail"].lower()

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_invalid_page_zero(self, mock_get_kb, client, mock_kb):
        """Test page number must be >= 1."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 0, "page_size": 10}
        )

        # Should return 422 Unprocessable Entity for validation error
        assert response.status_code == 422

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_max_page_size_limit(self, mock_get_kb, client, mock_kb):
        """Test page_size cannot exceed 100."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1, "page_size": 101}
        )

        assert response.status_code == 422

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_max_page_size_allowed(self, mock_get_kb, client, mock_kb):
        """Test page_size of 100 is allowed."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1, "page_size": 100}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page_size"] == 100

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_single_result_pagination(self, mock_get_kb, client, mock_kb):
        """Test pagination with only one result."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "synthesis", "page": 1, "page_size": 10}
        )

        assert response.status_code == 200
        data = response.json()

        pagination = data["pagination"]
        assert pagination["total_results"] == 1
        assert pagination["total_pages"] == 1
        assert pagination["has_next"] is False
        assert pagination["has_previous"] is False


class TestPaginationMetadata:
    """Test accuracy of pagination metadata."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_total_results_calculation(self, mock_get_kb, client, mock_kb):
        """Test total_results matches actual result count."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1, "page_size": 3}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have 10 total results (all docs have "audio")
        pagination = data["pagination"]
        assert pagination["total_results"] == 10

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_total_pages_calculation(self, mock_get_kb, client, mock_kb):
        """Test total_pages is calculated correctly."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1, "page_size": 3}
        )

        assert response.status_code == 200
        data = response.json()

        # 10 results / 3 per page = 4 pages (3, 3, 3, 1)
        pagination = data["pagination"]
        assert pagination["total_pages"] == 4


class TestBackwardCompatibility:
    """Test backward compatibility with legacy query endpoint."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_legacy_endpoint_still_works(self, mock_get_kb, client, mock_kb):
        """Test legacy /query endpoint is unaffected."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query",
            json={"query": "audio", "limit": 5, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()

        # Legacy endpoint should not have pagination field
        assert "pagination" not in data
        assert "results" in data
        assert "count" in data
        assert "cached" in data
        assert "query" in data


class TestCacheBehavior:
    """Test cache behavior with pagination."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_pagination_respects_use_cache_parameter(self, mock_get_kb, client, mock_kb):
        """Test paginated queries respect use_cache parameter."""
        mock_get_kb.return_value = mock_kb

        # Request with use_cache=True
        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "audio", "page": 1, "page_size": 5, "use_cache": True}
        )

        assert response.status_code == 200
        # Query method should have been called with use_cache=True
        mock_kb.query.assert_called_with("audio", True)


class TestQuerySanitization:
    """Test query sanitization works with pagination."""

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_dangerous_characters_rejected(self, mock_get_kb, client, mock_kb):
        """Test queries with dangerous characters are rejected."""
        mock_get_kb.return_value = mock_kb

        dangerous_queries = [
            "audio; DROP TABLE",
            "audio<script>",
            "audio | rm",
        ]

        for query in dangerous_queries:
            response = client.post(
                "/api/v1/query/paginated",
                json={"query": query, "page": 1, "page_size": 10}
            )

            # Should return 422 Unprocessable Entity for invalid query
            assert response.status_code == 422

    @patch('knowledgebeast.api.routes.get_kb_instance')
    def test_empty_query_rejected(self, mock_get_kb, client, mock_kb):
        """Test empty queries are rejected."""
        mock_get_kb.return_value = mock_kb

        response = client.post(
            "/api/v1/query/paginated",
            json={"query": "", "page": 1, "page_size": 10}
        )

        assert response.status_code == 422
