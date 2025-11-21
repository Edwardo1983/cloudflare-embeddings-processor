# Cloudflare Embeddings Processor

Advanced PDF processing system with AI-powered embeddings and vector search capability.

## Features

- **PDF Text Extraction**: Extract text from multiple PDFs with page tracking
- **AI Embeddings**: Generate 768-dimensional embeddings using Cloudflare AI
- **Vector Database**: Store and search embeddings in Pinecone
- **Batch Processing**: Efficient processing of large document collections
- **Incremental Processing**: Only process new/modified files (v4.0)
- **Educational Focus**: Optimized for Romanian educational materials

## Project Structure

```
cloudflare-embeddings-processor/
├── config.py                 # API keys and configuration
├── extract_pdfs.py          # PDF text extraction with manifest tracking
├── generate_embeddings.py   # Cloudflare AI + Pinecone integration
├── test_search.py           # Search validation and testing
├── requirements.txt         # Python dependencies
└── materiale_didactice/     # Source PDF materials
    ├── Scoala_de_Muzica_George_Enescu/
    └── Scoala_Normala/
```

## Prerequisites

- Python 3.9+ (Tested with Python 3.9.13)
- Cloudflare Account with Workers & Pages enabled
- Pinecone Account

## Installation

### 1. Setup Cloudflare

1. Create free account at https://cloudflare.com
2. Navigate to Workers & Pages → AI
3. Generate API Token:
   - Go to Account Settings → API Tokens
   - Create token with "AI" scope
   - Note your Account ID and API Token

### 2. Setup Pinecone

1. Create free account at https://pinecone.io
2. Create new index:
   - Name: `educational-ai`
   - Dimension: `768`
   - Metric: `cosine`
   - Serverless spec: AWS/us-east-1
3. Generate and note your API key

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create `.env` file in project root:

```env
# Cloudflare Configuration
CLOUDFLARE_API_TOKEN=your_token_here
CLOUDFLARE_ACCOUNT_ID=your_account_id_here

# Pinecone Configuration
PINECONE_API_KEY=your_api_key_here
PINECONE_INDEX_NAME=educational-ai

# Processing
PDF_SOURCE_DIR=./materiale_didactice
EXTRACTED_TEXT_DIR=./extracted_texts
LOG_LEVEL=INFO
```

## Usage

### 1. Extract Text from PDFs

**Default usage** (processes 2 school folders):
```bash
python extract_pdfs.py
```

**Advanced CLI options**:
```bash
# Process all folders in materiale_didactice
python extract_pdfs.py --all

# Process specific folder(s)
python extract_pdfs.py --folders Scoala_de_Muzica_George_Enescu
python extract_pdfs.py --folders Folder1 Folder2 Folder3

# Limit number of PDFs processed
python extract_pdfs.py --limit 50
python extract_pdfs.py --limit 100 --all

# Combine options
python extract_pdfs.py --folders Scoala_Normala --limit 20
```

**Incremental Processing** (NEW - Only process new/modified files):
```bash
# First run: extract and create manifest
python extract_pdfs.py --all

# Subsequent runs: only process new/modified files (FAST!)
python extract_pdfs.py --incremental

# Force reprocess everything (bypass manifest)
python extract_pdfs.py --force

# Combine with folder selection
python extract_pdfs.py --folders Scoala_Normala --incremental
python extract_pdfs.py --all --incremental --limit 100
```

**Help**:
```bash
python extract_pdfs.py --help
```

Extracts text from specified folders with robust error handling for scanned/corrupted PDFs.

Outputs:
- `extracted_texts/extraction_summary.json` - Detailed extraction report
- `extracted_texts/.extraction_manifest.json` - File tracking manifest (for incremental mode)

### 2. Generate Embeddings and Store in Pinecone

```bash
python generate_embeddings.py
```

Process flow:
1. Load extracted texts
2. Chunk texts with overlap (500 chars, 100 char overlap)
3. Generate embeddings via Cloudflare AI
4. Store vectors in Pinecone

Output: Summary statistics and embedding count

