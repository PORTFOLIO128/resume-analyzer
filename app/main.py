"""
Resume Analyzer API - Main Application Entry Point
Production-grade FastAPI backend for resume analysis using Grok LLM.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from app.routes import analyze

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Resume Analyzer API",
        description=(
            "A production-grade resume analysis backend powered by Grok LLM. "
            "Upload a PDF resume and receive a structured, ATS-style evaluation."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        contact={
            "name": "Resume Analyzer Team",
            "email": "support@resumeanalyzer.io",
        },
        license_info={
            "name": "MIT",
        },
    )

    # -----------------------------------------------------------------------
    # CORS Middleware
    # -----------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # Tighten in production to specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
    )

    # -----------------------------------------------------------------------
    # Request Timing Middleware
    # -----------------------------------------------------------------------
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.2f}"
        logger.info(
            "%-6s %-40s → %d  (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    # -----------------------------------------------------------------------
    # Global Exception Handler
    # -----------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred. Please try again later.",
                "error_type": type(exc).__name__,
            },
        )

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------
    app.include_router(analyze.router, prefix="/api/v1", tags=["Resume Analysis"])

    # -----------------------------------------------------------------------
    # Health / Root
    # -----------------------------------------------------------------------
    @app.get("/", tags=["Health"])
    async def root():
        return {
            "service": "Resume Analyzer API",
            "version": "1.0.0",
            "status": "operational",
        }

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy"}

    return app


app = create_app()
