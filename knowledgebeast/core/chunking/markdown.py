"""Markdown-aware chunker that preserves document structure."""

import re
from typing import List, Dict, Any, Optional, Tuple

from knowledgebeast.core.chunking.base import BaseChunker, Chunk


class MarkdownAwareChunker(BaseChunker):
    """Markdown-aware chunker that preserves headers, lists, and code blocks.

    This chunker:
    1. Preserves markdown structure (headers, lists, code blocks, tables)
    2. Maintains document hierarchy
    3. Keeps related content together (list items, code blocks)
    4. Adds structural metadata to chunks

    Attributes:
        max_chunk_size: Maximum chunk size in characters
        preserve_headers: Whether to include parent headers in chunks
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize markdown-aware chunker.

        Args:
            config: Configuration dictionary with:
                - max_chunk_size: int (default: 2000)
                - preserve_headers: bool (default: True)
        """
        super().__init__(config)
        self.max_chunk_size = self.config.get('max_chunk_size', 2000)
        self.preserve_headers = self.config.get('preserve_headers', True)

        if self.max_chunk_size <= 0:
            raise ValueError("max_chunk_size must be positive")

    def chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split markdown text into structure-aware chunks.

        Args:
            text: Markdown text to chunk
            metadata: Optional metadata (file_path, parent_doc_id, etc.)

        Returns:
            List of Chunk objects preserving markdown structure
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        parent_doc_id = metadata.get('parent_doc_id', 'unknown')

        # Parse markdown structure
        sections = self._parse_markdown_sections(text)

        # Create chunks from sections
        chunks = self._create_chunks_from_sections(
            sections, parent_doc_id, metadata
        )

        return chunks

    def _parse_markdown_sections(self, text: str) -> List[Dict[str, Any]]:
        """Parse markdown into hierarchical sections.

        Args:
            text: Markdown text

        Returns:
            List of section dictionaries with structure info
        """
        sections = []
        lines = text.split('\n')
        current_section = None
        header_stack = []  # Track header hierarchy
        in_code_block = False
        code_block_lines = []
        list_lines = []
        in_list = False

        for i, line in enumerate(lines):
            # Handle code blocks
            if line.strip().startswith('```'):
                if not in_code_block:
                    # Start code block
                    in_code_block = True
                    code_block_lines = [line]
                else:
                    # End code block
                    code_block_lines.append(line)
                    sections.append({
                        'type': 'code',
                        'content': '\n'.join(code_block_lines),
                        'line_start': i - len(code_block_lines) + 1,
                        'line_end': i,
                        'headers': list(header_stack),
                        'language': self._extract_code_language(code_block_lines[0])
                    })
                    in_code_block = False
                    code_block_lines = []
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Handle headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # Save current list if any
                if in_list and list_lines:
                    sections.append({
                        'type': 'list',
                        'content': '\n'.join(list_lines),
                        'line_start': i - len(list_lines),
                        'line_end': i - 1,
                        'headers': list(header_stack)
                    })
                    list_lines = []
                    in_list = False

                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                # Update header stack
                header_stack = [h for h in header_stack if h['level'] < level]
                header_stack.append({'level': level, 'title': title})

                sections.append({
                    'type': 'header',
                    'content': line,
                    'line_start': i,
                    'line_end': i,
                    'level': level,
                    'title': title,
                    'headers': list(header_stack[:-1])  # Parent headers
                })
                continue

            # Handle lists
            list_match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.+)$', line)
            if list_match:
                if not in_list:
                    in_list = True
                list_lines.append(line)
                continue
            elif in_list and line.strip():
                # Continuation of list item
                list_lines.append(line)
                continue
            elif in_list and not line.strip():
                # End of list
                sections.append({
                    'type': 'list',
                    'content': '\n'.join(list_lines),
                    'line_start': i - len(list_lines),
                    'line_end': i - 1,
                    'headers': list(header_stack)
                })
                list_lines = []
                in_list = False
                continue

            # Regular paragraph text
            if line.strip():
                sections.append({
                    'type': 'text',
                    'content': line,
                    'line_start': i,
                    'line_end': i,
                    'headers': list(header_stack)
                })

        # Handle remaining list
        if in_list and list_lines:
            sections.append({
                'type': 'list',
                'content': '\n'.join(list_lines),
                'line_start': len(lines) - len(list_lines),
                'line_end': len(lines) - 1,
                'headers': list(header_stack)
            })

        return sections

    def _extract_code_language(self, code_fence: str) -> str:
        """Extract language from code fence.

        Args:
            code_fence: First line of code block (```python)

        Returns:
            Language name or 'unknown'
        """
        match = re.match(r'^```(\w+)', code_fence)
        if match:
            return match.group(1)
        return 'unknown'

    def _create_chunks_from_sections(
        self,
        sections: List[Dict[str, Any]],
        parent_doc_id: str,
        metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """Create chunks from parsed sections.

        Args:
            sections: List of section dictionaries
            parent_doc_id: Parent document ID
            metadata: Base metadata

        Returns:
            List of Chunk objects
        """
        chunks = []
        current_chunk_sections = []
        current_size = 0
        chunk_index = 0

        for section in sections:
            section_size = len(section['content'])

            # Always keep code blocks and lists together
            if section['type'] in ('code', 'list'):
                # Flush current chunk if any
                if current_chunk_sections:
                    chunk = self._create_chunk_from_sections(
                        current_chunk_sections, parent_doc_id, chunk_index, metadata
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_chunk_sections = []
                    current_size = 0

                # Create chunk for code/list
                chunk = self._create_chunk_from_sections(
                    [section], parent_doc_id, chunk_index, metadata
                )
                chunks.append(chunk)
                chunk_index += 1
                continue

            # Check if adding this section would exceed max size
            if current_size + section_size > self.max_chunk_size and current_chunk_sections:
                # Create chunk from current sections
                chunk = self._create_chunk_from_sections(
                    current_chunk_sections, parent_doc_id, chunk_index, metadata
                )
                chunks.append(chunk)
                chunk_index += 1
                current_chunk_sections = []
                current_size = 0

            # Add section to current chunk
            current_chunk_sections.append(section)
            current_size += section_size

        # Create final chunk
        if current_chunk_sections:
            chunk = self._create_chunk_from_sections(
                current_chunk_sections, parent_doc_id, chunk_index, metadata
            )
            chunks.append(chunk)

        # Update total_chunks
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)

        return chunks

    def _create_chunk_from_sections(
        self,
        sections: List[Dict[str, Any]],
        parent_doc_id: str,
        chunk_index: int,
        metadata: Dict[str, Any]
    ) -> Chunk:
        """Create chunk from sections.

        Args:
            sections: List of sections to combine
            parent_doc_id: Parent document ID
            chunk_index: Chunk index
            metadata: Base metadata

        Returns:
            Chunk object
        """
        # Combine section content
        content_parts = []

        # Add header context if configured
        if self.preserve_headers and sections and sections[0]['headers']:
            for header in sections[0]['headers']:
                content_parts.append('#' * header['level'] + ' ' + header['title'])

        # Add section content
        for section in sections:
            content_parts.append(section['content'])

        chunk_text = '\n'.join(content_parts)

        # Determine chunk type
        chunk_types = [s['type'] for s in sections]
        if 'code' in chunk_types:
            chunk_type = 'code'
        elif 'list' in chunk_types:
            chunk_type = 'list'
        elif 'header' in chunk_types:
            chunk_type = 'header'
        else:
            chunk_type = 'text'

        # Extract section info
        section_titles = []
        if sections and sections[0]['headers']:
            section_titles = [h['title'] for h in sections[0]['headers']]

        chunk_id = self._generate_chunk_id(parent_doc_id, chunk_index)

        return Chunk(
            chunk_id=chunk_id,
            text=chunk_text.strip(),
            metadata={
                **metadata,
                'chunk_index': chunk_index,
                'chunk_type': chunk_type,
                'section': section_titles[-1] if section_titles else None,
                'subsection': section_titles[-2] if len(section_titles) > 1 else None,
                'line_start': sections[0]['line_start'],
                'line_end': sections[-1]['line_end'],
                'num_sections': len(sections)
            }
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get chunker statistics.

        Returns:
            Dictionary with chunker stats
        """
        return {
            **super().get_stats(),
            'max_chunk_size': self.max_chunk_size,
            'preserve_headers': self.preserve_headers
        }
