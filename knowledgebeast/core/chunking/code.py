"""Code-aware chunker that preserves function and class boundaries."""

import re
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from knowledgebeast.core.chunking.base import BaseChunker, Chunk


class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class CodeAwareChunker(BaseChunker):
    """Code-aware chunker that preserves function and class boundaries.

    This chunker:
    1. Detects programming language
    2. Identifies function and class boundaries
    3. Preserves complete code units (functions, classes, methods)
    4. Handles nested structures
    5. Maintains proper indentation

    Attributes:
        max_chunk_size: Maximum chunk size in lines
        preserve_imports: Whether to include imports with chunks
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize code-aware chunker.

        Args:
            config: Configuration dictionary with:
                - max_chunk_size: int (default: 100 lines)
                - preserve_imports: bool (default: True)
        """
        super().__init__(config)
        self.max_chunk_size = self.config.get('max_chunk_size', 100)
        self.preserve_imports = self.config.get('preserve_imports', True)

        if self.max_chunk_size <= 0:
            raise ValueError("max_chunk_size must be positive")

        # Language-specific patterns
        self.language_patterns = {
            Language.PYTHON: {
                'function': r'^(\s*)(def|async def)\s+(\w+)\s*\(',
                'class': r'^(\s*)class\s+(\w+)',
                'import': r'^(from\s+\S+\s+)?import\s+',
            },
            Language.JAVASCRIPT: {
                'function': r'^(\s*)(function|const|let|var)\s+(\w+)\s*[=\(]',
                'class': r'^(\s*)class\s+(\w+)',
                'import': r'^(import|require)\s+',
            },
            Language.TYPESCRIPT: {
                'function': r'^(\s*)(function|const|let)\s+(\w+)\s*[=\(]',
                'class': r'^(\s*)(class|interface|type)\s+(\w+)',
                'import': r'^import\s+',
            },
            Language.JAVA: {
                'function': r'^\s*(public|private|protected)?\s*(static)?\s*\w+\s+(\w+)\s*\(',
                'class': r'^\s*(public|private)?\s*(class|interface|enum)\s+(\w+)',
                'import': r'^import\s+',
            },
            Language.GO: {
                'function': r'^func\s+(\w+)\s*\(',
                'class': r'^type\s+(\w+)\s+(struct|interface)',
                'import': r'^import\s+',
            }
        }

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split code into chunks preserving structure.

        Args:
            text: Code text to chunk
            metadata: Optional metadata (file_path, parent_doc_id, language, etc.)

        Returns:
            List of Chunk objects preserving code structure
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        parent_doc_id = metadata.get('parent_doc_id', 'unknown')

        # Detect language
        language = self._detect_language(text, metadata)

        # Parse code units (functions, classes)
        code_units = self._parse_code_units(text, language)

        # Extract imports if configured
        imports = self._extract_imports(text, language) if self.preserve_imports else []

        # Create chunks from code units
        chunks = self._create_chunks_from_units(
            code_units, imports, parent_doc_id, metadata, language
        )

        return chunks

    def _detect_language(self, text: str, metadata: Dict[str, Any]) -> Language:
        """Detect programming language.

        Args:
            text: Code text
            metadata: Metadata that may contain language hint

        Returns:
            Detected Language
        """
        # Check metadata first
        if 'language' in metadata:
            lang_str = metadata['language'].lower()
            for lang in Language:
                if lang.value == lang_str:
                    return lang

        # Check file extension
        if 'file_path' in metadata:
            file_path = metadata['file_path']
            if file_path.endswith('.py'):
                return Language.PYTHON
            elif file_path.endswith('.js'):
                return Language.JAVASCRIPT
            elif file_path.endswith('.ts') or file_path.endswith('.tsx'):
                return Language.TYPESCRIPT
            elif file_path.endswith('.java'):
                return Language.JAVA
            elif file_path.endswith('.go'):
                return Language.GO
            elif file_path.endswith(('.cpp', '.cc', '.h', '.hpp')):
                return Language.CPP
            elif file_path.endswith('.rs'):
                return Language.RUST

        # Heuristic detection based on syntax
        if 'def ' in text or 'import ' in text:
            return Language.PYTHON
        elif 'function ' in text or 'const ' in text:
            return Language.JAVASCRIPT
        elif 'interface ' in text or 'type ' in text:
            return Language.TYPESCRIPT

        return Language.UNKNOWN

    def _parse_code_units(self, text: str, language: Language) -> List[Dict[str, Any]]:
        """Parse code into units (functions, classes).

        Args:
            text: Code text
            language: Programming language

        Returns:
            List of code unit dictionaries
        """
        lines = text.split('\n')
        units = []

        if language not in self.language_patterns:
            # Unknown language - treat each logical block as a unit
            return self._parse_generic_code(lines)

        patterns = self.language_patterns[language]
        current_unit = None
        current_indent = None

        for i, line in enumerate(lines):
            # Check for function definition
            func_match = re.match(patterns['function'], line)
            if func_match:
                # Save previous unit
                if current_unit:
                    units.append(current_unit)

                # Start new function unit
                indent = len(func_match.group(1)) if func_match.groups() else 0
                func_name = func_match.group(3) if len(func_match.groups()) >= 3 else 'unknown'

                current_unit = {
                    'type': 'function',
                    'name': func_name,
                    'line_start': i,
                    'lines': [line],
                    'indent': indent
                }
                current_indent = indent
                continue

            # Check for class definition
            class_match = re.match(patterns['class'], line)
            if class_match:
                # Save previous unit
                if current_unit:
                    units.append(current_unit)

                # Start new class unit
                indent = len(class_match.group(1)) if class_match.groups() else 0
                class_name = class_match.group(2) if len(class_match.groups()) >= 2 else 'unknown'

                current_unit = {
                    'type': 'class',
                    'name': class_name,
                    'line_start': i,
                    'lines': [line],
                    'indent': indent
                }
                current_indent = indent
                continue

            # Add line to current unit
            if current_unit:
                # Check if still within unit (based on indentation)
                if line.strip():  # Non-empty line
                    line_indent = len(line) - len(line.lstrip())
                    if line_indent > current_indent or not line.strip():
                        current_unit['lines'].append(line)
                    else:
                        # New top-level statement - save current unit
                        units.append(current_unit)
                        current_unit = None
                        current_indent = None
                else:
                    # Empty line - include in current unit
                    current_unit['lines'].append(line)

        # Save final unit
        if current_unit:
            units.append(current_unit)

        # Add line_end to all units
        for unit in units:
            unit['line_end'] = unit['line_start'] + len(unit['lines']) - 1

        return units

    def _parse_generic_code(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse code for unknown language.

        Args:
            lines: Code lines

        Returns:
            List of code unit dictionaries
        """
        units = []
        current_unit = None

        for i, line in enumerate(lines):
            if not line.strip():
                # Empty line - could be unit boundary
                if current_unit and len(current_unit['lines']) > 0:
                    current_unit['lines'].append(line)
                continue

            if current_unit is None:
                # Start new unit
                current_unit = {
                    'type': 'code',
                    'name': f'block_{len(units)}',
                    'line_start': i,
                    'lines': [line],
                    'indent': 0
                }
            else:
                current_unit['lines'].append(line)

                # Check if unit is getting too large
                if len(current_unit['lines']) >= self.max_chunk_size:
                    current_unit['line_end'] = i
                    units.append(current_unit)
                    current_unit = None

        # Save final unit
        if current_unit:
            current_unit['line_end'] = current_unit['line_start'] + len(current_unit['lines']) - 1
            units.append(current_unit)

        return units

    def _extract_imports(self, text: str, language: Language) -> List[str]:
        """Extract import statements.

        Args:
            text: Code text
            language: Programming language

        Returns:
            List of import lines
        """
        if language not in self.language_patterns:
            return []

        pattern = self.language_patterns[language]['import']
        imports = []

        for line in text.split('\n'):
            if re.match(pattern, line):
                imports.append(line)

        return imports

    def _create_chunks_from_units(
        self,
        units: List[Dict[str, Any]],
        imports: List[str],
        parent_doc_id: str,
        metadata: Dict[str, Any],
        language: Language
    ) -> List[Chunk]:
        """Create chunks from code units.

        Args:
            units: List of code units
            imports: List of import statements
            parent_doc_id: Parent document ID
            metadata: Base metadata
            language: Programming language

        Returns:
            List of Chunk objects
        """
        chunks = []
        chunk_index = 0

        for unit in units:
            # Combine imports with unit if configured
            chunk_lines = []
            if imports and self.preserve_imports:
                chunk_lines.extend(imports)
                chunk_lines.append('')  # Blank line separator

            chunk_lines.extend(unit['lines'])
            chunk_text = '\n'.join(chunk_lines)

            chunk_id = self._generate_chunk_id(parent_doc_id, chunk_index)

            chunk = Chunk(
                chunk_id=chunk_id,
                text=chunk_text.strip(),
                metadata={
                    **metadata,
                    'chunk_index': chunk_index,
                    'chunk_type': 'code',
                    'code_unit_type': unit['type'],
                    'code_unit_name': unit['name'],
                    'line_start': unit['line_start'],
                    'line_end': unit['line_end'],
                    'language': language.value,
                    'num_lines': len(unit['lines'])
                }
            )
            chunks.append(chunk)
            chunk_index += 1

        # Update total_chunks
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)

        return chunks

    def get_stats(self) -> Dict[str, Any]:
        """Get chunker statistics.

        Returns:
            Dictionary with chunker stats
        """
        return {
            **super().get_stats(),
            'max_chunk_size': self.max_chunk_size,
            'preserve_imports': self.preserve_imports,
            'supported_languages': [lang.value for lang in self.language_patterns.keys()]
        }
