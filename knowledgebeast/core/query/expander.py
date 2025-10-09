"""Query Expansion - Improve recall through synonym and acronym expansion.

This module provides query expansion capabilities to improve search recall by:
1. Synonym expansion using WordNet
2. Acronym expansion (ML -> Machine Learning)
3. Configurable max expansions
4. User feedback loop for expansions
"""

import logging
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field

from knowledgebeast.utils import wordnet_utils

logger = logging.getLogger(__name__)


# Common acronym mappings for technical domains
DEFAULT_ACRONYM_MAP = {
    'ml': 'machine learning',
    'ai': 'artificial intelligence',
    'nlp': 'natural language processing',
    'api': 'application programming interface',
    'ui': 'user interface',
    'ux': 'user experience',
    'db': 'database',
    'sql': 'structured query language',
    'nosql': 'not only sql',
    'rest': 'representational state transfer',
    'http': 'hypertext transfer protocol',
    'https': 'hypertext transfer protocol secure',
    'url': 'uniform resource locator',
    'uri': 'uniform resource identifier',
    'json': 'javascript object notation',
    'xml': 'extensible markup language',
    'html': 'hypertext markup language',
    'css': 'cascading style sheets',
    'js': 'javascript',
    'ts': 'typescript',
    'cpu': 'central processing unit',
    'gpu': 'graphics processing unit',
    'ram': 'random access memory',
    'ssd': 'solid state drive',
    'hdd': 'hard disk drive',
    'io': 'input output',
    'cli': 'command line interface',
    'gui': 'graphical user interface',
    'os': 'operating system',
    'vm': 'virtual machine',
    'ci': 'continuous integration',
    'cd': 'continuous deployment',
    'cicd': 'continuous integration continuous deployment',
    'devops': 'development operations',
    'qa': 'quality assurance',
    'tdd': 'test driven development',
    'bdd': 'behavior driven development',
    'orm': 'object relational mapping',
    'mvc': 'model view controller',
    'mvvm': 'model view viewmodel',
    'crud': 'create read update delete',
    'rasp': 'runtime application self protection',
    'sast': 'static application security testing',
    'dast': 'dynamic application security testing',
    'jwt': 'json web token',
    'oauth': 'open authorization',
    'saml': 'security assertion markup language',
    'ssl': 'secure sockets layer',
    'tls': 'transport layer security',
    'vpn': 'virtual private network',
    'dns': 'domain name system',
    'dhcp': 'dynamic host configuration protocol',
    'tcp': 'transmission control protocol',
    'udp': 'user datagram protocol',
    'ip': 'internet protocol',
    'fft': 'fast fourier transform',
    'dsp': 'digital signal processing',
    'daw': 'digital audio workstation',
    'midi': 'musical instrument digital interface',
    'vst': 'virtual studio technology',
    'lfo': 'low frequency oscillator',
    'adsr': 'attack decay sustain release',
    'eq': 'equalizer',
    'daw': 'digital audio workstation',
}


@dataclass
class ExpansionResult:
    """Result of query expansion.

    Attributes:
        original_query: Original query string
        expanded_query: Expanded query with synonyms/acronyms
        expansion_terms: List of added expansion terms
        synonym_expansions: Map of term -> synonyms
        acronym_expansions: Map of acronym -> expansion
        total_expansions: Total number of expansions added
    """
    original_query: str
    expanded_query: str
    expansion_terms: List[str] = field(default_factory=list)
    synonym_expansions: Dict[str, List[str]] = field(default_factory=dict)
    acronym_expansions: Dict[str, str] = field(default_factory=dict)
    total_expansions: int = 0


