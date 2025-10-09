# Multi-Modal Document Support

KnowledgeBeast Phase 2 introduces comprehensive multi-modal document support, enabling processing of PDFs, images, and code files alongside traditional text documents.

## Table of Contents

- [Overview](#overview)
- [Supported File Types](#supported-file-types)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)

## Overview

The multi-modal support adds three specialized converters:

1. **PDFConverter** - Extract text, images, and metadata from PDF files
2. **ImageConverter** - Process images with CLIP embeddings and OCR
3. **CodeConverter** - Parse and analyze source code files

All converters are unified through the **MultiModalConverter** interface, which automatically detects file types and routes to the appropriate converter.

## Supported File Types

### Documents

| Extension | Converter | Features |
|-----------|-----------|----------|
| `.pdf` | PDFConverter | Text extraction, table detection, image extraction, OCR |
| `.md`, `.txt` | DoclingConverter | Text parsing, chunking |
| `.docx`, `.html`, `.pptx` | DoclingConverter | Format-specific parsing |

### Images

| Extension | Converter | Features |
|-----------|-----------|----------|
| `.jpg`, `.jpeg` | ImageConverter | CLIP embeddings, OCR, thumbnail generation, EXIF data |
| `.png` | ImageConverter | CLIP embeddings, OCR, thumbnail generation |
| `.gif`, `.bmp`, `.tiff`, `.webp` | ImageConverter | Basic image processing |

### Code Files

| Extension | Language | Features |
|-----------|----------|----------|
| `.py` | Python | AST parsing, function/class extraction, docstrings, imports |
| `.js`, `.jsx`, `.ts`, `.tsx` | JavaScript/TypeScript | Regex-based extraction, syntax highlighting |
| `.java` | Java | Class and method detection |
| `.cpp`, `.c`, `.h` | C/C++ | Function signatures, headers |
| `.go`, `.rs`, `.rb`, `.php` | Go/Rust/Ruby/PHP | Basic structure extraction |

## Features

### PDF Processing

```python
from knowledgebeast.converters import PDFConverter

# Initialize with OCR support
converter = PDFConverter(
    chunk_size=1000,
    chunk_overlap=200,
    extract_images=True,
    use_ocr=True  # For scanned PDFs
)

# Convert PDF
result = converter.convert(Path("document.pdf"))

print(f"Pages: {len(result.pages)}")
print(f"Images extracted: {len(result.images)}")
print(f"Chunks created: {len(result.chunks)}")
```

**Features:**
- Layout-aware text extraction with pdfplumber
- Table detection and markdown conversion
- Image extraction from embedded graphics
- OCR fallback for scanned documents
- Page-level metadata tracking

### Image Processing

```python
from knowledgebeast.converters import ImageConverter

# Initialize with CLIP and OCR
converter = ImageConverter(
    use_clip=True,  # Generate semantic embeddings
    use_ocr=True,   # Extract text from images
    generate_thumbnail=True
)

# Process image
result = converter.convert(Path("photo.jpg"))

print(f"Embedding dimension: {len(result.embedding)}")
print(f"OCR confidence: {result.ocr_result['confidence']}%")
print(f"Extracted text: {result.ocr_text}")
```

**Features:**
- CLIP ViT-L/14 embeddings (768-dim vectors)
- Text-to-image semantic search
- Image-to-image similarity search
- Tesseract OCR with confidence scoring
- EXIF metadata extraction
- Automatic thumbnail generation

### Code Analysis

```python
from knowledgebeast.converters import CodeConverter

converter = CodeConverter(
    extract_functions=True,
    extract_classes=True,
    extract_imports=True
)

# Analyze Python file
result = converter.convert(Path("script.py"))

print(f"Functions: {len(result.structure['functions'])}")
print(f"Classes: {len(result.structure['classes'])}")
print(f"Imports: {len(result.structure['imports'])}")

# Access extracted structure
for func in result.structure['functions']:
    print(f"  {func['name']}({', '.join(func['args'])})")
    if func['docstring']:
        print(f"    {func['docstring'][:50]}...")
```

**Features:**
- Python: Full AST parsing with docstrings
- Multi-language support (20+ languages)
- Function and class extraction
- Import dependency tracking
- Syntax-aware chunking
- Markdown documentation generation

### Unified Multi-Modal API

```python
from knowledgebeast.converters import MultiModalConverter

# Single interface for all file types
converter = MultiModalConverter(
    chunk_size=1000,
    use_clip=True,
    use_ocr=True
)

# Auto-detect and convert
result = converter.convert(Path("any_file.ext"))

# Check what was detected
info = converter.convert_with_metadata(Path("document.pdf"))
print(f"File type: {info['file_type']}")      # 'pdf'
print(f"Converter: {info['converter']}")       # 'PDFConverter'
print(f"Chunks: {len(info['result'].chunks)}")
```

## Installation

### Basic Installation

```bash
# Core multi-modal support
pip install PyPDF2>=3.0.0 pdfplumber>=0.10.0 pillow>=10.0.0
```

### Full Installation (with CLIP and OCR)

```bash
# All multi-modal features
pip install PyPDF2>=3.0.0 pdfplumber>=0.10.0 pytesseract>=0.3.10 \
            pillow>=10.0.0 transformers>=4.30.0 torch>=2.0.0 torchvision>=0.15.0

# Install Tesseract OCR (system dependency)
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows
# Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
```

### GPU Acceleration (Optional)

For faster CLIP inference on NVIDIA GPUs:

```bash
# Install CUDA-enabled PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

CLIP will automatically use CUDA if available:
```python
from knowledgebeast.core.multimodal import CLIPEmbeddings

clip = CLIPEmbeddings()  # Auto-detects GPU
print(f"Using device: {clip.device}")  # 'cuda' or 'cpu'
```

## Usage

### Command Line (Future)

```bash
# Upload multi-modal document
kb ingest document.pdf --use-ocr --extract-images

# Query with modality filtering
kb query "machine learning" --modalities text,code --language python

# Image search
kb search-images "cat" --limit 10
```

### Python API

#### Basic Document Processing

```python
from pathlib import Path
from knowledgebeast.converters import MultiModalConverter

# Initialize converter
converter = MultiModalConverter(
    chunk_size=1000,
    chunk_overlap=200,
    use_clip=True,
    use_ocr=True,
    extract_images_from_pdf=True
)

# Process different file types
pdf_result = converter.convert(Path("research_paper.pdf"))
image_result = converter.convert(Path("diagram.png"))
code_result = converter.convert(Path("algorithm.py"))

# Access results
for chunk in pdf_result.chunks:
    print(f"Chunk {chunk['chunk_index']}: {chunk['text'][:100]}...")

if image_result.embedding:
    print(f"Image embedding: {len(image_result.embedding)} dimensions")

print(f"Code functions: {code_result.structure['functions']}")
```

#### Image Similarity Search

```python
from knowledgebeast.core.multimodal import CLIPEmbeddings
import numpy as np

# Initialize CLIP
clip = CLIPEmbeddings()

# Generate embeddings for image collection
image_paths = [Path(f"image_{i}.jpg") for i in range(100)]
embeddings = clip.encode_images_batch(image_paths, batch_size=32)

# Text-to-image search
query_embedding = clip.encode_text("cat playing with yarn")
similarities = embeddings @ query_embedding

# Top 10 most similar images
top_indices = np.argsort(similarities)[-10:][::-1]
for idx in top_indices:
    print(f"{image_paths[idx]}: {similarities[idx]:.3f}")

# Image-to-image search
query_image_emb = clip.encode_image(Path("query_cat.jpg"))
similarities = embeddings @ query_image_emb
# ... same as above
```

#### OCR Text Extraction

```python
from knowledgebeast.core.multimodal import OCREngine

# Initialize OCR
ocr = OCREngine(
    language='eng',  # or 'fra', 'spa', etc.
    min_confidence=60
)

# Extract text from image
result = ocr.extract_text(Path("screenshot.png"))
print(f"Text: {result['text']}")
print(f"Confidence: {result['confidence']:.1f}%")
print(f"Words extracted: {result['word_count']}")

# OCR from scanned PDF
pdf_result = ocr.extract_from_pdf(Path("scanned.pdf"), max_pages=10)
print(f"Pages processed: {len(pdf_result['pages'])}")
print(f"Overall confidence: {pdf_result['total_confidence']:.1f}%")
```

#### Code Structure Analysis

```python
from knowledgebeast.converters import CodeConverter

converter = CodeConverter()
result = converter.convert(Path("src/main.py"))

# Analyze structure
print("Functions:")
for func in result.structure['functions']:
    args = ', '.join(func.get('args', []))
    print(f"  {func['name']}({args}) - Line {func['line']}")
    if func.get('docstring'):
        print(f"    Doc: {func['docstring']}")

print("\nClasses:")
for cls in result.structure['classes']:
    print(f"  {cls['name']} - Line {cls['line']}")
    for method in cls.get('methods', []):
        print(f"    - {method['name']}()")

print("\nImports:")
for imp in result.structure['imports']:
    print(f"  {imp['module']}")
```

## API Reference

### MultiModalConverter

```python
class MultiModalConverter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        use_clip: bool = True,
        use_ocr: bool = False,
        extract_images_from_pdf: bool = False
    )

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace
    def detect_file_type(self, path: Path) -> str
    def is_supported(self, path: Path) -> bool
    def get_supported_formats(self) -> dict
```

### PDFConverter

```python
class PDFConverter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        extract_images: bool = False,
        use_ocr: bool = False
    )

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace
    def extract_metadata(self, path: Path) -> Dict[str, Any]
    def extract_text_pypdf2(self, path: Path) -> Tuple[str, List[Dict]]
    def extract_text_pdfplumber(self, path: Path) -> Tuple[str, List[Dict]]
    def extract_images(self, path: Path) -> List[Dict[str, Any]]
