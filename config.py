"""
Configuration file for Cloudflare Embeddings Processor
Store your API keys securely
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Cloudflare Configuration
CLOUDFLARE_API_TOKEN = os.getenv('CLOUDFLARE_API_TOKEN', 'your_cloudflare_api_token_here')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID', 'your_account_id_here')

# Pinecone Configuration
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY', 'your_pinecone_api_key_here')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT', 'us-east-1')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'educational-ai')

# File paths
PDF_SOURCE_DIR = os.getenv('PDF_SOURCE_DIR', './materiale_didactice')
EXTRACTED_TEXT_DIR = os.getenv('EXTRACTED_TEXT_DIR', './extracted_texts')

# Processing Configuration
CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 100  # overlap between chunks
EMBEDDING_DIMENSION = 768  # Cloudflare AI generates 768-dim embeddings
BATCH_SIZE = 32  # Pinecone batch size

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Validate critical configuration
def validate_config():
    """Validate that required configuration is present"""
    if CLOUDFLARE_API_TOKEN == 'your_cloudflare_api_token_here':
        print("WARNING: CLOUDFLARE_API_TOKEN not set in environment")
    if PINECONE_API_KEY == 'your_pinecone_api_key_here':
        print("WARNING: PINECONE_API_KEY not set in environment")
    return True
