"""Code file converter with syntax-aware parsing and structure extraction.

This module provides code file processing with:
- Multi-language support (Python, JavaScript, Java, C++, etc.)
- Function and class extraction
- Docstring/comment extraction
- Import/dependency tracking
- Syntax highlighting in markdown output
"""

import ast
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from types import SimpleNamespace

logger = logging.getLogger(__name__)


class CodeConverter:
    """Code file converter with syntax-aware parsing.

    This converter extracts structure and documentation from source code
    files with multi-language support.

    Thread Safety:
        - Stateless converter, safe for concurrent use
        - Each convert() call is independent
        - No shared mutable state

    Attributes:
        chunk_size: Maximum chunk size in characters (default: 1000)
        chunk_overlap: Overlap between chunks in characters (default: 200)
        extract_functions: Whether to extract function definitions
        extract_classes: Whether to extract class definitions
        extract_imports: Whether to track imports/dependencies
    """

    # Language-specific file extensions
    LANGUAGE_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.m': 'objective-c',
        '.sh': 'bash',
        '.sql': 'sql',
        '.r': 'r',
        '.lua': 'lua',
    }

    SUPPORTED_FORMATS = set(LANGUAGE_MAP.keys())

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        extract_functions: bool = True,
        extract_classes: bool = True,
        extract_imports: bool = True
    ):
        """Initialize CodeConverter.

        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            extract_functions: Whether to extract function definitions
            extract_classes: Whether to extract class definitions
            extract_imports: Whether to track imports/dependencies
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.extract_functions = extract_functions
        self.extract_classes = extract_classes
        self.extract_imports = extract_imports

    def is_supported(self, path: Path) -> bool:
        """Check if file format is supported.

        Args:
            path: Path to file

        Returns:
            True if format is supported, False otherwise
        """
        return path.suffix.lower() in self.SUPPORTED_FORMATS

    def detect_language(self, path: Path) -> str:
        """Detect programming language from file extension.

        Args:
            path: Path to source file

        Returns:
            Language name (e.g., 'python', 'javascript')
        """
        return self.LANGUAGE_MAP.get(path.suffix.lower(), 'unknown')

    def extract_metadata(self, path: Path, code: str, language: str) -> Dict[str, Any]:
        """Extract metadata from code file.

        Args:
            path: Path to code file
            code: Source code content
            language: Programming language

        Returns:
            Dictionary containing metadata
        """
        metadata = {
            'filename': path.name,
            'format': path.suffix.lower(),
            'size_bytes': len(code.encode('utf-8')),
            'modality': 'code',
            'document_type': 'code',
            'language': language,
        }

        try:
            # File system metadata
            stat = path.stat()
            metadata['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            metadata['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception as e:
            logger.warning(f"Could not extract file metadata: {e}")

        # Basic code metrics
        lines = code.split('\n')
        metadata['line_count'] = len(lines)
        metadata['char_count'] = len(code)

        # Count non-empty, non-comment lines (approximate)
        code_lines = [
            line for line in lines
            if line.strip() and not line.strip().startswith(('#', '//', '/*', '*'))
        ]
        metadata['code_line_count'] = len(code_lines)

        metadata['title'] = path.stem

        return metadata

    def extract_python_structure(self, code: str, path: Path) -> Dict[str, Any]:
        """Extract structure from Python code using AST.

        Args:
            code: Python source code
            path: Path to file (for error reporting)

        Returns:
            Dictionary with functions, classes, and imports
        """
        structure = {
            'functions': [],
            'classes': [],
            'imports': [],
        }

        try:
            tree = ast.parse(code, filename=str(path))

            for node in ast.walk(tree):
                # Extract function definitions
                if self.extract_functions and isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node) or '',
                    }

                    # Check for decorators
                    decorators = [d.id if isinstance(d, ast.Name) else str(d)
                                  for d in node.decorator_list]
                    if decorators:
                        func_info['decorators'] = decorators

                    structure['functions'].append(func_info)

                # Extract class definitions
                elif self.extract_classes and isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'docstring': ast.get_docstring(node) or '',
                        'methods': [],
                    }

                    # Extract base classes
                    bases = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.append(base.attr)
                    if bases:
                        class_info['bases'] = bases

                    # Extract methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            class_info['methods'].append({
                                'name': item.name,
                                'line': item.lineno,
                                'docstring': ast.get_docstring(item) or '',
                            })

                    structure['classes'].append(class_info)

                # Extract imports
                elif self.extract_imports and isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            structure['imports'].append({
                                'module': alias.name,
                                'alias': alias.asname,
                                'line': node.lineno,
                            })
                    else:  # ImportFrom
                        module = node.module or ''
                        for alias in node.names:
                            structure['imports'].append({
                                'module': f"{module}.{alias.name}" if module else alias.name,
                                'alias': alias.asname,
                                'from': module,
                                'line': node.lineno,
                            })

        except SyntaxError as e:
            logger.warning(f"Python syntax error in {path}: {e}")
        except Exception as e:
            logger.warning(f"Failed to parse Python code: {e}")

        return structure

    def extract_generic_structure(self, code: str, language: str) -> Dict[str, Any]:
        """Extract structure using regex patterns (for non-Python languages).

        Args:
            code: Source code
            language: Programming language

        Returns:
            Dictionary with functions, classes, and imports
        """
        structure = {
            'functions': [],
            'classes': [],
            'imports': [],
        }

        lines = code.split('\n')

        # Language-specific patterns
        if language == 'javascript' or language == 'typescript':
            # Function patterns
            func_patterns = [
                r'function\s+(\w+)\s*\(',  # function name()
                r'const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',  # const name = () =>
                r'(\w+)\s*:\s*(?:async\s*)?\([^)]*\)\s*=>',  # name: () =>
            ]

            # Class patterns
            class_patterns = [
                r'class\s+(\w+)',
            ]

            # Import patterns
            import_patterns = [
                r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',  # import ... from 'module'
                r'import\s+[\'"]([^\'"]+)[\'"]',  # import 'module'
                r'require\([\'"]([^\'"]+)[\'"]\)',  # require('module')
            ]

        elif language == 'java':
            func_patterns = [
                r'(?:public|private|protected)?\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(',
            ]
            class_patterns = [
                r'(?:public|private)?\s+class\s+(\w+)',
            ]
            import_patterns = [
                r'import\s+([\w.]+);',
            ]

        else:
            # Generic patterns
            func_patterns = [r'def\s+(\w+)\s*\(', r'function\s+(\w+)\s*\(']
            class_patterns = [r'class\s+(\w+)']
            import_patterns = [r'import\s+([\w.]+)']

        # Extract functions
        if self.extract_functions:
            for i, line in enumerate(lines, 1):
                for pattern in func_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        structure['functions'].append({
                            'name': match if isinstance(match, str) else match[0],
                            'line': i,
                        })

        # Extract classes
        if self.extract_classes:
            for i, line in enumerate(lines, 1):
                for pattern in class_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        structure['classes'].append({
                            'name': match if isinstance(match, str) else match[0],
                            'line': i,
                        })

        # Extract imports
        if self.extract_imports:
            for i, line in enumerate(lines, 1):
                for pattern in import_patterns:
                    matches = re.findall(pattern, line)
                    for match in matches:
                        structure['imports'].append({
                            'module': match if isinstance(match, str) else match[0],
                            'line': i,
                        })

        return structure

    def chunk_code(self, code: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Split code into overlapping chunks.

        Args:
            code: Source code to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunks with text and metadata
        """
        if not code:
            return []

        chunks = []
        lines = code.split('\n')
        current_chunk = []
        current_size = 0
        chunk_index = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline

            if current_size + line_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'chunk_index': chunk_index,
                    'line_count': len(current_chunk),
                    'modality': 'text',
                    'metadata': metadata.copy() if metadata else {},
                })
                chunk_index += 1

                # Start new chunk with overlap
                overlap_lines = max(1, self.chunk_overlap // 50)  # Approximate lines
                current_chunk = current_chunk[-overlap_lines:] if len(current_chunk) > overlap_lines else []
                current_size = sum(len(l) + 1 for l in current_chunk)

            current_chunk.append(line)
            current_size += line_size

        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'chunk_index': chunk_index,
                'line_count': len(current_chunk),
                'modality': 'text',
                'metadata': metadata.copy() if metadata else {},
            })

        return chunks

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace:
        """Convert code file with structure extraction and chunking.

        Args:
            path: Path to code file
            enable_chunking: Whether to split into chunks (default: True)

        Returns:
            SimpleNamespace with:
                - document: SimpleNamespace with name and export_to_markdown method
                - chunks: List of code chunks (if enable_chunking=True)
                - metadata: File metadata including language and metrics
                - structure: Extracted functions, classes, and imports

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
            RuntimeError: If conversion fails
        """
        if not self.is_supported(path):
            raise ValueError(
                f"Unsupported format: {path.suffix}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            # Read source code
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()

            # Detect language
            language = self.detect_language(path)

            # Extract metadata
            metadata = self.extract_metadata(path, code, language)

            # Extract code structure
            if language == 'python':
                structure = self.extract_python_structure(code, path)
            else:
                structure = self.extract_generic_structure(code, language)

            # Add structure info to metadata
            metadata['function_count'] = len(structure['functions'])
            metadata['class_count'] = len(structure['classes'])
            metadata['import_count'] = len(structure['imports'])

            # Create markdown representation
            markdown = f"# {metadata['title']}\n\n"
            markdown += f"**Language:** {language}\n\n"

            # Add structure documentation
            if structure['imports']:
                markdown += "## Imports\n\n"
                for imp in structure['imports'][:10]:  # Limit to first 10
                    markdown += f"- `{imp['module']}`\n"
                markdown += "\n"

            if structure['classes']:
                markdown += "## Classes\n\n"
                for cls in structure['classes']:
                    markdown += f"### {cls['name']} (line {cls['line']})\n\n"
                    if cls.get('docstring'):
                        markdown += f"{cls['docstring']}\n\n"

            if structure['functions']:
                markdown += "## Functions\n\n"
                for func in structure['functions']:
                    args = func.get('args', [])
                    args_str = ', '.join(args) if args else ''
                    markdown += f"### {func['name']}({args_str}) (line {func['line']})\n\n"
                    if func.get('docstring'):
                        markdown += f"{func['docstring']}\n\n"

            # Add source code
            markdown += f"## Source Code\n\n```{language}\n{code}\n```\n"

            # Create chunks
            chunks = []
            if enable_chunking:
                chunks = self.chunk_code(code, metadata)

            # Return result
            return SimpleNamespace(
                document=SimpleNamespace(
                    name=metadata['title'],
                    export_to_markdown=lambda: markdown
                ),
                chunks=chunks,
                metadata=metadata,
                structure=structure,
                source_code=code,
                language=language
            )

        except Exception as e:
            logger.error(f"Code conversion failed for {path}: {e}")
            raise RuntimeError(f"Code conversion failed: {e}") from e
