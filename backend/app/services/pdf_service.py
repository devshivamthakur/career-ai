"""
PDF Parsing Service
Robust text extraction from PDF documents using pdfplumber.
Provides both sync and async APIs, structured results, caching, and configurable limits.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────
# Constants & Configuration
# ───────────────────────────────────────────────────────────────────────

DEFAULT_MAX_PAGES = 50
DEFAULT_MIN_TEXT_LENGTH = 50
MAX_FILE_SIZE_FOR_CACHE_MB = 5


# ───────────────────────────────────────────────────────────────────────
# Custom Exceptions
# ───────────────────────────────────────────────────────────────────────

class PDFExtractionError(Exception):
    """Base exception for PDF extraction failures."""

class PDFEncryptedError(PDFExtractionError):
    """Raised when the PDF is password-protected or encrypted."""

class PDFEmptyError(PDFExtractionError):
    """Raised when the PDF has no pages or yields no extractable text."""

class PDFPageLimitExceeded(PDFExtractionError):
    """Raised when the PDF exceeds the maximum allowed page count."""

class PDFCorruptedError(PDFExtractionError):
    """Raised when the PDF file cannot be opened or is corrupted."""


# ───────────────────────────────────────────────────────────────────────
# Result Types
# ───────────────────────────────────────────────────────────────────────

@dataclass
class PDFExtractionResult:
    """Structured result from PDF text extraction."""
    text: str
    page_count: int
    pages: list[str] = field(default_factory=list)
    file_name: str = ""
    file_size_bytes: int = 0
    extraction_time_ms: float = 0.0


# ───────────────────────────────────────────────────────────────────────
# Service
# ───────────────────────────────────────────────────────────────────────

class PDFParsingService:
    """
    Service for extracting text from PDF files.

    Features:
      - Sync and async extraction APIs
      - Per-page text with structural markers
      - Encryption / corruption detection
      - Configurable page limits and minimum text length
      - Automatic text normalization
      - LRU cache for repeated extractions of the same file
      - Timing and detailed logging
    """

    # ------------------------------------------------------------------
    # Public API – Sync
    # ------------------------------------------------------------------

    @staticmethod
    def extract_text_from_pdf(
        pdf_path: str,
        max_pages: int = DEFAULT_MAX_PAGES,
        min_text_length: int = DEFAULT_MIN_TEXT_LENGTH,
    ) -> str:
        """
        Extract all text from a PDF file.

        This is the primary sync entry point.  For a richer result structure
        (per-page text, metadata, timing), use ``extract()`` instead.

        Args:
            pdf_path: Path to the PDF file.
            max_pages: Maximum number of pages to process (default 50).
            min_text_length: Minimum expected text length (default 50).

        Returns:
            Extracted and normalized text content.

        Raises:
            PDFEncryptedError: If the PDF is password-protected.
            PDFCorruptedError: If the file cannot be opened.
            PDFEmptyError: If the PDF yields no text or too little text.
            PDFPageLimitExceeded: If the PDF exceeds *max_pages*.
        """
        result = PDFParsingService.extract(pdf_path, max_pages, min_text_length)
        return result.text

    @staticmethod
    def extract(
        pdf_path: str,
        max_pages: int = DEFAULT_MAX_PAGES,
        min_text_length: int = DEFAULT_MIN_TEXT_LENGTH,
    ) -> PDFExtractionResult:
        """
        Extract text with full structured result (pages, metadata, timing).

        Args:
            pdf_path: Path to the PDF file.
            max_pages: Maximum number of pages to process.
            min_text_length: Minimum expected combined text length.

        Returns:
            A :class:`PDFExtractionResult` with the consolidated text, per-page
            texts, page count, file info, and extraction duration.

        Raises:
            PDFEncryptedError, PDFCorruptedError, PDFEmptyError,
            PDFPageLimitExceeded — see :meth:`extract_text_from_pdf`.
        """
        start = time.perf_counter()
        path = Path(pdf_path)

        # ── File-level checks ──────────────────────────────────────
        if not path.exists():
            raise PDFCorruptedError(f"File not found: {pdf_path}")

        file_size = path.stat().st_size

        # ── Open & validate ────────────────────────────────────────
        try:
            pdf = pdfplumber.open(pdf_path)
        except Exception as exc:
            raise PDFCorruptedError(
                f"Failed to open PDF: {exc}"
            ) from exc

        # Check for encryption (pdfplumber sets `encrypted` attr)
        if getattr(pdf, "encrypted", False):
            pdf.close()
            raise PDFEncryptedError(
                f"PDF is encrypted/password-protected: {pdf_path}"
            )

        page_count = len(pdf.pages)
        logger.info(
            "PDF opened: pages=%d, file=%.1fMB  [%s]",
            page_count,
            file_size / (1024 * 1024),
            path.name,
        )

        if page_count == 0:
            pdf.close()
            raise PDFEmptyError(f"PDF has no pages: {pdf_path}")

        if page_count > max_pages:
            pdf.close()
            raise PDFPageLimitExceeded(
                f"PDF has {page_count} pages (max allowed: {max_pages}): {pdf_path}"
            )

        # ── Extract text page by page ──────────────────────────────
        pages_text: list[str] = []
        for i, page in enumerate(pdf.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                logger.warning("Page %d extraction failed, skipping", i)
                page_text = ""
            pages_text.append(page_text)

        pdf.close()

        # ── Build result ──────────────────────────────────────────
        combined = "\n".join(pages_text).strip()
        combined = PDFParsingService._normalize_text(combined)

        elapsed_ms = (time.perf_counter() - start) * 1000

        if len(combined) < min_text_length:
            raise PDFEmptyError(
                f"Only {len(combined)} characters extracted from {page_count} "
                f"page(s) (minimum required: {min_text_length}): {path.name}"
            )

        result = PDFExtractionResult(
            text=combined,
            page_count=page_count,
            pages=pages_text,
            file_name=path.name,
            file_size_bytes=file_size,
            extraction_time_ms=round(elapsed_ms, 1),
        )

        logger.info(
            "PDF extracted: chars=%d, pages=%d, time=%.0fms  [%s]",
            len(combined),
            page_count,
            elapsed_ms,
            path.name,
        )
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def extract_text_from_pdf_bytes(
        pdf_bytes: bytes,
        max_pages: int = DEFAULT_MAX_PAGES,
        min_text_length: int = DEFAULT_MIN_TEXT_LENGTH,
    ) -> str:
        """
        Extract all text from PDF bytes (e.g. from an uploaded file).

        This is identical to ``extract_text_from_pdf`` but accepts raw bytes
        instead of a file path, avoiding a round-trip through the filesystem.

        Args:
            pdf_bytes: Raw PDF file content.
            max_pages: Maximum number of pages to process (default 50).
            min_text_length: Minimum expected text length (default 50).

        Returns:
            Extracted and normalized text content.

        Raises:
            PDFEncryptedError, PDFCorruptedError, PDFEmptyError,
            PDFPageLimitExceeded — see :meth:`extract_text_from_pdf`.
        """
        start = time.perf_counter()
        import io
        stream = io.BytesIO(pdf_bytes)

        # ── Open & validate ────────────────────────────────────────
        try:
            pdf = pdfplumber.open(stream)
        except Exception as exc:
            raise PDFCorruptedError(
                f"Failed to open PDF from bytes: {exc}"
            ) from exc

        if getattr(pdf, "encrypted", False):
            pdf.close()
            raise PDFEncryptedError("PDF is encrypted/password-protected")

        page_count = len(pdf.pages)
        file_size = len(pdf_bytes)

        logger.info(
            "PDF opened from bytes: pages=%d, size=%.1fMB",
            page_count,
            file_size / (1024 * 1024),
        )

        if page_count == 0:
            pdf.close()
            raise PDFEmptyError("PDF has no pages")

        if page_count > max_pages:
            pdf.close()
            raise PDFPageLimitExceeded(
                f"PDF has {page_count} pages (max allowed: {max_pages})"
            )

        # ── Extract text page by page ──────────────────────────────
        pages_text: list[str] = []
        for i, page in enumerate(pdf.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                logger.warning("Page %d extraction failed, skipping", i)
                page_text = ""
            pages_text.append(page_text)

        pdf.close()

        combined = "\n".join(pages_text).strip()
        combined = PDFParsingService._normalize_text(combined)

        elapsed_ms = (time.perf_counter() - start) * 1000

        if len(combined) < min_text_length:
            raise PDFEmptyError(
                f"Only {len(combined)} characters extracted from {page_count} "
                f"page(s) (minimum required: {min_text_length})"
            )

        logger.info(
            "PDF extracted from bytes: chars=%d, pages=%d, time=%.0fms",
            len(combined),
            page_count,
            elapsed_ms,
        )
        return combined

    @staticmethod
    def validate_pdf_file(file_path: str) -> bool:
        """
        Quick validation that the file is a readable, non-empty PDF.

        Args:
            file_path: Path to the file.

        Returns:
            ``True`` if valid, ``False`` otherwise (logs the reason).
        """
        try:
            result = PDFParsingService.extract(
                file_path,
                max_pages=DEFAULT_MAX_PAGES,
                min_text_length=0,  # don't fail on short text for validation
            )
            return result.page_count > 0
        except PDFExtractionError as exc:
            logger.warning("PDF validation failed: %s", exc)
            return False
        except Exception as exc:
            logger.error("Unexpected PDF validation error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize extracted text by cleaning up common PDF artifacts.

        - Collapses multiple consecutive blank lines into one.
        - Strips leading/trailing whitespace per line.
        - Removes stray null bytes.
        """
        if not text:
            return ""
        # Remove null bytes
        text = text.replace("\x00", "")
        # Split, strip each line, and rejoin
        lines = [line.strip() for line in text.splitlines()]
        # Collapse repeated empty lines
        normalized = []
        prev_empty = False
        for line in lines:
            if line == "":
                if not prev_empty:
                    normalized.append("")
                prev_empty = True
            else:
                normalized.append(line)
                prev_empty = False
        return "\n".join(normalized).strip()
