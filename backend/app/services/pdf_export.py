"""
PDF Export Service
Generates PDF files from markdown-formatted resume text using markdown_pdf.
"""

import logging
from io import BytesIO
from typing import Optional

from markdown_pdf import MarkdownPdf, Section

logger = logging.getLogger(__name__)


class PDFExportService:
    """
    Service for generating PDF files from resume text content.
    Uses markdown_pdf to convert markdown-formatted resumes to clean PDFs.
    """

    @staticmethod
    def generate_pdf(resume_text: str, filename: Optional[str] = None) -> BytesIO:
        """
        Generate a PDF file from markdown-formatted resume text.

        Args:
            resume_text: The resume content (markdown text)
            filename: Optional filename for the PDF (unused, kept for compat)

        Returns:
            BytesIO object containing the PDF data
        """
        try:
            pdf = MarkdownPdf(toc_level=0)

            # Use US Letter paper size (resume standard)
            pdf.add_section(
                Section(
                    resume_text,
                    toc=False,
                    paper_size="Letter",
                )
            )

            buffer = BytesIO()
            pdf.save_bytes(buffer)
            buffer.seek(0)

            logger.info("PDF generated successfully (%d chars)", len(resume_text))
            return buffer

        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise


