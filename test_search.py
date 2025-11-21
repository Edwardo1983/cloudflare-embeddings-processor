# -*- coding: utf-8 -*-
"""
Test search functionality against Pinecone index
Validates that embeddings are correctly stored and searchable

SETUP REQUIRED:
1. Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in .env
2. Set PINECONE_API_KEY in .env
3. Run generate_embeddings.py first to populate the index
"""

import sys
import io

# Force UTF-8 encoding for Windows console compatibility
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import logging
import time
import os
import argparse
from typing import List
from pathlib import Path

# Only import these if API keys are configured
try:
    from generate_embeddings import CloudflareEmbedder, PineconeIndexManager
    APIS_AVAILABLE = True
except ImportError:
    APIS_AVAILABLE = False

from config import LOG_LEVEL

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SearchTester:
    """Test search functionality"""

    def __init__(self):
        if not APIS_AVAILABLE:
            raise RuntimeError("API libraries not available. Install from requirements.txt")

        self.embedder = CloudflareEmbedder()
        self.pinecone_manager = PineconeIndexManager()

    def search_query(self, query: str, top_k: int = 5) -> List[dict]:
        """
        Search for similar documents

        Args:
            query: Search query text
            top_k: Number of top results to return

        Returns:
            list: Search results with metadata and scores
        """
        try:
            logger.info(f"Generating embedding for query: '{query}'")
            query_embedding = self.embedder.generate_embedding(query)

            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            logger.info(f"Searching for top {top_k} results...")
            results = self.pinecone_manager.search(query_embedding, top_k=top_k)

            return results

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def test_searches(self, test_queries: List[str], top_k: int = 5):
        """
        Run multiple search tests

        Args:
            test_queries: List of query strings to test
            top_k: Number of results per query
        """
        print("\n" + "="*80)
        print("SEARCH FUNCTIONALITY TEST")
        print("="*80 + "\n")

        results_summary = []

        for i, query in enumerate(test_queries, 1):
            print(f"Test {i}/{len(test_queries)}")
            print(f"Query: '{query}'")
            print("-" * 80)

            results = self.search_query(query, top_k=top_k)

            if results:
                # Sort results by score descending to ensure correct ranking
                sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
                print(f"Found {len(sorted_results)} results:\n")

                for rank, result in enumerate(sorted_results, 1):
                    metadata = result.get('metadata', {})
                    score = result.get('score', 0)
                    text_preview = metadata.get('text', '')[:100]

                    print(f"  Rank {rank} (Score: {score:.4f})")
                    print(f"    Source: {metadata.get('source_file', 'Unknown')}")
                    print(f"    Chunk: {metadata.get('chunk_index', 'N/A')}")
                    print(f"    Preview: {text_preview}...")
                    print()

                results_summary.append({
                    'query': query,
                    'results_found': len(sorted_results),
                    'top_score': sorted_results[0].get('score', 0) if sorted_results else 0,
                    'status': 'SUCCESS'
                })
            else:
                print("No results found or search failed.\n")
                results_summary.append({
                    'query': query,
                    'results_found': 0,
                    'top_score': 0,
                    'status': 'FAILED'
                })

            print("="*80 + "\n")
            time.sleep(1)  # Delay between searches

        # Print summary
        print("SEARCH TEST SUMMARY")
        print("="*80)
        for result in results_summary:
            # Use ASCII symbols for Windows compatibility (avoid Unicode encoding issues)
            status_symbol = "[OK]" if result['status'] == 'SUCCESS' else "[FAIL]"
            print(f"{status_symbol} Query: '{result['query']}'")
            print(f"  Results: {result['results_found']}, Top Score: {result['top_score']:.4f}")
        print("="*80 + "\n")

        return results_summary

    def test_index_stats(self):
        """Display index statistics"""
        print("\n" + "="*80)
        print("INDEX STATISTICS")
        print("="*80 + "\n")

        stats = self.pinecone_manager.get_index_stats()

        if stats:
            print(f"Index Name: {stats.get('index_name', 'Unknown')}")
            print(f"Dimension: {stats.get('dimension', 'Unknown')}")
            print(f"Total Vectors: {stats.get('total_vector_count', 0):,}")
            print(f"Index Size: {stats.get('index_fullness', 0):.2%}")

            namespace_stats = stats.get('namespaces', {}).get('', {})
            print(f"Vectors in Default Namespace: {namespace_stats.get('vector_count', 0):,}")

            print("\n" + "="*80 + "\n")
            return stats
        else:
            print("Failed to retrieve index statistics\n")
            return None


