"""
Extract text content from PDF files
Supports batch processing of multiple PDFs
"""

import os
import json
import logging
from pathlib import Path
from PyPDF2 import PdfReader
from config import PDF_SOURCE_DIR, EXTRACTED_TEXT_DIR, LOG_LEVEL

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PDFExtractor:
    """Extract text from PDF files"""

    def __init__(self, source_dir=PDF_SOURCE_DIR, output_dir=EXTRACTED_TEXT_DIR):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_files = []

    def extract_text_from_pdf(self, pdf_path):
        """
        Extract all text from a PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            dict: {pages: int, text: str, metadata: dict}
        """
        try:
            reader = PdfReader(pdf_path)
            text_content = []
            num_pages = len(reader.pages)

            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text.strip():
                        text_content.append({
                            'page': page_num,
                            'content': text
                        })
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num} from {pdf_path.name}: {e}")

            # Combine all text
            full_text = "\n".join([p['content'] for p in text_content])

            result = {
                'pages': num_pages,
                'text': full_text,
                'extracted_pages': len(text_content),
                'metadata': {
                    'source_file': pdf_path.name,
                    'source_path': str(pdf_path),
                }
            }

            if reader.metadata:
                result['metadata']['pdf_title'] = reader.metadata.get('/Title', 'Unknown')
                result['metadata']['pdf_author'] = reader.metadata.get('/Author', 'Unknown')

            logger.info(f"Extracted {len(text_content)} pages from {pdf_path.name}")
            return result

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return None

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

    def extract_all(self, specific_folders=None):
        """
        Extract text from all PDFs in source directory

        Args:
            specific_folders: list of specific folder names to process
                            if None, process all PDFs

        Returns:
            dict: {total_files: int, successful: int, failed: int, files: list}
        """
        if specific_folders:
            pdf_files = self.extract_specific_folders(specific_folders)
        else:
            pdf_files = list(self.source_dir.rglob('*.pdf'))

        logger.info(f"Processing {len(pdf_files)} PDF files")

        successful = 0
        failed = 0
        results = []

        for pdf_path in pdf_files:
            result = self.extract_text_from_pdf(pdf_path)

            if result:
                successful += 1

                # Save individual extraction
                relative_path = pdf_path.relative_to(self.source_dir)
                output_path = self.output_dir / f"{relative_path.stem}_extracted.json"
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
            else:
                failed += 1

        summary = {
            'total_files': len(pdf_files),
            'successful': successful,
            'failed': failed,
            'output_directory': str(self.output_dir),
            'files': results
        }

        # Save summary
        summary_path = self.output_dir / 'extraction_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"Extraction complete: {successful} successful, {failed} failed")
        logger.info(f"Summary saved to {summary_path}")

        return summary


def main():
    """Main entry point for PDF extraction"""

    # Define which folders to process
    specific_folders = [
        'Scoala_de_Muzica_George_Enescu',
        'Scoala_Normala'
    ]

    extractor = PDFExtractor()
    summary = extractor.extract_all(specific_folders=specific_folders)

    print("\n" + "="*60)
    print("PDF EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total files processed: {summary['total_files']}")
    print(f"Successful extractions: {summary['successful']}")
    print(f"Failed extractions: {summary['failed']}")
    print(f"Output directory: {summary['output_directory']}")
    print("="*60 + "\n")

    return summary


if __name__ == '__main__':
    main()
