"""
PDF Parsing Service
Extracts text and structured data from PDF documents using pdfplumber and pypdf.
"""

import pdfplumber
from pypdf import PdfReader
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PDFParsingService:
    """
    Service for parsing and extracting data from PDF files.
    Handles both text extraction and structured data parsing.
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
    def extract_structured_data(pdf_text: str) -> Dict:
        """
        Parse extracted PDF text into structured resume data.
        This is a basic parser; can be enhanced with ML/NLP models.
        
        Args:
            pdf_text: Raw text extracted from PDF
            
        Returns:
            Dictionary with structured resume data
        """
        sections = {
            "full_text": pdf_text,
            "contact_info": PDFParsingService._extract_contact_info(pdf_text),
            "summary": PDFParsingService._extract_summary(pdf_text),
            "experience": PDFParsingService._extract_experience(pdf_text),
            "skills": PDFParsingService._extract_skills(pdf_text),
            "education": PDFParsingService._extract_education(pdf_text),
        }
        return sections

    @staticmethod
    def _extract_contact_info(text: str) -> Dict:
        """Extract contact information from resume text."""
        import re

        contact = {}
        
        # Email pattern
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if email_match:
            contact["email"] = email_match.group()
        
        # Phone pattern (US format)
        phone_match = re.search(r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phone_match:
            contact["phone"] = phone_match.group()
        
        # URL pattern
        url_match = re.search(r"https?://[\w\.-]+", text)
        if url_match:
            contact["url"] = url_match.group()
        
        return contact

    @staticmethod
    def _extract_summary(text: str) -> Optional[str]:
        """Extract professional summary or objective."""
        import re

        # Look for sections like "Professional Summary", "Objective", etc.
        pattern = r"(professional summary|objective|executive summary)[\s\n]+(.*?)(?=\n\n|\n[A-Z]|\Z)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            return match.group(2).strip()[:500]  # Limit to 500 chars
        
        return None

    @staticmethod
    def _extract_experience(text: str) -> List[str]:
        """Extract work experience entries."""
        import re

        experiences = []
        
        # Pattern: Company Name, Job Title, Dates
        pattern = r"(^|\n)([A-Z][A-Za-z\s,\.]+)\s*\n\s*([A-Z][A-Za-z\s,]+)\s*\n\s*(.*?(?=\n\n|\n[A-Z]|\Z))"
        matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            exp_text = f"{match.group(2)} - {match.group(3)}"
            experiences.append(exp_text)
        
        return experiences[:5]  # Return top 5 experiences

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        """Extract skills section."""
        import re

        # Look for "Skills" section
        pattern = r"(skills?)[\s\n]+(.*?)(?=\n\n[A-Z]|\Z)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            skills_text = match.group(2)
            # Split by common delimiters
            skills = re.split(r"[,•\n]", skills_text)
            skills = [s.strip() for s in skills if s.strip()]
            return skills[:30]  # Return top 30 skills
        
        return []

    @staticmethod
    def _extract_education(text: str) -> List[str]:
        """Extract education entries."""
        import re

        education = []
        
        # Pattern: Degree, School, Graduation Year
        pattern = r"(^|\n)([A-Z][A-Za-z\s,\.]+(?:degree|diploma|certificate).*?)\n\s*([A-Z][A-Za-z\s,\.]+)\s*(?:\n\s*(\d{4}))?"
        matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
        
        for match in matches:
            edu_text = f"{match.group(2)} from {match.group(3)}"
            if match.group(4):
                edu_text += f" ({match.group(4)})"
            education.append(edu_text)
        
        return education[:5]  # Return top 5 education entries

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
