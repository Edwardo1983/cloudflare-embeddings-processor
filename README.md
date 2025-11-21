# Cloudflare Embeddings Processor

Advanced PDF processing system with AI-powered embeddings and vector search capability.

## Features

- **PDF Text Extraction**: Extract text from multiple PDFs with page tracking
- **AI Embeddings**: Generate 768-dimensional embeddings using Cloudflare AI
- **Vector Database**: Store and search embeddings in Pinecone
- **Batch Processing**: Efficient processing of large document collections
- **Educational Focus**: Optimized for Romanian educational materials

## Project Structure

```
cloudflare-embeddings-processor/
├── config.py                 # API keys and configuration
├── extract_pdfs.py          # PDF text extraction
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

```bash
python extract_pdfs.py
```

Extracts text from specific folders:
- `Scoala_de_Muzica_George_Enescu`
- `Scoala_Normala`

Output: `extracted_texts/extraction_summary.json`

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

```bash
python test_search.py
```

Tests:
- Index statistics
- 5 predefined search queries
- Result ranking and relevance

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
- `PDFExtractor` class: Handles PDF reading and text extraction
- `extract_specific_folders()`: Process specific school materials
- `extract_all()`: Batch process all PDFs
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

## Performance Metrics

- PDF extraction: ~50ms per page
- Embedding generation: ~100ms per chunk (via Cloudflare API)
- Pinecone upsert: ~10ms per batch (32 vectors)

## Troubleshooting

### API Errors
- Verify API tokens in `.env`
- Check rate limits (Cloudflare: 50 req/min free tier)
- Ensure Pinecone index is active

### PDF Extraction Issues
- Some PDFs may have copy protection
- Scanned PDFs require OCR (not included)
- Check file permissions

### Embedding Generation
- Ensure internet connection
- Validate API credentials
- Check account quota

## Future Enhancements

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
