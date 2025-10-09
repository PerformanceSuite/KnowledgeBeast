"""WordNet utilities for synonym expansion and semantic enrichment.

This module provides utilities for querying WordNet to expand search terms
with synonyms, handle part-of-speech tagging, and filter contextually
relevant word relationships.
"""

import logging
from typing import List, Set, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import NLTK and WordNet
try:
    import nltk
    from nltk.corpus import wordnet as wn
    from nltk import pos_tag, word_tokenize

    NLTK_AVAILABLE = True

    # Download required NLTK data if not already present
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        logger.info("Downloading WordNet corpus...")
        nltk.download('wordnet', quiet=True)

    try:
        nltk.data.find('corpora/omw-1.4')
    except LookupError:
        logger.info("Downloading Open Multilingual Wordnet...")
        nltk.download('omw-1.4', quiet=True)

    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        logger.info("Downloading POS tagger...")
        nltk.download('averaged_perceptron_tagger', quiet=True)

    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        logger.info("Downloading punkt tokenizer...")
        nltk.download('punkt', quiet=True)

except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available. Synonym expansion will be disabled.")


# POS tag mapping from Penn Treebank to WordNet
POS_TAG_MAP = {
    'NN': wn.NOUN if NLTK_AVAILABLE else None,
    'NNS': wn.NOUN if NLTK_AVAILABLE else None,
    'NNP': wn.NOUN if NLTK_AVAILABLE else None,
    'NNPS': wn.NOUN if NLTK_AVAILABLE else None,
    'VB': wn.VERB if NLTK_AVAILABLE else None,
    'VBD': wn.VERB if NLTK_AVAILABLE else None,
    'VBG': wn.VERB if NLTK_AVAILABLE else None,
    'VBN': wn.VERB if NLTK_AVAILABLE else None,
    'VBP': wn.VERB if NLTK_AVAILABLE else None,
    'VBZ': wn.VERB if NLTK_AVAILABLE else None,
    'JJ': wn.ADJ if NLTK_AVAILABLE else None,
    'JJR': wn.ADJ if NLTK_AVAILABLE else None,
    'JJS': wn.ADJ if NLTK_AVAILABLE else None,
    'RB': wn.ADV if NLTK_AVAILABLE else None,
    'RBR': wn.ADV if NLTK_AVAILABLE else None,
    'RBS': wn.ADV if NLTK_AVAILABLE else None,
}


def is_available() -> bool:
    """Check if WordNet is available.

    Returns:
        True if NLTK and WordNet are available, False otherwise
    """
    return NLTK_AVAILABLE


def get_wordnet_pos(treebank_tag: str) -> Optional[str]:
    """Convert Penn Treebank POS tag to WordNet POS tag.

    Args:
        treebank_tag: Penn Treebank POS tag (e.g., 'NN', 'VBD')

    Returns:
        WordNet POS tag ('n', 'v', 'a', 'r') or None if no mapping
    """
    if not NLTK_AVAILABLE:
        return None

    return POS_TAG_MAP.get(treebank_tag, None)


@lru_cache(maxsize=1000)
def get_synonyms(word: str, pos: Optional[str] = None, max_synonyms: int = 5) -> List[str]:
    """Get synonyms for a word from WordNet.

    This function uses LRU caching to improve performance for repeated queries.

    Args:
        word: Word to find synonyms for
        pos: Part of speech (WordNet format: 'n', 'v', 'a', 'r'). If None, search all POS.
        max_synonyms: Maximum number of synonyms to return

    Returns:
        List of synonym strings (excluding the original word)
        Returns empty list if WordNet is not available or word not found
    """
    if not NLTK_AVAILABLE:
        return []

    word = word.lower()
    synonyms: Set[str] = set()

    # Get synsets for the word
    synsets = wn.synsets(word, pos=pos) if pos else wn.synsets(word)

    for synset in synsets[:3]:  # Limit to first 3 synsets for relevance
        # Get lemmas (word forms) from synset
        for lemma in synset.lemmas():
            synonym = lemma.name().lower().replace('_', ' ')

            # Exclude the original word and ensure it's different
            if synonym != word and len(synonyms) < max_synonyms:
                synonyms.add(synonym)

    return sorted(list(synonyms))[:max_synonyms]


