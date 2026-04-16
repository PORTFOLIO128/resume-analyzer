"""
PDF Parser Service
Extracts clean, structured text from uploaded resume PDF files using PyMuPDF.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFParserError(Exception):
    """Raised when PDF parsing fails."""


class PDFParser:
    """
    Responsible solely for extracting raw text from a PDF byte stream.
    No analysis logic lives here.
    """

    @staticmethod
    def extract_text(pdf_bytes: bytes) -> str:
        """
        Extract all text from a PDF provided as raw bytes.

        Args:
            pdf_bytes: Raw bytes of the uploaded PDF file.

        Returns:
            A single string containing all extracted text, pages joined by newlines.

        Raises:
            PDFParserError: On any parsing failure.
        """
        if not pdf_bytes:
            raise PDFParserError("PDF file is empty.")

        try:
            document = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        except Exception as exc:
            logger.error("Failed to open PDF document: %s", exc)
            raise PDFParserError(f"Cannot open PDF: {exc}") from exc

        if document.page_count == 0:
            raise PDFParserError("PDF has no pages.")

        pages_text: list[str] = []
        for page_num in range(document.page_count):
            try:
                page = document.load_page(page_num)
                text = page.get_text("text")  # Plain text extraction
                if text.strip():
                    pages_text.append(text.strip())
            except Exception as exc:
                logger.warning("Could not extract text from page %d: %s", page_num, exc)

        document.close()

        if not pages_text:
            raise PDFParserError(
                "No readable text found in the PDF. "
                "The file may be scanned/image-based. Please upload a text-based PDF."
            )

        full_text = "\n\n".join(pages_text)
        logger.info("Extracted %d characters from %d page(s).", len(full_text), len(pages_text))
        return full_text

    @staticmethod
    def validate_pdf(pdf_bytes: bytes, max_size_bytes: int) -> None:
        """
        Validate uploaded PDF before processing.

        Args:
            pdf_bytes: Raw PDF bytes.
            max_size_bytes: Maximum allowed file size in bytes.

        Raises:
            PDFParserError: If file is invalid or exceeds size limit.
        """
        if len(pdf_bytes) > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            raise PDFParserError(
                f"File size exceeds the {max_mb:.0f} MB limit. "
                "Please upload a smaller PDF."
            )

        # Quick magic-byte check (PDF starts with %PDF)
        if not pdf_bytes.startswith(b"%PDF"):
            raise PDFParserError(
                "Uploaded file does not appear to be a valid PDF. "
                "Please upload a proper PDF resume."
            )
