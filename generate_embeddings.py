"""
Generate embeddings using Cloudflare AI and store in Pinecone
Supports batch processing and efficient vector storage
"""

import json
import logging
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
import requests
from pinecone import Pinecone, ServerlessSpec
from config import (
    CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_ACCOUNT_ID,
    PINECONE_API_KEY,
    PINECONE_ENVIRONMENT,
    PINECONE_INDEX_NAME,
    EXTRACTED_TEXT_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_DIMENSION,
    BATCH_SIZE,
    LOG_LEVEL
)

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudflareEmbedder:
    """Generate embeddings using Cloudflare AI"""

    def __init__(self, api_token=CLOUDFLARE_API_TOKEN, account_id=CLOUDFLARE_ACCOUNT_ID):
        self.api_token = api_token
        self.account_id = account_id
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
        self.model = "@cf/baai/bge-base-en-v1.5"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.request_count = 0
        self.total_tokens_used = 0

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Cloudflare AI

        Args:
            text: Input text to embed

        Returns:
            list: Embedding vector (768 dimensions)
        """
        try:
            # Clean and prepare text
            text = text.strip()
            if not text:
                logger.warning("Empty text provided for embedding")
                return None

            payload = {
                "text": text
            }

            response = requests.post(
                f"{self.base_url}/{self.model}",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                self.request_count += 1

                # Extract embedding from response
                if 'result' in result and 'data' in result['result']:
                    embedding = result['result']['data'][0]
                    return embedding
                else:
                    logger.error(f"Unexpected response format: {result}")
                    return None
            else:
                logger.error(f"API error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def generate_embeddings_batch(self, texts: List[str]) -> List[Tuple[int, str, List[float]]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of text strings

        Returns:
            list: List of (index, text, embedding) tuples - preserves original index for sync
        """
        results = []
        for i, text in enumerate(texts):
            embedding = self.generate_embedding(text)
            if embedding:
                results.append((i, text, embedding))  # Include original index for metadata sync
                if (i + 1) % 10 == 0:
                    logger.info(f"Generated {i + 1}/{len(texts)} embeddings")
                time.sleep(0.1)  # Rate limiting
            else:
                logger.warning(f"Failed to generate embedding for chunk {i} (skipping to prevent metadata misalignment)")

        return results


class TextChunker:
    """Split text into overlapping chunks"""

    def __init__(self, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into chunks with overlap

        Args:
            text: Input text to chunk
            metadata: Additional metadata for chunks

        Returns:
            list: List of {text, metadata, chunk_index} dicts
        """
        chunks = []
        step = self.chunk_size - self.overlap

        for i in range(0, len(text), step):
            chunk = text[i:i + self.chunk_size]
            if len(chunk.strip()) > 50:  # Skip very small chunks
                chunk_metadata = metadata.copy() if metadata else {}
                chunk_metadata['chunk_index'] = len(chunks)
                chunk_metadata['chunk_size'] = len(chunk)

                chunks.append({
                    'text': chunk,
                    'metadata': chunk_metadata,
                    'chunk_index': len(chunks)
                })

        return chunks


class PineconeIndexManager:
    """Manage Pinecone index operations"""

    def __init__(self, api_key=PINECONE_API_KEY, index_name=PINECONE_INDEX_NAME):
        self.api_key = api_key
        self.index_name = index_name
        self.pc = Pinecone(api_key=api_key)
        self.index = None
        self._ensure_index_exists()

    def _ensure_index_exists(self):
        """Create index if it doesn't exist"""
        try:
            # Check if index exists
            indexes = self.pc.list_indexes()
            index_names = [idx['name'] for idx in indexes.get('indexes', [])]

            if self.index_name not in index_names:
                logger.info(f"Creating index '{self.index_name}'...")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=EMBEDDING_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                logger.info("Index created successfully")
                time.sleep(5)  # Wait for index to be ready

            self.index = self.pc.Index(self.index_name)
            logger.info(f"Connected to index '{self.index_name}'")

        except Exception as e:
            logger.error(f"Error managing index: {e}")
            raise

    def upsert_vectors(self, vectors: List[Tuple[str, List[float], Dict]], batch_size=BATCH_SIZE, namespace=None):
        """
        Upload vectors to Pinecone index

        Args:
            vectors: List of (id, embedding, metadata) tuples
            batch_size: Batch size for upsert
            namespace: Optional namespace for vector isolation (None = default namespace)
        """
        try:
            total_upserted = 0

            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]

                # Format for Pinecone
                upsert_data = [
                    {
                        'id': vec_id,
                        'values': embedding,
                        'metadata': metadata
                    }
                    for vec_id, embedding, metadata in batch
                ]

                if namespace:
                    self.index.upsert(vectors=upsert_data, namespace=namespace)
                else:
                    self.index.upsert(vectors=upsert_data)

                total_upserted += len(batch)
                logger.info(f"Upserted {total_upserted}/{len(vectors)} vectors to namespace '{namespace if namespace else 'default'}'")
                time.sleep(0.5)  # Rate limiting

        except Exception as e:
            logger.error(f"Error upserting vectors: {e}")
            raise

    def search(self, query_embedding: List[float], top_k=5, namespace=None) -> List[Dict]:
        """
        Search similar vectors in Pinecone

        Args:
            query_embedding: Query embedding vector
            top_k: Number of top results to return
            namespace: Optional namespace to search in (None = default namespace)

        Returns:
            list: Search results with scores
        """
        try:
            if namespace:
                results = self.index.query(
                    vector=query_embedding,
                    top_k=top_k,
                    include_metadata=True,
                    namespace=namespace
                )
            else:
                results = self.index.query(
                    vector=query_embedding,
                    top_k=top_k,
                    include_metadata=True
                )
            return results.get('matches', [])
        except Exception as e:
            logger.error(f"Error searching index: {e}")
            return []

    def get_index_stats(self):
        """Get index statistics"""
        try:
            return self.index.describe_index_stats()
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return None