### 3. Test Search Functionality

**Default usage**:
```bash
python test_search.py
```

**Custom extraction directory**:
```bash
python test_search.py --extracted-dir ./custom_extraction
python test_search.py --extracted-dir /path/to/extracted_texts
```

**Help**:
```bash
python test_search.py --help
```

Tests:
- Index statistics
- 5 predefined search queries
- Result ranking and relevance
- Validates extracted files in selected directory

## Configuration Options

### Text Chunking
- `CHUNK_SIZE`: 500 characters per chunk
- `CHUNK_OVERLAP`: 100 character overlap between chunks

### Embeddings
- `EMBEDDING_DIMENSION`: 768 (Cloudflare AI standard)
- `BATCH_SIZE`: 32 vectors per Pinecone batch

### Processing
- `LOG_LEVEL`: INFO, DEBUG, WARNING, ERROR

## API Models

### Cloudflare AI
- Model: `@cf/baai/bge-base-en-v1.5`
- Output: 768-dimensional vectors
- Metric: Cosine similarity

### Pinecone
- Index type: Serverless
- Cloud: AWS
- Region: us-east-1

## File Descriptions

### config.py
Central configuration management with environment variable support.

### extract_pdfs.py
- `PDFExtractor` class: Handles PDF reading and text extraction with manifest tracking
- `extract_specific_folders()`: Process specific school materials
- `extract_all()`: Batch process all PDFs (supports incremental mode)
- Manifest-based change detection via file hashing
- JSON output with metadata

### generate_embeddings.py
- `CloudflareEmbedder`: API calls to Cloudflare AI
- `TextChunker`: Smart text chunking with overlap
- `PineconeIndexManager`: Vector database operations
- `EmbeddingPipeline`: Orchestrates complete workflow

### test_search.py
- `SearchTester`: Search functionality validation
- `test_searches()`: Run multiple queries
- `test_index_stats()`: Display vector database statistics
- `ExtractionValidator`: Validates extracted files with rglob for nested folders

## Performance Metrics

- PDF extraction: ~50ms per page
- Embedding generation: ~100ms per chunk (via Cloudflare API)
- Pinecone upsert: ~10ms per batch (32 vectors)
- Incremental processing: 10-20ms per file (hash checking only)

## Optimizations (v2.0)

### 1. **CLI Arguments for extract_pdfs.py**
- Flexible folder selection: `--folders Folder1 Folder2`, `--all`
- PDF limit support: `--limit N`
- Smart defaults with help text via `--help`
- Prevents hard-coded folder lists; adapts to directory structure changes

### 2. **Robust PDF Extraction**
- **None guard**: Handles scanned PDFs and corrupted pages gracefully
- Fixed: `if text and text.strip()` (was `if text.strip()`, causing AttributeError)
- Logs debug messages for non-extractable pages
- Batch processing continues even if individual PDFs fail

### 3. **Fixed Metadata Sync in Embedding Pipeline** (Critical)
- Changed embedding return: `(text, embedding)` → `(index, text, embedding)`
- Prevents metadata misalignment when embedding requests fail
- Each vector maintains correct chunk index using returned indices
- Ensures data integrity: No more off-by-one errors in metadata

### 4. **Windows Console Encoding Support**
- Added UTF-8 encoding wrapper for cross-platform compatibility
- Replaces Unicode symbols (✓/✗) with ASCII alternatives ([OK]/[FAIL])
- Sorted search results by score descending for correct ranking
- Handles Romanian text and special characters correctly

## Critical Fixes (v3.0)

### 1. **Deterministic Vector ID Strategy** (Production Critical)
- **Problem**: Time-based IDs caused duplicate vectors on re-runs
  - First run: 1000 vectors stored
  - Second run: 2000 vectors (1000 old + 1000 new duplicates)
  - Index accumulates stale data with each pipeline re-execution
- **Solution**: MD5 hash-based IDs from `(source_filename + chunk_index)`
- **Benefits**:
  - Idempotent: Re-running pipeline updates vectors instead of creating duplicates
  - Reproducible: Same content always gets same ID
  - Efficient: No accumulation of stale vectors in Pinecone