@lru_cache(maxsize=1000)
def get_hypernyms(word: str, pos: Optional[str] = None, max_hypernyms: int = 3) -> List[str]:
    """Get hypernyms (broader terms) for a word from WordNet.

    Example: dog -> animal, canine

    Args:
        word: Word to find hypernyms for
        pos: Part of speech (WordNet format)
        max_hypernyms: Maximum number of hypernyms to return

    Returns:
        List of hypernym strings
    """
    if not NLTK_AVAILABLE:
        return []

    word = word.lower()
    hypernyms: Set[str] = set()

    synsets = wn.synsets(word, pos=pos) if pos else wn.synsets(word)

    for synset in synsets[:2]:  # Limit synsets
        for hypernym_synset in synset.hypernyms()[:2]:  # Limit hypernyms per synset
            for lemma in hypernym_synset.lemmas():
                hypernym = lemma.name().lower().replace('_', ' ')
                if hypernym != word and len(hypernyms) < max_hypernyms:
                    hypernyms.add(hypernym)

    return sorted(list(hypernyms))[:max_hypernyms]


@lru_cache(maxsize=1000)
def get_hyponyms(word: str, pos: Optional[str] = None, max_hyponyms: int = 3) -> List[str]:
    """Get hyponyms (more specific terms) for a word from WordNet.

    Example: animal -> dog, cat

    Args:
        word: Word to find hyponyms for
        pos: Part of speech (WordNet format)
        max_hyponyms: Maximum number of hyponyms to return

    Returns:
        List of hyponym strings
    """
    if not NLTK_AVAILABLE:
        return []

    word = word.lower()
    hyponyms: Set[str] = set()

    synsets = wn.synsets(word, pos=pos) if pos else wn.synsets(word)

    for synset in synsets[:2]:
        for hyponym_synset in synset.hyponyms()[:2]:
            for lemma in hyponym_synset.lemmas():
                hyponym = lemma.name().lower().replace('_', ' ')
                if hyponym != word and len(hyponyms) < max_hyponyms:
                    hyponyms.add(hyponym)

    return sorted(list(hyponyms))[:max_hyponyms]


def get_pos_tags(text: str) -> List[Tuple[str, str]]:
    """Get part-of-speech tags for words in text.

    Args:
        text: Text to analyze

    Returns:
        List of (word, pos_tag) tuples
        Returns empty list if NLTK not available
    """
    if not NLTK_AVAILABLE:
        return []

    try:
        tokens = word_tokenize(text)
        return pos_tag(tokens)
    except Exception as e:
        logger.warning(f"Error getting POS tags: {e}")
        return []


def expand_with_synonyms(
    words: List[str],
    max_expansions_per_word: int = 3,
    use_pos_tagging: bool = True
) -> List[str]:
    """Expand a list of words with their synonyms.

    Args:
        words: List of words to expand
        max_expansions_per_word: Maximum number of synonyms per word
        use_pos_tagging: Use POS tagging for better synonym matching

    Returns:
        List of expanded words (original + synonyms)
    """
    if not NLTK_AVAILABLE:
        return words

    expanded = list(words)  # Start with original words

    # Get POS tags if requested
    pos_tags = {}
    if use_pos_tagging:
        text = ' '.join(words)
        tagged = get_pos_tags(text)
        pos_tags = {word.lower(): get_wordnet_pos(tag) for word, tag in tagged}

    # Expand each word with synonyms
    for word in words:
        word_lower = word.lower()
        pos = pos_tags.get(word_lower) if use_pos_tagging else None

        synonyms = get_synonyms(word_lower, pos=pos, max_synonyms=max_expansions_per_word)
        expanded.extend(synonyms)

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for word in expanded:
        if word.lower() not in seen:
            seen.add(word.lower())
            result.append(word)

    return result


def get_word_similarity(word1: str, word2: str) -> float:
    """Calculate semantic similarity between two words using WordNet.

    Uses path similarity between synsets.

    Args:
        word1: First word
        word2: Second word

    Returns:
        Similarity score between 0 (unrelated) and 1 (identical)
        Returns 0.0 if WordNet not available
    """
    if not NLTK_AVAILABLE:
        return 0.0

    word1 = word1.lower()
    word2 = word2.lower()

    if word1 == word2:
        return 1.0

    # Get synsets for both words
    synsets1 = wn.synsets(word1)
    synsets2 = wn.synsets(word2)

    if not synsets1 or not synsets2:
        return 0.0

    # Calculate max similarity across all synset pairs
    max_similarity = 0.0
    for s1 in synsets1[:3]:  # Limit to first 3 synsets
        for s2 in synsets2[:3]:
            similarity = s1.path_similarity(s2)
            if similarity and similarity > max_similarity:
                max_similarity = similarity

    return max_similarity


def clear_cache() -> None:
    """Clear the LRU cache for all cached functions.

    Useful for testing or memory management.
    """
    get_synonyms.cache_clear()
    get_hypernyms.cache_clear()
    get_hyponyms.cache_clear()