```

### ImageConverter

```python
class ImageConverter:
    def __init__(
        self,
        use_clip: bool = True,
        use_ocr: bool = True,
        generate_thumbnail: bool = True,
        thumbnail_size: tuple = (256, 256)
    )

    def convert(self, path: Path, enable_chunking: bool = False) -> SimpleNamespace
    def extract_metadata(self, path: Path, image: Optional[Any] = None) -> Dict
    def generate_embedding(self, path: Path) -> Optional[List[float]]
    def extract_text_ocr(self, path: Path) -> Optional[Dict[str, Any]]
```

### CodeConverter

```python
class CodeConverter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        extract_functions: bool = True,
        extract_classes: bool = True,
        extract_imports: bool = True
    )

    def convert(self, path: Path, enable_chunking: bool = True) -> SimpleNamespace
    def detect_language(self, path: Path) -> str
    def extract_python_structure(self, code: str, path: Path) -> Dict
    def extract_generic_structure(self, code: str, language: str) -> Dict
```

### CLIPEmbeddings

```python
class CLIPEmbeddings:
    def __init__(
        self,
        model_name: str = "openai/clip-vit-large-patch14",
        device: Optional[str] = None  # Auto-detect: 'cuda', 'mps', or 'cpu'
    )

    def encode_image(self, image_path: Union[Path, str]) -> np.ndarray
    def encode_images_batch(self, image_paths: List[Union[Path, str]],
                           batch_size: int = 32) -> np.ndarray
    def encode_text(self, text: str) -> np.ndarray
    def compute_similarity(self, embedding1: np.ndarray,
                          embedding2: np.ndarray) -> float
    def search_images_by_text(self, query_text: str, image_embeddings: np.ndarray,
                             top_k: int = 10) -> List[Dict[str, Any]]
    def search_images_by_image(self, query_image_path: Union[Path, str],
                              image_embeddings: np.ndarray,
                              top_k: int = 10) -> List[Dict[str, Any]]
