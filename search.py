"""
Dual-interface search for educational materials with namespace isolation
Supports both explicit subject selection and auto-routing based on query keywords
"""

import json
import logging
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
from config import (
    CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_ACCOUNT_ID,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    LOG_LEVEL
)
from generate_embeddings import CloudflareEmbedder, PineconeIndexManager

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# UTF-8 support for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class SubjectRouter:
    """Route queries to appropriate subject namespaces based on keywords"""

    def __init__(self):
        self.subject_mapping = self._load_subject_mapping()

    def _load_subject_mapping(self) -> Dict:
        """Load subject mapping configuration"""
        try:
            mapping_file = Path(__file__).parent / 'subject_mapping.json'
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning("subject_mapping.json not found")
                return None
        except Exception as e:
            logger.error(f"Error loading subject mapping: {e}")
            return None

    def get_all_subjects(self) -> List[str]:
        """Get list of all available subjects"""
        if not self.subject_mapping:
            return []
        return [subj['primary'] for subj in self.subject_mapping.get('subjects', [])]

    def route_query(self, query: str, school: str, class_name: str) -> Optional[str]:
        """
        Route query to appropriate subject namespace based on keywords

        Args:
            query: User query text
            school: School name (normalized, e.g., "scoala_normala")
            class_name: Class name (normalized, e.g., "clasa_0")

        Returns:
            str: Recommended namespace or None if no match found
        """
        if not self.subject_mapping:
            logger.warning("No subject mapping available for auto-routing")
            return None

        query_lower = query.lower()
        best_match = None
        best_score = 0

        for subject_config in self.subject_mapping.get('subjects', []):
            keywords = subject_config.get('keywords', [])
            matches = sum(1 for kw in keywords if kw.lower() in query_lower)

            if matches > best_score:
                best_score = matches
                best_match = subject_config

        if best_match:
            subject_ns = best_match.get('namespace', best_match['primary'].lower().replace(' ', '_'))
            namespace = f"{school}_{class_name}_{subject_ns}"
            logger.info(f"Auto-routed to subject '{best_match['primary']}' ({matches} keyword matches)")
            return namespace
        else:
            logger.info("No matching subject found in keywords")
            return None

    def find_namespace(self, query: str, subject: str, school: str, class_name: str) -> Optional[str]:
        """
        Find namespace for explicit subject selection

        Args:
            query: User query (for logging)
            subject: Explicit subject name
            school: School name (normalized)
            class_name: Class name (normalized)

        Returns:
            str: Namespace or None if subject not found
        """
        if not self.subject_mapping:
            return None

        # Find subject by primary name or alias
        for subject_config in self.subject_mapping.get('subjects', []):
            if (subject.lower() == subject_config['primary'].lower() or
                subject.lower() in [alias.lower() for alias in subject_config.get('aliases', [])]):
                subject_ns = subject_config.get('namespace', subject.lower().replace(' ', '_'))
                namespace = f"{school}_{class_name}_{subject_ns}"
                logger.info(f"Using explicit subject namespace: {namespace}")
                return namespace

        logger.warning(f"Subject '{subject}' not found in mapping")
        return None