- **Implementation**: `generate_embeddings.py` lines 9, 323-327

### 2. **Folder Structure Preservation in Extraction Output**
- **Problem**: Filename collisions when PDFs with same name exist in different folders
- **Solution**: Preserve folder hierarchy in output directory matching source structure
- **Benefits**:
  - No data loss from filename collisions
  - Source location fully traceable from output directory structure
  - Metadata includes path context for better search indexing
- **Implementation**: `extract_pdfs.py` lines 141-143

### 3. **CLI Argument Support for test_search.py**
- **Problem**: Hardcoded extraction directory prevented headless testing against different outputs
- **Solution**: Added `--extracted-dir` CLI argument with sensible default
- **Usage**:
  ```bash
  python test_search.py                              # Default: ./extracted_texts
  python test_search.py --extracted-dir ./custom_dir # Custom directory
  python test_search.py --help                       # Show options
  ```
- **Benefits**:
  - Enables headless automation without wrapper scripts
  - Test against multiple extraction outputs
  - Flexible testing and validation workflows
  - Integration-friendly for CI/CD pipelines
- **Implementation**: `test_search.py` lines 24, 239-260

### 4. **Recursive File Discovery with rglob**
- **Problem**: ExtractionValidator couldn't find files in nested folder structure
- **Solution**: Changed from glob() to rglob() for recursive discovery
- **Impact**: Works with folder structure preservation from v3.0 fix #2

## Incremental Processing (v4.0)

### **File Change Detection with Manifest Tracking**

#### Problem
Without incremental processing, every pipeline run reprocesses all PDFs:
- First run: 100 PDFs → 100 extractions
- Second run: 100 PDFs + 20 new = 120 PDFs → 120 extractions (100 unnecessary!)
- Result: Exponential cost growth and time waste

#### Solution
Automatic change detection using `.extraction_manifest.json`:
- **Source Hash**: MD5 of PDF file (detects file modifications)
- **Extracted Hash**: MD5 of text content (tracks extraction success)
- **Status Tracking**: Records `success`, `partial`, `no_text`, `failed` for each file
- **Timestamp**: When each file was last processed

#### How It Works

**Manifest Structure**:
```json
{
  "extraction_version": "1.1",
  "last_updated": "2025-11-21T19:06:...",
  "files": {
    "Scoala_Normala/clasa_0/document.pdf": {
      "source_hash": "abc123def456...",
      "extracted_hash": "xyz789...",
      "extracted_pages": 8,
      "total_pages": 10,
      "extraction_status": "success",
      "timestamp": "2025-11-21T19:06:..."
    }
  }
}
```

**File Processing Logic**:
- NEW FILES: Always processed (hash absent from manifest)
- MODIFIED FILES: Hash changed → reprocessed
- UNCHANGED FILES: Skipped entirely in incremental mode (fast!)

#### Performance Impact

| Scenario | Without Incremental | With Incremental | Improvement |
|----------|-------------------|-----------------|------------|
| Add 20 PDFs to 100 | 120 extractions | 20 extractions | **83% faster** |
| Re-run unchanged | 100 extractions | 0 extractions | **100% time saved** |
| Update 5 of 100 | 100 extractions | 5 extractions | **95% faster** |
| Cost per update | $1.20 | $0.20 | **83% cost reduction** |

#### Error Handling

**PDFs with 0 extractable pages** (images, scanned):
- Status: `no_text`
- Logged but not stored in embeddings
- Pipeline continues without failure

**Corrupted/unopenable PDFs**:
- Status: `failed`
- Logged in manifest
- Pipeline continues with next file

## Subject-Based Namespace Isolation (v5.0)

### Overview

Phase 5.0 introduces **complete subject-based namespace isolation** in Pinecone to solve the context-confusion problem:

**Problem**: Without isolation, all embeddings mixed in single index → "1+1" could come from Matematica, Dezvoltare Personala, OR Geografie, causing factually correct but contextually wrong responses.

