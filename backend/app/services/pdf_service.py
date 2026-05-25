"""
PDF Parsing Service
Simple text extraction from PDF documents using pdfplumber.
AI handles all detailed analysis and parsing.
"""

import pdfplumber
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PDFParsingService:
    """
    Service for extracting text from PDF files.
    Focuses on simple text extraction - AI handles all detailed parsing.
    """

    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """
        Extract all text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            Exception: If PDF parsing fails
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise

    @staticmethod
    def validate_pdf_file(file_path: str) -> bool:
        """
        Validate that the file is a readable PDF.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages) > 0
        except Exception as e:
            logger.error(f"Invalid PDF file: {str(e)}")
            return False