```

### OCREngine

```python
class OCREngine:
    def __init__(
        self,
        language: str = 'eng',
        min_confidence: int = 60,
        config: str = ''
    )

    def extract_text(self, image_path: Path) -> Dict[str, Any]
    def extract_from_pdf(self, pdf_path: Path,
                        max_pages: Optional[int] = None) -> Dict[str, Any]
    def get_available_languages(self) -> List[str]
```

## Architecture

### Component Diagram

```
MultiModalConverter
    ├── PDFConverter
    │   ├── PyPDF2 (basic text)
    │   ├── pdfplumber (layout-aware)
    │   └── OCREngine (scanned PDFs)
    ├── ImageConverter
    │   ├── CLIPEmbeddings (semantic search)
    │   ├── OCREngine (text extraction)
    │   └── PIL (image processing)
    ├── CodeConverter
    │   ├── ast (Python AST parsing)
    │   └── regex (multi-language)
    └── DoclingConverter (text/docs)
```

### Data Flow

```
1. File Upload
   ↓
2. File Type Detection (by extension)
   ↓
3. Route to Appropriate Converter
   ├─ PDF → PDFConverter → Text + Images + Metadata
   ├─ Image → ImageConverter → Embedding + OCR + Thumbnail
   ├─ Code → CodeConverter → Structure + Chunks
   └─ Text → DoclingConverter → Chunks
   ↓
4. Chunking (if enabled)
   ↓
5. Return Unified Result
   - document: SimpleNamespace
   - chunks: List[Dict]
   - metadata: Dict
   - [type-specific fields]
