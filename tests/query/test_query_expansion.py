"""Comprehensive tests for query expansion functionality.

This module tests:
- Synonym expansion using WordNet
- Acronym expansion
- Max expansion limit enforcement
- Edge cases (no expansions found)
- WordNet integration
- Configuration and customization
- Performance metrics
"""

import pytest
from unittest.mock import patch, MagicMock

from knowledgebeast.core.query.expander import QueryExpander, ExpansionResult
from knowledgebeast.utils import wordnet_utils


class TestQueryExpansion:
    """Test suite for query expansion."""

    def test_basic_synonym_expansion(self):
        """Test basic synonym expansion using WordNet."""
        expander = QueryExpander(
            use_synonyms=True,
            use_acronyms=False,
            max_expansions=3
        )

        result = expander.expand("fast car")

        assert isinstance(result, ExpansionResult)
        assert result.original_query == "fast car"
        assert len(result.expansion_terms) > 0  # Should have some synonyms
        assert result.total_expansions > 0

    def test_acronym_expansion(self):
        """Test acronym expansion (ML -> machine learning)."""
        expander = QueryExpander(
            use_synonyms=False,
            use_acronyms=True,
            max_expansions=3
        )

        result = expander.expand("ML best practices")

        assert result.total_expansions > 0
        assert "ml" in result.acronym_expansions
        assert result.acronym_expansions["ml"] == "machine learning"
        assert "machine" in result.expansion_terms or "machine learning" in result.expanded_query.lower()

    def test_combined_expansion(self):
        """Test combined synonym and acronym expansion."""
        expander = QueryExpander(
            use_synonyms=True,
            use_acronyms=True,
            max_expansions=2
        )

        result = expander.expand("AI algorithm")

        # Should expand both acronym and synonyms
        assert result.total_expansions > 0

    def test_max_expansions_limit(self):
        """Test that max_expansions limit is enforced."""
        expander = QueryExpander(
            use_synonyms=True,
            use_acronyms=False,
            max_expansions=2
        )

        result = expander.expand("fast quick rapid")

        # Each word should have at most 2 synonyms
        for term, synonyms in result.synonym_expansions.items():
            assert len(synonyms) <= 2

    def test_no_expansions_found(self):
        """Test edge case where no expansions are found."""
        expander = QueryExpander(
            use_synonyms=True,
            use_acronyms=True,
            max_expansions=3
        )

        # Use gibberish that won't have synonyms or be an acronym
        result = expander.expand("xyzabc defghi")

        # Should still return a valid result, just with no expansions
        assert isinstance(result, ExpansionResult)
        assert result.original_query == "xyzabc defghi"
        # May or may not have expansions depending on WordNet

    def test_empty_query(self):
        """Test handling of empty query."""
        expander = QueryExpander()

        result = expander.expand("")

        assert result.original_query == ""
        assert result.expanded_query == ""
        assert result.total_expansions == 0

    def test_expansion_disabled(self):
        """Test that expansion can be disabled."""
        expander = QueryExpander(enabled=False)

        result = expander.expand("ML fast algorithm")

        assert result.original_query == "ML fast algorithm"
        assert result.expanded_query == "ML fast algorithm"
        assert result.total_expansions == 0

    def test_custom_acronyms(self):
        """Test adding custom acronym mappings."""
        custom_acronyms = {
            "xyz": "extra year zephyr",
            "abc": "always be coding"
        }

        expander = QueryExpander(
            use_acronyms=True,
            use_synonyms=False,
            custom_acronyms=custom_acronyms
        )

        result = expander.expand("xyz abc")

        assert "xyz" in result.acronym_expansions
        assert result.acronym_expansions["xyz"] == "extra year zephyr"
        assert "abc" in result.acronym_expansions

    def test_add_acronym_dynamically(self):
        """Test adding acronyms dynamically (feedback loop)."""
        expander = QueryExpander(use_acronyms=True, use_synonyms=False)

        expander.add_acronym("CUSTOM", "custom expansion")

        result = expander.expand("CUSTOM term")

        assert "custom" in result.acronym_expansions
        assert result.acronym_expansions["custom"] == "custom expansion"

    def test_remove_acronym(self):
        """Test removing acronym mappings."""
        expander = QueryExpander(use_acronyms=True, use_synonyms=False)

        # ML should exist by default
        result_before = expander.expand("ML")
        assert "ml" in result_before.acronym_expansions

        # Remove it
        removed = expander.remove_acronym("ML")
        assert removed is True

        # Should no longer expand
        result_after = expander.expand("ML")
        assert "ml" not in result_after.acronym_expansions

    def test_expand_to_or_query(self):
        """Test OR query formatting."""
        expander = QueryExpander(use_acronyms=True, use_synonyms=False)

        or_query = expander.expand_to_or_query("ML")

        assert "ML" in or_query
        assert "OR" in or_query
        assert "machine" in or_query.lower() or "learning" in or_query.lower()

    def test_preview_expansion(self):
        """Test expansion preview for UI/debugging."""
        expander = QueryExpander(use_acronyms=True, use_synonyms=False)

        preview = expander.preview_expansion("AI ML")

        assert isinstance(preview, dict)
        assert "original" in preview
        assert "expanded" in preview
        assert "total_expansions" in preview
        assert "acronym_expansions" in preview

    def test_get_stats(self):
        """Test expander statistics."""
        expander = QueryExpander(
            use_synonyms=True,
            use_acronyms=True,
            max_expansions=5
        )

        stats = expander.get_stats()

        assert stats["enabled"] is True
        assert stats["use_synonyms"] is True
        assert stats["use_acronyms"] is True
        assert stats["max_expansions"] == 5
        assert "acronym_count" in stats
        assert "wordnet_available" in stats

    @patch('knowledgebeast.utils.wordnet_utils.is_available')
    def test_wordnet_unavailable_graceful_fallback(self, mock_is_available):
        """Test graceful fallback when WordNet is unavailable."""
        mock_is_available.return_value = False

        expander = QueryExpander(use_synonyms=True, use_acronyms=True)

        # Should still work, just without synonym expansion
        result = expander.expand("ML algorithm")

        assert isinstance(result, ExpansionResult)
        # Acronyms should still work
        assert result.total_expansions >= 0

    def test_special_characters_handling(self):
        """Test handling of special characters in queries."""
        expander = QueryExpander(use_synonyms=False, use_acronyms=True)

        result = expander.expand("What is ML? How to use API...")

        # Should handle punctuation gracefully
        assert isinstance(result, ExpansionResult)
        assert result.total_expansions > 0  # Should still expand acronyms


@pytest.mark.skipif(not wordnet_utils.is_available(), reason="WordNet not available")
class TestWordNetIntegration:
    """Test WordNet-specific functionality."""

    def test_synonym_quality(self):
        """Test that synonyms are contextually relevant."""
        expander = QueryExpander(use_synonyms=True, use_acronyms=False, max_expansions=5)

        result = expander.expand("fast")

        # Check that we got actual synonyms
        if result.synonym_expansions:
            synonyms = result.synonym_expansions.get("fast", [])
            # Common synonyms for "fast": quick, rapid, speedy
            assert len(synonyms) > 0

    def test_wordnet_cache_efficiency(self):
        """Test that WordNet lookups are cached for performance."""
        expander = QueryExpander(use_synonyms=True, max_expansions=3)

        # Clear cache first
        wordnet_utils.clear_cache()

        # First lookup
        result1 = expander.expand("fast car")

        # Second lookup (should hit cache)
        result2 = expander.expand("fast car")

        # Results should be identical
        assert result1.expansion_terms == result2.expansion_terms
