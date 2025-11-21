"""
Extract text content from PDF files
Supports batch processing of multiple PDFs with CLI arguments
"""

import os
import json
import logging
import argparse
import sys
from pathlib import Path
from PyPDF2 import PdfReader
import hashlib
from datetime import datetime
from config import PDF_SOURCE_DIR, EXTRACTED_TEXT_DIR, LOG_LEVEL

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PDFExtractor:
    """Extract text from PDF files with incremental processing"""

    MANIFEST_FILE = ".extraction_manifest.json"

    def __init__(self, source_dir=PDF_SOURCE_DIR, output_dir=EXTRACTED_TEXT_DIR):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_files = []
        self.manifest_path = self.output_dir / self.MANIFEST_FILE
        self.manifest = self.load_manifest()
        self.identified_subjects = set()

    def parse_subject_from_path(self, pdf_path):
        """
        Extract school, class, and subject from PDF path hierarchy

        Expected structure:
        materiale_didactice/School/Class/Subject/document.pdf
        e.g., materiale_didactice/Scoala_Normala/clasa_0/Matematica/file.pdf

        Args:
            pdf_path: Path object of the PDF file

        Returns:
            dict: {school: str, class: str, subject: str} or {school: None, class: None, subject: None}
        """
        try:
            relative_path = pdf_path.relative_to(self.source_dir)
            parts = relative_path.parts

            # Expected structure: [school, class, subject, filename.pdf]
            if len(parts) >= 3:
                school = parts[0]
                class_name = parts[1]
                subject = parts[2]
                return {
                    'school': school,
                    'class': class_name,
                    'subject': subject
                }
            else:
                logger.warning(f"PDF doesn't follow expected hierarchy: {relative_path}")
                return {
                    'school': None,
                    'class': None,
                    'subject': None
                }
        except Exception as e:
            logger.error(f"Error parsing subject from path {pdf_path}: {e}")
            return {
                'school': None,
                'class': None,
                'subject': None
            }

    def extract_text_from_pdf(self, pdf_path):
        """
        Extract all text from a PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            dict: {pages: int, text: str, metadata: dict, extraction_status: str}
        """
        try:
            reader = PdfReader(pdf_path)
            text_content = []
            num_pages = len(reader.pages)
            extraction_status = None
            error_log = None

            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    # Guard against None (e.g., scanned PDFs, corrupted pages)
                    if text and text.strip():
                        text_content.append({
                            'page': page_num,
                            'content': text
                        })
                    elif not text:
                        logger.debug(f"Page {page_num} from {pdf_path.name}: no extractable text (scanned?)")
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num} from {pdf_path.name}: {e}")

            # Combine all text
            full_text = "\n".join([p['content'] for p in text_content])

            # Parse subject information from path hierarchy
            subject_info = self.parse_subject_from_path(pdf_path)
            if subject_info['subject']:
                self.identified_subjects.add(subject_info['subject'])

            result = {
                'pages': num_pages,
                'text': full_text,
                'extracted_pages': len(text_content),
                'metadata': {
                    'source_file': pdf_path.name,
                    'source_path': str(pdf_path),
                    'school': subject_info['school'],
                    'class': subject_info['class'],
                    'subject': subject_info['subject']
                }
            }

            if reader.metadata:
                result['metadata']['pdf_title'] = reader.metadata.get('/Title', 'Unknown')
                result['metadata']['pdf_author'] = reader.metadata.get('/Author', 'Unknown')

            logger.info(f"Extracted {len(text_content)} pages from {pdf_path.name} [{extraction_status}]")
            return result

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return None

    def load_manifest(self):
        """Load extraction manifest or create new one"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                logger.info(f"Loaded manifest with {len(manifest.get('files', {}))} tracked files")
                return manifest
            except Exception as e:
                logger.warning(f"Error loading manifest: {e}. Creating new manifest.")
                return self._create_new_manifest()
        return self._create_new_manifest()

    def _create_new_manifest(self):
        """Create new manifest structure"""
        return {
            'extraction_version': '1.1',
            'last_updated': datetime.now().isoformat(),
            'files': {}
        }

    def save_manifest(self):
        """Save manifest to disk"""
        self.manifest['last_updated'] = datetime.now().isoformat()
        try:
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, ensure_ascii=False, indent=2)
            logger.info(f"Manifest saved with {len(self.manifest['files'])} files")
        except Exception as e:
            logger.error(f"Error saving manifest: {e}")

    def calculate_file_hash(self, pdf_path):
        """Calculate MD5 hash of PDF file for change detection"""
        try:
            hash_md5 = hashlib.md5()
            with open(pdf_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {pdf_path}: {e}")
            return None

    def should_process_file(self, pdf_path, force=False):
        """Determine if file should be processed based on hash comparison"""
        if force:
            return True, "Force reprocessing"

        relative_path = str(pdf_path.relative_to(self.source_dir))
        current_hash = self.calculate_file_hash(pdf_path)

        if not current_hash:
            return False, "Failed to calculate file hash"

        if relative_path not in self.manifest['files']:
            return True, "New file"

        stored_info = self.manifest['files'][relative_path]
        stored_hash = stored_info.get('source_hash')

        if stored_hash != current_hash:
            return True, "File modified (hash changed)"

        return False, "File unchanged"

    def extract_specific_folders(self, school_folders):
        """
        Extract from specific school folders

        Args:
            school_folders: list of folder names to process
                          e.g., ['Scoala_de_Muzica_George_Enescu', 'Scoala_Normala']
        """
        found_pdfs = []

        for folder_name in school_folders:
            folder_path = self.source_dir / folder_name
            if not folder_path.exists():
                logger.warning(f"Folder not found: {folder_path}")
                continue

            pdf_files = list(folder_path.rglob('*.pdf'))
            logger.info(f"Found {len(pdf_files)} PDFs in {folder_name}")
            found_pdfs.extend(pdf_files)

        return found_pdfs

    def extract_all(self, specific_folders=None, limit=None, incremental=False, force=False):
        """
        Extract text from all PDFs in source directory

        Args:
            specific_folders: list of specific folder names to process
                            if None, process all PDFs
            limit: maximum number of PDFs to process

        Returns:
            dict: {total_files: int, successful: int, failed: int, files: list}
        """
        if specific_folders:
            pdf_files = self.extract_specific_folders(specific_folders)
        else:
            pdf_files = list(self.source_dir.rglob('*.pdf'))

        # Apply limit if specified
        if limit:
            pdf_files = pdf_files[:limit]

        logger.info(f"Found {len(pdf_files)} PDF files")

        # Filter files if incremental mode
        files_to_process = []
        skipped_files = []

        if incremental and not force:
            logger.info("Running in incremental mode - checking for changes")
            for pdf_path in pdf_files:
                should_process, reason = self.should_process_file(pdf_path, force=force)
                if should_process:
                    files_to_process.append(pdf_path)
                else:
                    skipped_files.append((pdf_path, reason))
            logger.info(f"Processing {len(files_to_process)} new/modified files, skipping {len(skipped_files)} unchanged")
        else:
            files_to_process = pdf_files
            if force:
                logger.info("Force reprocessing all files")
            else:
                logger.info(f"Processing all {len(files_to_process)} files")

        successful = 0
        failed = 0
        no_text = 0
        results = []

        for pdf_path in files_to_process:
            result = self.extract_text_from_pdf(pdf_path)

            if result:
                successful += 1

                # Save individual extraction, preserving folder structure to avoid filename collisions
                # E.g., materiale_didactice/Folder1/subfolder/file.pdf → extracted_texts/Folder1/subfolder/file_extracted.json
                relative_path = pdf_path.relative_to(self.source_dir)
                output_path = self.output_dir / relative_path.parent / f"{relative_path.stem}_extracted.json"
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                results.append({
                    'file': relative_path.name,
                    'path': str(relative_path),
                    'pages': result['pages'],
                    'extracted_pages': result['extracted_pages'],
                    'text_length': len(result['text']),
                    'output_file': str(output_path)
                })

                # Update manifest with file tracking and subject information
                relative_path_str = str(relative_path)
                source_hash = self.calculate_file_hash(pdf_path)
                extracted_hash = hashlib.md5(result['text'].encode()).hexdigest()

                self.manifest['files'][relative_path_str] = {
                    'source_hash': source_hash,
                    'extracted_hash': extracted_hash,
                    'extracted_pages': result['extracted_pages'],
                    'total_pages': result['pages'],
                    'extraction_status': result.get('extraction_status', 'success'),
                    'school': result['metadata'].get('school'),
                    'class': result['metadata'].get('class'),
                    'subject': result['metadata'].get('subject'),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                failed += 1

        summary = {
            'total_files': len(pdf_files),
            'successful': successful,
            'failed': failed,
            'identified_subjects': sorted(list(self.identified_subjects)),
            'output_directory': str(self.output_dir),
            'files': results
        }

        # Save summary
        summary_path = self.output_dir / 'extraction_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # Save manifest
        self.save_manifest()

        logger.info(f"Extraction complete: {successful} successful, {failed} failed")
        logger.info(f"Summary saved to {summary_path}")
        logger.info(f"Manifest saved to {self.manifest_path}")

        return summary


def main():
    """Main entry point for PDF extraction with CLI argument support"""

    # Setup argument parser
    parser = argparse.ArgumentParser(
        description='Extract text from PDF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extract_pdfs.py                    # Default: process 2 school folders
  python extract_pdfs.py --all              # Process all folders in materiale_didactice
  python extract_pdfs.py --folders Scoala_de_Muzica_George_Enescu  # Process specific folder
  python extract_pdfs.py --folders Folder1 Folder2 Folder3         # Process multiple folders
  python extract_pdfs.py --limit 50         # Process max 50 PDFs from default folders
        """
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all folders in materiale_didactice (default: only 2 school folders)'
    )
    parser.add_argument(
        '--folders',
        nargs='+',
        help='Specify which folders to process (e.g., --folders Scoala_de_Muzica_George_Enescu Scoala_Normala)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of PDFs to process'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only process new/modified files (requires previous run)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reprocessing of all files even if unchanged'
    )

    args = parser.parse_args()

    # Determine which folders to process
    specific_folders = None

    if args.folders:
        # User specified folders
        specific_folders = args.folders
        logger.info(f"Processing specified folders: {args.folders}")
    elif args.all:
        # Process all folders
        logger.info("Processing all folders in materiale_didactice")
        specific_folders = None  # Will process everything
    else:
        # Default behavior: process 2 school folders
        specific_folders = [
            'Scoala_de_Muzica_George_Enescu',
            'Scoala_Normala'
        ]
        logger.info(f"Processing default folders: {specific_folders}")

    # Create extractor and process
    extractor = PDFExtractor()
    summary = extractor.extract_all(
        specific_folders=specific_folders,
        limit=args.limit,
        incremental=args.incremental,
        force=args.force
    )

    # Print summary
    print("\n" + "="*60)
    print("PDF EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total files processed: {summary['total_files']}")
    print(f"Successful extractions: {summary['successful']}")
    print(f"Failed extractions: {summary['failed']}")
    if summary.get('identified_subjects'):
        print(f"Identified subjects: {', '.join(summary['identified_subjects'])}")
    if summary.get('no_text_files', 0) > 0:
        print(f"No-text files (skipped): {summary['no_text_files']}")
    if summary.get('skipped', 0) > 0:
        print(f"Unchanged files (skipped): {summary['skipped']}")
    if args.limit:
        print(f"(Limited to: {args.limit} PDFs)")
    if args.incremental:
        print(f"Mode: INCREMENTAL")
    if args.force:
        print(f"Mode: FORCE REPROCESS")
    print(f"Output directory: {summary['output_directory']}")
    print("="*60 + "\n")

    return summary


if __name__ == '__main__':
    main()