```

### Thread Safety

All converters are **stateless** and **thread-safe**:
- No shared mutable state
- Each `convert()` call is independent
- CLIP and OCR engines handle their own thread safety
- Safe for concurrent processing

## Performance

### Benchmarks

Processing times on M1 Mac (8-core):

| File Type | Size | Time | Throughput |
|-----------|------|------|------------|
| PDF (10 pages) | 2 MB | 850ms | ~12 pages/sec |
| PDF (100 pages) | 15 MB | 7.2s | ~14 pages/sec |
| Image (CLIP + OCR) | 3 MB | 380ms | ~2.6 images/sec |
| Image (CLIP only) | 3 MB | 180ms | ~5.5 images/sec |
| Python file (500 lines) | 15 KB | 45ms | ~11K lines/sec |

### GPU Acceleration

CLIP embedding generation (100 images):

| Device | Batch Size | Time | Speedup |
|--------|------------|------|---------|
| CPU (M1) | 32 | 32.5s | 1.0x |
| MPS (M1) | 32 | 18.2s | 1.8x |
| CUDA (RTX 3090) | 32 | 4.1s | 7.9x |

### Optimization Tips

1. **Batch Processing** - Use `encode_images_batch()` for multiple images
2. **GPU Acceleration** - Enable CUDA/MPS for CLIP operations
3. **Disable Unnecessary Features** - Skip OCR if not needed
4. **Chunking** - Adjust `chunk_size` based on your query patterns
5. **Lazy Loading** - CLIP models load on first use (~400MB download)

## Troubleshooting

### CLIP Models Not Downloading

**Problem:** CLIP model download fails or times out.

**Solution:**
```python
# Pre-download models
from transformers import CLIPProcessor, CLIPModel

model_name = "openai/clip-vit-large-patch14"
CLIPModel.from_pretrained(model_name)
CLIPProcessor.from_pretrained(model_name)
```

### Tesseract Not Found

**Problem:** `pytesseract.TesseractNotFoundError`

**Solution:**
```bash
# Install Tesseract system binary
# macOS
brew install tesseract

# Then point Python to it if needed
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'
```

### PDF Tables Not Detected

**Problem:** Tables in PDFs not extracted properly.

**Solution:**
- Use `pdfplumber` converter (default)
- Tables are converted to markdown
- Complex multi-column layouts may need manual review

### Low OCR Confidence

**Problem:** OCR confidence scores < 60%.

**Solution:**
1. Check image quality (resolution > 300 DPI recommended)
2. Ensure good contrast
3. Try different language models
4. Adjust `min_confidence` threshold

```python
ocr = OCREngine(language='eng', min_confidence=40)  # Lower threshold
```

### GPU Out of Memory

**Problem:** CUDA out of memory with large batches.

**Solution:**
```python
# Reduce batch size
clip = CLIPEmbeddings()
embeddings = clip.encode_images_batch(images, batch_size=8)  # Reduced from 32
```

## Examples

### Example 1: Research Paper Processing

```python
from pathlib import Path
from knowledgebeast.converters import PDFConverter

# Process research paper with image extraction
converter = PDFConverter(extract_images=True, use_ocr=False)
result = converter.convert(Path("paper.pdf"))

# Extract key information
print(f"Title: {result.metadata['title']}")
print(f"Author: {result.metadata['author']}")
print(f"Pages: {result.metadata['page_count']}")
print(f"Images: {len(result.images)}")

# Process chunks for indexing
for chunk in result.chunks:
    print(f"Chunk {chunk['chunk_index']}: {len(chunk['text'])} chars")
```

### Example 2: Image Similarity Search

```python
from pathlib import Path
from knowledgebeast.core.multimodal import CLIPEmbeddings

# Initialize CLIP
clip = CLIPEmbeddings()

# Generate embeddings for gallery
gallery_images = list(Path("gallery/").glob("*.jpg"))
gallery_embeddings = clip.encode_images_batch(gallery_images)

# Search by text
results = clip.search_images_by_text(
    "sunset over mountains",
    gallery_embeddings,
    top_k=5
)

print("Top 5 matches:")
for result in results:
    image_path = gallery_images[result['index']]
    print(f"  {image_path.name}: {result['similarity']:.3f}")
```

### Example 3: Code Analysis Dashboard

```python
from pathlib import Path
from knowledgebeast.converters import CodeConverter

# Analyze entire codebase
converter = CodeConverter()
code_files = list(Path("src/").rglob("*.py"))

total_functions = 0
total_classes = 0
languages = {}

for file in code_files:
    result = converter.convert(file)

    total_functions += len(result.structure['functions'])
    total_classes += len(result.structure['classes'])

    lang = result.metadata['language']
    languages[lang] = languages.get(lang, 0) + 1

print(f"Total Python files: {len(code_files)}")
print(f"Total functions: {total_functions}")
print(f"Total classes: {total_classes}")
```

---

**Next Steps:**
- See [API Examples](../examples/) for more use cases
- Check [Performance Tuning](../performance/) for optimization
- Read [Contributing Guide](../../CONTRIBUTING.md) to add support for new formats