class DualInterfaceSearch:
    """Dual-interface search supporting both explicit and auto-route modes"""

    def __init__(self):
        self.embedder = CloudflareEmbedder()
        self.pinecone_manager = PineconeIndexManager()
        self.router = SubjectRouter()

    def search_with_subject(self, query: str, subject: str, school: str = "scoala_normala",
                           class_name: str = "clasa_0", top_k: int = 5) -> List[Dict]:
        """
        Search with explicit subject selection

        Args:
            query: Search query
            subject: Subject name (e.g., "Matematica")
            school: School name (defaults to "scoala_normala")
            class_name: Class name (defaults to "clasa_0")
            top_k: Number of results to return

        Returns:
            list: Search results with relevance scores
        """
        logger.info(f"Explicit search - Subject: {subject}, Query: {query}")

        # Find namespace for subject
        namespace = self.router.find_namespace(query, subject, school.lower().replace(' ', '_'),
                                               class_name.lower().replace(' ', '_'))

        if not namespace:
            logger.error(f"Could not find namespace for subject: {subject}")
            return []

        # Generate embedding for query
        query_embedding = self.embedder.generate_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []

        # Search in the specific namespace
        results = self.pinecone_manager.search(query_embedding, top_k=top_k, namespace=namespace)
        logger.info(f"Found {len(results)} results in {subject}")

        return results

    def search_with_auto_route(self, query: str, school: str = "scoala_normala",
                              class_name: str = "clasa_0", top_k: int = 5) -> Dict:
        """
        Search with auto-routing based on query keywords

        Args:
            query: Search query
            school: School name (defaults to "scoala_normala")
            class_name: Class name (defaults to "clasa_0")
            top_k: Number of results to return

        Returns:
            dict: {subject: str, results: list, confidence: float}
        """
        logger.info(f"Auto-route search - Query: {query}")

        # Normalize school and class
        school_norm = school.lower().replace(' ', '_')
        class_norm = class_name.lower().replace(' ', '_')

        # Route to subject based on keywords
        namespace = self.router.route_query(query, school_norm, class_norm)

        if not namespace:
            logger.warning("No matching subject found, searching default namespace")
            # Fall back to default namespace (all subjects)
            results = self._search_all_namespaces(query, top_k)
            return {
                'subject': 'All Subjects',
                'results': results,
                'confidence': 0.0,
                'mode': 'fallback'
            }

        # Generate embedding for query
        query_embedding = self.embedder.generate_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return {'subject': 'Error', 'results': [], 'confidence': 0.0}

        # Search in the routed namespace
        results = self.pinecone_manager.search(query_embedding, top_k=top_k, namespace=namespace)

        # Extract subject name from namespace for display
        parts = namespace.split('_')
        subject_name = ' '.join(parts[2:]) if len(parts) > 2 else 'Unknown'

        logger.info(f"Auto-routed to '{subject_name}' with {len(results)} results")

        return {
            'subject': subject_name.title(),
            'results': results,
            'confidence': 1.0,  # Placeholder - could be improved with keyword match percentage
            'mode': 'auto_route'
        }

    def _search_all_namespaces(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search across all available subjects"""
        logger.info("Searching across all namespaces")
        query_embedding = self.embedder.generate_embedding(query)
        if not query_embedding:
            return []

        # Search default namespace (which has all vectors if no namespaces are used)
        results = self.pinecone_manager.search(query_embedding, top_k=top_k)
        return results

    def list_subjects(self) -> List[str]:
        """List all available subjects"""
        subjects = self.router.get_all_subjects()
        return subjects

    def get_index_stats(self) -> Dict:
        """Get Pinecone index statistics"""
        return self.pinecone_manager.get_index_stats()


def main():
    """Main entry point with CLI argument handling"""
    parser = argparse.ArgumentParser(
        description='Search educational materials with subject-based isolation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Explicit subject search
  python search.py --subject "Matematica" --query "How to solve equations?"

  # Auto-route based on keywords
  python search.py --auto-route --query "What is photosynthesis?"

  # List available subjects
  python search.py --list-subjects

  # Show index statistics
  python search.py --stats

  # Custom school/class
  python search.py --subject "Limba Romana" --school "Scoala_de_Muzica_George_Enescu" --class "clasa_1" --query "What is a sonnet?"
        """
    )

    parser.add_argument(
        '--subject',
        help='Explicit subject name (e.g., "Matematica", "Limba Romana")'
    )
    parser.add_argument(
        '--query',
        help='Search query'
    )
    parser.add_argument(
        '--auto-route',
        action='store_true',
        help='Auto-route query to subject based on keywords'
    )
    parser.add_argument(
        '--school',
        default='Scoala_Normala',
        help='School name (default: Scoala_Normala)'
    )
    parser.add_argument(
        '--class',
        dest='class_name',
        default='clasa_0',
        help='Class name (default: clasa_0)'
    )
    parser.add_argument(
        '--top-k',
        type=int,
        default=5,
        help='Number of results to return (default: 5)'
    )
    parser.add_argument(
        '--list-subjects',
        action='store_true',
        help='List all available subjects'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show Pinecone index statistics'
    )

    args = parser.parse_args()

    # Initialize search interface
    search = DualInterfaceSearch()

    # Handle different commands
    if args.list_subjects:
        subjects = search.list_subjects()
        print("\nAvailable Subjects:")
        print("=" * 40)
        for subject in subjects:
            print(f"  - {subject}")
        print("=" * 40 + "\n")
        return

    if args.stats:
        stats = search.get_index_stats()
        print("\nPinecone Index Statistics:")
        print("=" * 40)
        if stats:
            print(json.dumps(stats, indent=2))
        else:
            print("Could not retrieve index statistics")
        print("=" * 40 + "\n")
        return

    if args.auto_route and args.query:
        # Auto-route mode
        result = search.search_with_auto_route(
            query=args.query,
            school=args.school,
            class_name=args.class_name,
            top_k=args.top_k
        )

        print("\n" + "=" * 60)
        print(f"SEARCH RESULTS - Subject: {result['subject']}")
        print(f"Mode: {result['mode'].upper()}")
        print("=" * 60)

        if result['results']:
            for i, match in enumerate(result['results'], 1):
                text = match.get('metadata', {}).get('text', 'N/A')
                score = match.get('score', 0)
                print(f"\n[{i}] Score: {score:.4f}")
                print(f"Content: {text[:300]}...")
        else:
            print("No results found.")

        print("=" * 60 + "\n")
        return

    if args.subject and args.query:
        # Explicit subject mode
        results = search.search_with_subject(
            query=args.query,
            subject=args.subject,
            school=args.school,
            class_name=args.class_name,
            top_k=args.top_k
        )

        print("\n" + "=" * 60)
        print(f"SEARCH RESULTS - Subject: {args.subject}")
        print(f"Query: {args.query}")
        print("=" * 60)

        if results:
            for i, match in enumerate(results, 1):
                text = match.get('metadata', {}).get('text', 'N/A')
                score = match.get('score', 0)
                print(f"\n[{i}] Score: {score:.4f}")
                print(f"Content: {text[:300]}...")
        else:
            print("No results found.")

        print("=" * 60 + "\n")
        return

    # No valid mode selected
    parser.print_help()


if __name__ == '__main__':
    main()