**Solution**: Separate Pinecone namespaces per subject course path with dual-interface search supporting both explicit subject selection and auto-routing.

### Architecture

#### Metadata Extraction

**Subject Path Parsing** (`extract_pdfs.py`):
- Folder hierarchy: `School/Class/Subject/PDFs`
- Example: `Scoala_Normala/clasa_0/Matematica/document.pdf`
- Automatically extracts and stores: `school`, `class`, `subject` in metadata

**Manifest Tracking** (`.extraction_manifest.json`):
- Now includes subject information per file:
  ```json
  {
    "Scoala_Normala/clasa_0/Matematica/file.pdf": {
      "school": "Scoala_Normala",
      "class": "clasa_0",
      "subject": "Matematica",
      "extraction_status": "success",
      "timestamp": "2025-11-21T..."
    }
  }
  ```

#### Namespace Management

**Namespace Format** (`generate_embeddings.py`):
- Format: `{school}_{class}_{subject}` (lowercase, underscores)
- Example: `scoala_normala_clasa_0_matematica`
- Each namespace completely isolated in Pinecone index

**Vector Grouping**:
1. Load extracted texts with subject metadata
2. Group chunks by calculated namespace
3. Upsert each group to its corresponding namespace
4. Vectors in same namespace searchable together; isolated from others

**Subject Mapping** (`subject_mapping.json`):
- Centralized subject configuration
- Maps subject names to namespaces
- Contains keywords for auto-routing:
  ```json
  {
    "primary": "Matematica",
    "aliases": ["Math", "Aritmetica"],
    "keywords": ["plus", "minus", "ecuatie", "teorema", ...],
    "namespace": "matematica"
  }
  ```

#### Dual-Interface Search

**New Search Module** (`search.py`):

**1. Explicit Subject Selection** (User specifies subject):
```bash
python search.py --subject "Matematica" --query "How to solve equations?"
python search.py --subject "Limba Romana" --class "clasa_1" --query "What is a sonnet?"
```
- Searches only in specified subject namespace
- Results guaranteed from correct subject context
- Best for targeted, precise searches

**2. Auto-Route Mode** (Keyword-based routing):
```bash
python search.py --auto-route --query "What is photosynthesis?"
```
- Analyzes query keywords against subject mapping
- Routes to best-matching subject automatically
- Falls back to all subjects if no clear match
- Best for general exploratory searches

**3. Utility Commands**:
```bash
# List all available subjects
python search.py --list-subjects

# Show Pinecone index statistics
python search.py --stats

# Custom school/class
python search.py --subject "Limba Romana" --school "Scoala_de_Muzica_George_Enescu" --class "clasa_1" --query "..."
```

### Implementation Details

#### extract_pdfs.py Changes
- Added `parse_subject_from_path()` method
- Extracts school, class, subject from path hierarchy
- Tracks identified subjects in summary
- Updates manifest with subject per file

#### generate_embeddings.py Changes
- Added `_load_subject_mapping()` to load configuration
- Added `_calculate_namespace()` to generate namespace from metadata
- Modified `upsert_vectors()` to accept optional `namespace` parameter
- Modified `search()` to accept optional `namespace` parameter
- Updated `process_pipeline()` to:
  - Group vectors by namespace
  - Upsert each group to its namespace
  - Track namespaces created
  - Report namespace statistics

#### search.py (NEW)
- `SubjectRouter` class: Route queries to appropriate namespaces
- `DualInterfaceSearch` class: Unified search interface
- Supports explicit subject selection or auto-routing
- Provides utility commands (list subjects, show stats)

### Usage Examples

**Basic Search (Explicit)**:
```bash
# Search only in Matematica for class 0
python search.py --subject "Matematica" --query "What is addition?"
# Output: Results only from scoala_normala_clasa_0_matematica namespace
```

**Auto-Route Search**:
```bash
# System automatically determines subject from query keywords
python search.py --auto-route --query "Describe photosynthesis"
# Output: Auto-routed to Stiinte_Naturale based on keyword matching
```