class QueryExpander:
    """Query expansion engine for improving search recall.

    This class expands queries with synonyms and acronyms to improve recall
    by matching on semantically similar terms beyond exact keyword matches.

    Features:
        - Synonym expansion using WordNet
        - Acronym expansion with configurable dictionary
        - Configurable max expansions per term
        - User feedback loop for learning
        - Thread-safe operation (stateless expansion)

    Thread Safety:
        - Expansion operations are stateless
        - WordNet utilities use LRU cache (thread-safe)
        - Acronym map is read-only after initialization

    Attributes:
        enabled: Enable query expansion
        use_synonyms: Enable synonym expansion
        use_acronyms: Enable acronym expansion
        max_expansions: Maximum expansions per term
        acronym_map: Mapping of acronyms to expansions
    """

    def __init__(
        self,
        enabled: bool = True,
        use_synonyms: bool = True,
        use_acronyms: bool = True,
        max_expansions: int = 3,
        custom_acronyms: Optional[Dict[str, str]] = None
    ):
        """Initialize query expander.

        Args:
            enabled: Enable query expansion
            use_synonyms: Enable synonym expansion via WordNet
            use_acronyms: Enable acronym expansion
            max_expansions: Maximum number of expansions per term
            custom_acronyms: Custom acronym mappings (merged with defaults)

        Raises:
            ValueError: If max_expansions < 0
        """
        if max_expansions < 0:
            raise ValueError("max_expansions must be non-negative")

        self.enabled = enabled
        self.use_synonyms = use_synonyms
        self.use_acronyms = use_acronyms
        self.max_expansions = max_expansions

        # Merge custom acronyms with defaults
        self.acronym_map = dict(DEFAULT_ACRONYM_MAP)
        if custom_acronyms:
            self.acronym_map.update(custom_acronyms)

        # Check WordNet availability
        if use_synonyms and not wordnet_utils.is_available():
            logger.warning("WordNet not available. Synonym expansion will be disabled.")
            self.use_synonyms = False

        logger.info(f"QueryExpander initialized: synonyms={self.use_synonyms}, "
                   f"acronyms={self.use_acronyms}, max_expansions={self.max_expansions}")

    def expand(self, query: str) -> ExpansionResult:
        """Expand query with synonyms and acronyms.

        This is the main entry point for query expansion.

        Args:
            query: Original query string

        Returns:
            ExpansionResult with expanded query and metadata
        """
        if not self.enabled or not query.strip():
            return ExpansionResult(
                original_query=query,
                expanded_query=query,
                expansion_terms=[],
                total_expansions=0
            )

        # Parse query into terms
        terms = self._parse_query(query)

        # Track expansions
        all_expansion_terms: Set[str] = set()
        synonym_map: Dict[str, List[str]] = {}
        acronym_map: Dict[str, str] = {}

        # Expand acronyms
        if self.use_acronyms:
            for term in terms:
                expansion = self._expand_acronym(term)
                if expansion:
                    acronym_map[term] = expansion
                    # Add expansion terms
                    expansion_words = expansion.split()
                    all_expansion_terms.update(expansion_words)

        # Expand with synonyms
        if self.use_synonyms:
            for term in terms:
                # Skip very short terms (likely stopwords or acronyms)
                if len(term) <= 2:
                    continue

                synonyms = wordnet_utils.get_synonyms(
                    term,
                    max_synonyms=self.max_expansions
                )

                if synonyms:
                    synonym_map[term] = synonyms
                    all_expansion_terms.update(synonyms)

        # Build expanded query
        expanded_terms = list(terms) + list(all_expansion_terms)
        expanded_query = ' '.join(expanded_terms)

        return ExpansionResult(
            original_query=query,
            expanded_query=expanded_query,
            expansion_terms=list(all_expansion_terms),
            synonym_expansions=synonym_map,
            acronym_expansions=acronym_map,
            total_expansions=len(all_expansion_terms)
        )

    def expand_to_or_query(self, query: str) -> str:
        """Expand query and format as OR query.

        Example: "ML best practices" -> "ML best practices OR machine learning best practices"

        Args:
            query: Original query string

        Returns:
            OR-formatted expanded query
        """
        result = self.expand(query)

        if not result.expansion_terms:
            return query

        # Format as OR query
        return f"{query} OR {' '.join(result.expansion_terms)}"

    def _parse_query(self, query: str) -> List[str]:
        """Parse query string into terms.

        Args:
            query: Query string

        Returns:
            List of normalized terms
        """
        # Simple whitespace tokenization with lowercase normalization
        # Remove punctuation except hyphens (for compound words)
        cleaned = re.sub(r'[^\w\s-]', ' ', query)
        return cleaned.lower().split()

    def _expand_acronym(self, term: str) -> Optional[str]:
        """Expand acronym if found in acronym map.

        Args:
            term: Term to check for acronym expansion

        Returns:
            Expansion string if found, None otherwise
        """
        term_lower = term.lower()

        # Check exact match in acronym map
        if term_lower in self.acronym_map:
            return self.acronym_map[term_lower]

        # Check if it's all uppercase (likely acronym)
        if term.isupper() and len(term) >= 2:
            expansion = self.acronym_map.get(term_lower)
            if expansion:
                return expansion

        return None

    def add_acronym(self, acronym: str, expansion: str) -> None:
        """Add custom acronym mapping.

        This allows for user feedback and learning.

        Args:
            acronym: Acronym to add
            expansion: Full expansion of acronym
        """
        self.acronym_map[acronym.lower()] = expansion.lower()
        logger.info(f"Added acronym mapping: {acronym} -> {expansion}")

    def remove_acronym(self, acronym: str) -> bool:
        """Remove acronym mapping.

        Args:
            acronym: Acronym to remove

        Returns:
            True if removed, False if not found
        """
        acronym_lower = acronym.lower()
        if acronym_lower in self.acronym_map:
            del self.acronym_map[acronym_lower]
            logger.info(f"Removed acronym mapping: {acronym}")
            return True
        return False

    def get_stats(self) -> Dict:
        """Get expander statistics.

        Returns:
            Dictionary with expander stats
        """
        return {
            'enabled': self.enabled,
            'use_synonyms': self.use_synonyms,
            'use_acronyms': self.use_acronyms,
            'max_expansions': self.max_expansions,
            'acronym_count': len(self.acronym_map),
            'wordnet_available': wordnet_utils.is_available(),
        }

    def preview_expansion(self, query: str) -> Dict:
        """Preview expansion for debugging/UI display.

        Args:
            query: Query to preview expansion for

        Returns:
            Dictionary with expansion preview details
        """
        result = self.expand(query)

        return {
            'original': result.original_query,
            'expanded': result.expanded_query,
            'total_expansions': result.total_expansions,
            'synonym_expansions': result.synonym_expansions,
            'acronym_expansions': result.acronym_expansions,
            'expansion_terms': result.expansion_terms,
        }
