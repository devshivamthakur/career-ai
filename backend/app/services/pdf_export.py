"""
PDF Export Service
Generates PDF files from resume text using reportlab.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import logging
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


class PDFExportService:
    """
    Service for generating PDF files from resume text content.
    """

    MARGIN_SIZE = 0.75 * inch
    PAGE_WIDTH, PAGE_HEIGHT = letter

    @staticmethod
    def generate_pdf(resume_text: str, filename: Optional[str] = None) -> BytesIO:
        """
        Generate a PDF file from resume text.
        
        Args:
            resume_text: The resume content (plain text)
            filename: Optional filename for the PDF
            
        Returns:
            BytesIO object containing the PDF data
        """
        try:
            # Create an in-memory PDF
            buffer = BytesIO()
            
            # Create PDF document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=PDFExportService.MARGIN_SIZE,
                leftMargin=PDFExportService.MARGIN_SIZE,
                topMargin=PDFExportService.MARGIN_SIZE,
                bottomMargin=PDFExportService.MARGIN_SIZE,
            )

            # Create styles
            styles = getSampleStyleSheet()
            
            # Custom styles for resume
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=14,
                textColor="#000000",
                spaceAfter=6,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
            
            heading_style = ParagraphStyle(
                "CustomHeading",
                parent=styles["Heading2"],
                fontSize=11,
                textColor="#1a1a1a",
                spaceAfter=6,
                spaceBefore=12,
                fontName="Helvetica-Bold",
            )
            
            body_style = ParagraphStyle(
                "CustomBody",
                parent=styles["BodyText"],
                fontSize=9,
                textColor="#333333",
                spaceAfter=6,
                leading=11,
            )

            # Build the story (content)
            story = []

            # Parse the resume text into sections
            lines = resume_text.split("\n")
            
            for line in lines:
                line = line.strip()
                
                if not line:
                    # Add spacer for empty lines
                    story.append(Spacer(1, 0.1 * inch))
                elif line.isupper() and len(line.split()) <= 5:
                    # Treat all-caps or short lines as headings
                    story.append(Paragraph(line, heading_style))
                elif any(char.isdigit() for char in line):
                    # Lines with dates or numbers as body
                    story.append(Paragraph(line, body_style))
                else:
                    # Regular text
                    story.append(Paragraph(line, body_style))

            # Build the PDF
            doc.build(story)
            
            # Reset buffer position to the beginning
            buffer.seek(0)
            
            logger.info("PDF generated successfully")
            return buffer

        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            raise

    @staticmethod
    def save_pdf_to_file(resume_text: str, file_path: str) -> None:
        """
        Generate and save a PDF file to disk.
        
        Args:
            resume_text: The resume content
            file_path: Path where the PDF should be saved
        """
        try:
            pdf_buffer = PDFExportService.generate_pdf(resume_text)
            
            with open(file_path, "wb") as f:
                f.write(pdf_buffer.getvalue())
            
            logger.info(f"PDF saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving PDF to file: {str(e)}")
            raise

    @staticmethod
    def generate_formatted_pdf(
        name: str,
        contact_info: dict,
        sections: dict,
    ) -> BytesIO:
        """
        Generate a more polished PDF with structured sections.
        
        Args:
            name: Candidate name
            contact_info: Dictionary with email, phone, location, etc.
            sections: Dictionary with resume sections
                     Keys: 'summary', 'experience', 'education', 'skills'
                     Values: List of strings or single string
            
        Returns:
            BytesIO object containing the PDF data
        """
        try:
            buffer = BytesIO()
            
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=PDFExportService.MARGIN_SIZE,
                leftMargin=PDFExportService.MARGIN_SIZE,
                topMargin=PDFExportService.MARGIN_SIZE,
                bottomMargin=PDFExportService.MARGIN_SIZE,
            )

            styles = getSampleStyleSheet()
            
            name_style = ParagraphStyle(
                "NameStyle",
                parent=styles["Heading1"],
                fontSize=16,
                textColor="#000000",
                spaceAfter=2,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
            
            contact_style = ParagraphStyle(
                "ContactStyle",
                parent=styles["Normal"],
                fontSize=8,
                textColor="#666666",
                spaceAfter=12,
                alignment=TA_CENTER,
            )
            
            section_style = ParagraphStyle(
                "SectionStyle",
                parent=styles["Heading2"],
                fontSize=11,
                textColor="#1a1a1a",
                spaceAfter=6,
                spaceBefore=12,
                fontName="Helvetica-Bold",
                borderColor="#cccccc",
                borderWidth=1,
                borderPadding=4,
            )
            
            body_style = ParagraphStyle(
                "BodyStyle",
                parent=styles["BodyText"],
                fontSize=9,
                textColor="#333333",
                spaceAfter=4,
                leading=10,
            )

            story = []

            # Add name
            story.append(Paragraph(name, name_style))

            # Add contact info
            contact_parts = []
            for key, value in contact_info.items():
                if value:
                    contact_parts.append(str(value))
            
            if contact_parts:
                contact_line = " | ".join(contact_parts)
                story.append(Paragraph(contact_line, contact_style))

            story.append(Spacer(1, 0.1 * inch))

            # Add sections
            for section_name, section_content in sections.items():
                if not section_content:
                    continue

                section_title = section_name.upper().replace("_", " ")
                story.append(Paragraph(section_title, section_style))

                if isinstance(section_content, list):
                    for item in section_content:
                        story.append(Paragraph(f"• {item}", body_style))
                else:
                    story.append(Paragraph(section_content, body_style))

                story.append(Spacer(1, 0.05 * inch))

            doc.build(story)
            buffer.seek(0)
            
            logger.info("Formatted PDF generated successfully")
            return buffer

        except Exception as e:
            logger.error(f"Error generating formatted PDF: {str(e)}")
            raise