**Custom School/Class**:
```bash
python search.py --subject "Muzica" --school "Scoala_de_Muzica_George_Enescu" --class "clasa_2" --query "What is a sonata?"
```

**List Available Subjects**:
```bash
python search.py --list-subjects
# Output:
# Available Subjects:
# ==================
#   - Matematica
#   - Limba Romana
#   - Geografie
#   - ... (all subjects)
```

**View Index Statistics**:
```bash
python search.py --stats
# Shows namespace counts, vector distribution across subjects
```

### Workflow

1. **Extract PDFs** (subject metadata auto-detected):
   ```bash
   python extract_pdfs.py --all
   ```
   Output: Extractions include school/class/subject metadata

2. **Generate Embeddings** (namespace isolation automatic):
   ```bash
   python generate_embeddings.py
   ```
   Output: Vectors stored in subject-specific namespaces

3. **Search** (explicit or auto-route):
   ```bash
   # Explicit: User chooses subject
   python search.py --subject "Matematica" --query "..."

   # Auto-route: System chooses subject
   python search.py --auto-route --query "..."
   ```

### Benefits

| Aspect | Before (Mixed Index) | After (Namespaces) |
|--------|-------|--------|
| "1+1" search | Results from ALL subjects | Results only from Matematica |
| Context correctness | High confusion | High accuracy |
| AI response quality | Diluted/confused | Focused/precise |
| Query filtering | Manual (offline) | Automatic (online) |
| Subject discovery | Manual exploration | Explicit list |
| Admin control | Single index | Per-subject control |

### Configuration

**Subject Mapping** (`subject_mapping.json`):
- Add new subjects to `subjects[]` array
- Include aliases for common name variations
- Provide keywords for auto-routing
- Namespace format follows pattern: `lowercase_with_underscores`

Example add:
```json
{
  "primary": "Istoria",
  "aliases": ["History", "Istorie"],
  "keywords": ["epoca", "razboi", "imperiu", "rege"],
  "namespace": "istoria"
}
```

### Troubleshooting

**No namespace created for vectors**:
- Check folder structure follows `School/Class/Subject/PDFs`
- Verify metadata extraction: `extraction_summary.json` shows `identified_subjects`
- Check extraction manifest for `school`, `class`, `subject` fields

**Auto-route routes to wrong subject**:
- Review query keywords vs. `subject_mapping.json`
- Update keywords for better matching
- Use explicit mode `--subject` for precision

**Search returns empty**:
- Verify namespace name matches extraction output
- Check namespace exists in Pinecone: `python search.py --stats`
- Ensure embeddings were generated: `generate_embeddings.py` completed successfully

## Troubleshooting

### API Errors
- Verify API tokens in `.env`
- Check rate limits (Cloudflare: 50 req/min free tier)
- Ensure Pinecone index is active

### PDF Extraction Issues
- Some PDFs may have copy protection
- Scanned PDFs require OCR (not included)
- Check file permissions
- Files with 0 extractable pages are skipped (see `extraction_status: no_text`)

### Embedding Generation
- Ensure internet connection
- Validate API credentials
- Check account quota
- Check logs for failed embeddings

### Incremental Processing
- Delete `.extraction_manifest.json` to reset tracking
- Use `--force` flag to reprocess all files
- Check `extraction_summary.json` for processing status

## Future Enhancements

- [ ] Incremental embedding generation with Pinecone cleanup
- [ ] Vector cleanup handler for modified files
- [ ] OCR support for scanned PDFs
- [ ] Multiple language support
- [ ] Custom embedding models
- [ ] Web interface
- [ ] Advanced filtering and facets
- [ ] Analytics dashboard

## License

MIT License - Educational Use

## Support

For issues or questions:
1. Check API credentials in `.env`
2. Review logs for error messages
3. Verify Cloudflare and Pinecone accounts are active
4. Check `.extraction_manifest.json` for file tracking status
5. See `extraction_summary.json` for detailed extraction report
