"""
Routes — /api/v1/analyze & /api/v1/download-pdf
No business logic lives here. Routes are thin wrappers around services.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
import io
import pydantic

from app.models.response_model import ErrorResponse, ResumeAnalysisResponse
from app.services.analyzer import ResumeAnalyzer
from app.services.parser import PDFParserError
from app.services.llm_service import LLMServiceError
from app.services.pdf_generator import PDFGenerator

logger = logging.getLogger(__name__)

router = APIRouter()

# Singletons — instantiated once at module load (thread-safe, stateless services)
_analyzer = ResumeAnalyzer()
_pdf_generator = PDFGenerator()


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=ResumeAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a resume PDF",
    description=(
        "Upload a PDF resume and receive a strict, structured ATS-style evaluation. "
        "The response includes scores, strengths, weaknesses, job roles (if ready), "
        "domains, and an actionable improvement plan."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or unreadable PDF"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        502: {"model": ErrorResponse, "description": "LLM API error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def analyze_resume(
    file: Annotated[
        UploadFile,
        File(description="PDF resume file. Max 10 MB."),
    ],
) -> ResumeAnalysisResponse:
    """
    **POST /api/v1/analyze**

    Upload a resume PDF → receive structured JSON analysis.

    - Validates the uploaded file (type + size)
    - Extracts text via PyMuPDF
    - Splits into sections (skills, projects, experience, education)
    - Calls Grok LLM with a strict ATS evaluation prompt
    - Applies rule-based scoring adjustments
    - Returns validated `ResumeAnalysisResponse`
    """
    logger.info(
        "Received resume upload: filename='%s' content_type='%s'",
        file.filename,
        file.content_type,
    )

    try:
        pdf_bytes = await file.read()
    except Exception as exc:
        logger.exception("Failed to read uploaded file.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded file: {exc}",
        ) from exc
    finally:
        await file.close()

    # Magic-byte check — catches .docx / .jpg / etc. renamed as .pdf
    if not pdf_bytes[:4] == b"%PDF":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The uploaded file is not a valid PDF. "
                "Please upload a proper PDF resume (not .docx, .doc, or image files)."
            ),
        )

    try:
        result = await _analyzer.analyze(pdf_bytes)
    except PDFParserError as exc:
        logger.warning("PDF parse error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LLMServiceError as exc:
        logger.error("LLM service error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        ) from exc
    except ValueError as exc:
        logger.error("Response parsing error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except pydantic.ValidationError as exc:
        logger.error("Pydantic validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The LLM returned a JSON structure that failed validation: {exc}",
        ) from exc
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        logger.exception("Unexpected error during analysis.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during analysis: {exc}\n\nTraceback:\n{tb}",
        ) from exc

    return result


# ---------------------------------------------------------------------------
# POST /download-pdf
# ---------------------------------------------------------------------------

@router.post(
    "/download-pdf",
    summary="Download analysis report as PDF",
    description=(
        "Pass a `ResumeAnalysisResponse` JSON body and receive a formatted "
        "PDF analysis report as a downloadable file."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF analysis report file",
        },
        422: {"model": ErrorResponse, "description": "Invalid request body"},
        500: {"model": ErrorResponse, "description": "PDF generation error"},
    },
)
async def download_pdf_report(
    analysis: ResumeAnalysisResponse,
) -> StreamingResponse:
    """
    **POST /api/v1/download-pdf**

    Input: `ResumeAnalysisResponse` JSON body (from /analyze)
    Output: Downloadable PDF report

    This endpoint is intentionally stateless — it regenerates the PDF
    on demand from the provided JSON, requiring no server-side storage.
    """
    try:
        pdf_bytes = _pdf_generator.generate(analysis)
    except RuntimeError as exc:
        logger.exception("PDF generation failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {exc}",
        ) from exc

    filename = "resume_analysis_report.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
