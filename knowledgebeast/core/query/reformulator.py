"""Query Reformulation - Transform queries for better retrieval.

This module provides query reformulation capabilities to improve search by:
1. Question to keyword transformation
2. Negation handling ("not about X")
3. Date range extraction
4. Entity recognition (NER) with spaCy (optional)
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import spaCy for NER
try:
    import spacy
    SPACY_AVAILABLE = True

    # Try to load a small English model
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logger.warning("spaCy model 'en_core_web_sm' not found. NER will be limited.")
        nlp = None
        SPACY_AVAILABLE = False

except ImportError:
    SPACY_AVAILABLE = False
    nlp = None
    logger.info("spaCy not installed. Advanced NER features will be disabled.")


# Question word patterns
QUESTION_WORDS = {
    'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whose',
    'can', 'could', 'should', 'would', 'will', 'is', 'are', 'do', 'does', 'did'
}

# Stopwords to remove during keyword extraction
STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
    'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
    'to', 'was', 'will', 'with', 'i', 'me', 'my', 'you', 'your'
}

# Negation patterns
NEGATION_PATTERNS = [
    r'\bnot\s+about\s+(\w+)',
    r'\bexcept\s+(\w+)',
    r'\bexclude\s+(\w+)',
    r'\bexcluding\s+(\w+)',
    r'\bwithout\s+(\w+)',
]

# Date patterns (simplified)
DATE_PATTERNS = [
    r'\b(\d{4})\b',  # Year: 2024
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b',
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})\b',
    r'\b(last|past)\s+(year|month|week|day)\b',
    r'\b(this|current)\s+(year|month|week)\b',
]


@dataclass
class ReformulationResult:
    """Result of query reformulation.

    Attributes:
        original_query: Original query string
        reformulated_query: Reformulated query
        keywords: Extracted keywords
        entities: Named entities (if NER available)
        negations: Negated terms
        date_ranges: Extracted date information
        is_question: Whether query is a question
        question_type: Type of question (what, how, etc.)
    """
    original_query: str
    reformulated_query: str
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, List[str]] = field(default_factory=dict)
    negations: List[str] = field(default_factory=list)
    date_ranges: List[str] = field(default_factory=list)
    is_question: bool = False
    question_type: Optional[str] = None


class QueryReformulator:
    """Query reformulation engine for improving search effectiveness.

    This class transforms natural language queries into more effective search
    queries by extracting keywords, handling negations, and recognizing entities.

    Features:
        - Question to keyword transformation
        - Negation detection and handling
        - Date range extraction
        - Named Entity Recognition (if spaCy available)
        - Stopword removal
        - Thread-safe operation (stateless reformulation)

    Thread Safety:
        - Reformulation operations are stateless
        - spaCy model is thread-safe (read-only)
        - No shared mutable state

    Attributes:
        use_ner: Enable Named Entity Recognition
        remove_stopwords: Remove stopwords during reformulation
        extract_dates: Extract date information
    """

    def __init__(
        self,
        use_ner: bool = True,
        remove_stopwords: bool = True,
        extract_dates: bool = True
    ):
        """Initialize query reformulator.

        Args:
            use_ner: Enable Named Entity Recognition (requires spaCy)
            remove_stopwords: Remove stopwords during keyword extraction
            extract_dates: Extract date information from queries
        """
        self.use_ner = use_ner and SPACY_AVAILABLE
        self.remove_stopwords = remove_stopwords
        self.extract_dates = extract_dates

        if use_ner and not SPACY_AVAILABLE:
            logger.warning("spaCy not available. NER features will be disabled.")

        logger.info(f"QueryReformulator initialized: NER={self.use_ner}, "
                   f"stopwords={self.remove_stopwords}, dates={self.extract_dates}")

    def reformulate(self, query: str) -> ReformulationResult:
        """Reformulate query for better retrieval.

        This is the main entry point for query reformulation.

        Args:
            query: Original query string

        Returns:
            ReformulationResult with reformulated query and metadata
        """
        if not query.strip():
            return ReformulationResult(
                original_query=query,
                reformulated_query=query,
                keywords=[]
            )

        # Check if it's a question
        is_question, question_type = self._detect_question(query)

        # Extract negations
        negations = self._extract_negations(query)

        # Extract dates
        date_ranges = []
        if self.extract_dates:
            date_ranges = self._extract_dates(query)

        # Extract entities (if NER enabled)
        entities = {}
        if self.use_ner and nlp:
            entities = self._extract_entities(query)

        # Transform question to keywords
        if is_question:
            keywords = self._question_to_keywords(query)
        else:
            keywords = self._extract_keywords(query)

        # Remove negated terms from keywords
        keywords = [kw for kw in keywords if kw not in negations]

        # Build reformulated query
        reformulated = ' '.join(keywords)

        return ReformulationResult(
            original_query=query,
            reformulated_query=reformulated,
            keywords=keywords,
            entities=entities,
            negations=negations,
            date_ranges=date_ranges,
            is_question=is_question,
            question_type=question_type
        )

    def _detect_question(self, query: str) -> Tuple[bool, Optional[str]]:
        """Detect if query is a question and determine type.

        Args:
            query: Query string

        Returns:
            Tuple of (is_question, question_type)
        """
        query_lower = query.lower().strip()

        # Check for question mark
        if query.endswith('?'):
            # Determine question type
            first_word = query_lower.split()[0] if query_lower else None
            if first_word in QUESTION_WORDS:
                return True, first_word
            return True, None

        # Check for question words at start
        first_word = query_lower.split()[0] if query_lower else None
        if first_word in QUESTION_WORDS:
            return True, first_word

        return False, None

    def _question_to_keywords(self, query: str) -> List[str]:
        """Transform question to keywords.

        Args:
            query: Question string

        Returns:
            List of keywords
        """
        # Remove question mark
        query_clean = query.rstrip('?')

        # Split into words
        words = re.findall(r'\b\w+\b', query_clean.lower())

        # Remove question words and stopwords
        keywords = []
        for word in words:
            if word not in QUESTION_WORDS and (not self.remove_stopwords or word not in STOPWORDS):
                keywords.append(word)

        return keywords

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query.

        Args:
            query: Query string

        Returns:
            List of keywords
        """
        # Split into words
        words = re.findall(r'\b\w+\b', query.lower())

        # Remove stopwords if enabled
        if self.remove_stopwords:
            keywords = [w for w in words if w not in STOPWORDS]
        else:
            keywords = words

        return keywords

    def _extract_negations(self, query: str) -> List[str]:
        """Extract negated terms from query.

        Args:
            query: Query string

        Returns:
            List of negated terms
        """
        negations = []

        for pattern in NEGATION_PATTERNS:
            matches = re.findall(pattern, query.lower())
            negations.extend(matches)

        return negations

    def _extract_dates(self, query: str) -> List[str]:
        """Extract date information from query.

        Args:
            query: Query string

        Returns:
            List of date strings/ranges
        """
        dates = []

        for pattern in DATE_PATTERNS:
            matches = re.findall(pattern, query.lower())
            for match in matches:
                if isinstance(match, tuple):
                    dates.append(' '.join(match))
                else:
                    dates.append(match)

        return dates

    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract named entities from query using spaCy.

        Args:
            query: Query string

        Returns:
            Dictionary mapping entity type to list of entities
        """
        if not nlp:
            return {}

        try:
            doc = nlp(query)

            entities: Dict[str, List[str]] = {}
            for ent in doc.ents:
                entity_type = ent.label_
                entity_text = ent.text

                if entity_type not in entities:
                    entities[entity_type] = []

                entities[entity_type].append(entity_text)

            return entities

        except Exception as e:
            logger.warning(f"Error extracting entities: {e}")
            return {}

    def is_available(self) -> bool:
        """Check if NER is available.

        Returns:
            True if spaCy and model are available, False otherwise
        """
        return SPACY_AVAILABLE and nlp is not None

    def get_stats(self) -> Dict:
        """Get reformulator statistics.

        Returns:
            Dictionary with reformulator stats
        """
        return {
            'use_ner': self.use_ner,
            'remove_stopwords': self.remove_stopwords,
            'extract_dates': self.extract_dates,
            'spacy_available': SPACY_AVAILABLE,
            'ner_available': self.use_ner and nlp is not None,
        }

    def preview_reformulation(self, query: str) -> Dict:
        """Preview reformulation for debugging/UI display.

        Args:
            query: Query to preview reformulation for

        Returns:
            Dictionary with reformulation preview details
        """
        result = self.reformulate(query)

        return {
            'original': result.original_query,
            'reformulated': result.reformulated_query,
            'keywords': result.keywords,
            'entities': result.entities,
            'negations': result.negations,
            'date_ranges': result.date_ranges,
            'is_question': result.is_question,
            'question_type': result.question_type,
        }