class EmbeddingPipeline:
    """Complete pipeline for extraction, chunking, embedding, and storage with namespace isolation"""

    def __init__(self):
        self.embedder = CloudflareEmbedder()
        self.chunker = TextChunker()
        self.pinecone_manager = PineconeIndexManager()
        self.extracted_dir = Path(EXTRACTED_TEXT_DIR)
        self.subject_mapping = self._load_subject_mapping()
        self.namespaces_created = set()

    def _load_subject_mapping(self) -> Dict:
        """Load subject mapping configuration"""
        try:
            mapping_file = Path(__file__).parent / 'subject_mapping.json'
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning("subject_mapping.json not found, using namespace-less mode")
                return None
        except Exception as e:
            logger.error(f"Error loading subject mapping: {e}")
            return None

    def _calculate_namespace(self, metadata: Dict) -> str:
        """
        Calculate Pinecone namespace from metadata

        Expected format: {school}_{class}_{subject}
        e.g., scoala_normala_clasa_0_matematica

        Args:
            metadata: Document metadata with school, class, subject fields

        Returns:
            str: Normalized namespace name or None
        """
        school = metadata.get('school', '').lower().replace(' ', '_')
        class_name = metadata.get('class', '').lower().replace(' ', '_')
        subject = metadata.get('subject', '').lower().replace(' ', '_')

        if school and class_name and subject:
            namespace = f"{school}_{class_name}_{subject}"
            return namespace
        else:
            logger.warning(f"Incomplete metadata for namespace calculation: {metadata}")
            return None

    def load_extracted_texts(self, limit=None) -> List[Dict]:
        """Load extracted PDF texts"""
        extracted_files = list(self.extracted_dir.glob('**/*_extracted.json'))

        if limit:
            extracted_files = extracted_files[:limit]

        documents = []
        for file_path in extracted_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    documents.append(data)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        return documents

    def process_pipeline(self, limit=None):
        """Run complete pipeline with namespace-based isolation"""
        logger.info("Starting embedding pipeline with namespace isolation...")

        # Load extracted texts
        documents = self.load_extracted_texts(limit=limit)
        logger.info(f"Loaded {len(documents)} documents")

        # Chunk texts - include subject metadata for namespace calculation
        all_chunks = []
        for doc in documents:
            chunks = self.chunker.chunk_text(
                doc['text'],
                metadata={
                    'source_file': doc['metadata']['source_file'],
                    'source_path': doc['metadata'].get('source_path', ''),
                    'total_pages': doc['pages'],
                    'school': doc['metadata'].get('school'),
                    'class': doc['metadata'].get('class'),
                    'subject': doc['metadata'].get('subject')
                }
            )
            all_chunks.extend(chunks)

        logger.info(f"Created {len(all_chunks)} text chunks")

        # Generate embeddings (returns tuples with original indices for metadata sync)
        texts_to_embed = [chunk['text'] for chunk in all_chunks]
        text_embeddings = self.embedder.generate_embeddings_batch(texts_to_embed)

        logger.info(f"Generated {len(text_embeddings)} embeddings")

        # Prepare vectors grouped by namespace
        # IMPORTANT: Using returned indices ensures metadata stays synced even if some embeddings fail
        vectors_by_namespace = {}
        vectors_without_namespace = []

        for chunk_idx, text, embedding in text_embeddings:
            chunk_data = all_chunks[chunk_idx]  # Use returned index to access correct metadata

            # Generate deterministic ID from source file + chunk index
            # This prevents duplicate vectors when re-running the pipeline
            source_file = chunk_data['metadata'].get('source_file', 'unknown')
            id_hash = hashlib.md5(f"{source_file}_{chunk_idx}".encode()).hexdigest()[:12]
            vector_id = f"vec_{id_hash}"

            vector_metadata = {
                'text': text[:500],  # Store first 500 chars
                **chunk_data['metadata']
            }

            # Calculate namespace from metadata
            namespace = self._calculate_namespace(chunk_data['metadata'])

            if namespace:
                if namespace not in vectors_by_namespace:
                    vectors_by_namespace[namespace] = []
                vectors_by_namespace[namespace].append((vector_id, embedding, vector_metadata))
            else:
                # Fallback: store in default namespace
                vectors_without_namespace.append((vector_id, embedding, vector_metadata))

        # Upsert vectors to their respective namespaces
        total_stored = 0
        for namespace, vectors in vectors_by_namespace.items():
            logger.info(f"Upserting {len(vectors)} vectors to namespace '{namespace}'")
            self.pinecone_manager.upsert_vectors(vectors, namespace=namespace)
            self.namespaces_created.add(namespace)
            total_stored += len(vectors)

        # Upsert vectors without namespace to default namespace
        if vectors_without_namespace:
            logger.info(f"Upserting {len(vectors_without_namespace)} vectors to default namespace (incomplete metadata)")
            self.pinecone_manager.upsert_vectors(vectors_without_namespace)
            total_stored += len(vectors_without_namespace)

        # Get stats
        stats = self.pinecone_manager.get_index_stats()

        summary = {
            'documents_processed': len(documents),
            'chunks_created': len(all_chunks),
            'embeddings_generated': len(text_embeddings),
            'vectors_stored': total_stored,
            'namespaces_created': sorted(list(self.namespaces_created)),
            'vectors_in_namespaces': {ns: len(vecs) for ns, vecs in vectors_by_namespace.items()},
            'vectors_in_default': len(vectors_without_namespace),
            'index_stats': stats,
            'cloudflare_requests': self.embedder.request_count
        }

        return summary


def main():
    """Main entry point"""
    try:
        pipeline = EmbeddingPipeline()
        summary = pipeline.process_pipeline(limit=None)

        print("\n" + "="*60)
        print("EMBEDDING PIPELINE SUMMARY")
        print("="*60)
        print(f"Documents processed: {summary['documents_processed']}")
        print(f"Chunks created: {summary['chunks_created']}")
        print(f"Embeddings generated: {summary['embeddings_generated']}")
        print(f"Vectors stored: {summary['vectors_stored']}")
        print(f"Cloudflare API requests: {summary['cloudflare_requests']}")
        if summary.get('namespaces_created'):
            print(f"\nNamespaces created: {len(summary['namespaces_created'])}")
            for ns in summary['namespaces_created']:
                vec_count = summary['vectors_in_namespaces'].get(ns, 0)
                print(f"  - {ns}: {vec_count} vectors")
        if summary.get('vectors_in_default', 0) > 0:
            print(f"Vectors in default namespace: {summary['vectors_in_default']}")
        print("="*60 + "\n")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == '__main__':
    main()