class ExtractionValidator:
    """Validate PDF extraction results without requiring APIs"""

    def __init__(self, extracted_dir='./extracted_texts'):
        self.extracted_dir = Path(extracted_dir)

    def validate_extractions(self):
        """Validate extracted JSON files"""
        print("\n" + "="*80)
        print("EXTRACTION VALIDATION")
        print("="*80 + "\n")

        if not self.extracted_dir.exists():
            print(f"[ERROR] Extraction directory not found: {self.extracted_dir}")
            return None

        json_files = list(self.extracted_dir.rglob('*_extracted.json'))
        print(f"Found {len(json_files)} extracted files\n")

        total_pages = 0
        total_text_length = 0
        valid_files = 0
        invalid_files = 0

        for json_file in json_files[:10]:  # Show first 10
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                pages = data.get('pages', 0)
                extracted_pages = data.get('extracted_pages', 0)
                text_length = len(data.get('text', ''))

                total_pages += extracted_pages
                total_text_length += text_length
                valid_files += 1

                status = "[OK]" if extracted_pages > 0 else "[WARN]"
                print(f"{status} {json_file.name}")
                print(f"   Pages: {extracted_pages}/{pages}, Text: {text_length:,} chars")

            except Exception as e:
                print(f"[ERROR] {json_file.name}: {e}")
                invalid_files += 1

        print(f"\n{'-'*80}")
        print(f"Valid files: {valid_files}")
        print(f"Invalid files: {invalid_files}")
        print(f"Total pages extracted (first 10): {total_pages}")
        print(f"Total text length (first 10): {total_text_length:,} characters")
        print("="*80 + "\n")

        return {
            'total_files': len(json_files),
            'valid_files': valid_files,
            'invalid_files': invalid_files,
            'sample_total_pages': total_pages,
            'sample_text_length': total_text_length
        }


def main():
    """Main test entry point with CLI arguments"""

    # Setup argument parser
    parser = argparse.ArgumentParser(
        description='Test search functionality and validate extractions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_search.py                    # Use default extracted_texts dir
  python test_search.py --extracted-dir ./custom_extraction  # Use custom dir
  python test_search.py --help             # Show this help message
        """
    )

    parser.add_argument(
        '--extracted-dir',
        default='./extracted_texts',
        help='Path to extracted texts directory (default: ./extracted_texts)'
    )

    args = parser.parse_args()

    # First, validate extractions (no API needed)
    validator = ExtractionValidator(args.extracted_dir)
    extraction_stats = validator.validate_extractions()

    # If extraction is valid and APIs are available, test search
    if extraction_stats and extraction_stats['valid_files'] > 0:
        try:
            tester = SearchTester()

            # Display index stats
            tester.test_index_stats()

            # Define test queries - optimized for educational content
            test_queries = [
                "muzica clasica si educatie",
                "metode de predare si pedagogie",
                "dezvoltarea inteligentei copilului",
                "arte vizuale si practica",
                "curriculum si competente"
            ]

            # Run tests
            test_results = tester.test_searches(test_queries, top_k=3)

            # Summary statistics
            successful_tests = sum(1 for r in test_results if r['status'] == 'SUCCESS')
            total_results = sum(r['results_found'] for r in test_results)

            print("\nOVERALL TEST RESULTS")
            print("="*80)
            print(f"Total queries tested: {len(test_results)}")
            print(f"Successful searches: {successful_tests}/{len(test_results)}")
            print(f"Total results retrieved: {total_results}")
            print("="*80 + "\n")

            return test_results

        except Exception as e:
            print(f"\n{'='*80}")
            print("SEARCH TESTING SKIPPED")
            print("="*80)
            print(f"Reason: {e}")
            print("\nTo enable search testing:")
            print("1. Configure CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in .env")
            print("2. Configure PINECONE_API_KEY in .env")
            print("3. Run: python generate_embeddings.py")
            print(f"{'='*80}\n")

    else:
        print("\n" + "="*80)
        print("EXTRACTION VALIDATION FAILED")
        print("="*80)
        print(f"No valid extracted files found in: {args.extracted_dir}")
        print("Run: python extract_pdfs.py")
        print("="*80 + "\n")


if __name__ == '__main__':
    main()
