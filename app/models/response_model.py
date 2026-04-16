"""
Response Models — Pydantic schemas that define the strict contract
between the analyzer service and the API consumer.
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResumeStatus(str, Enum):
    JOB_READY = "JOB_READY"
    NOT_JOB_READY = "NOT_JOB_READY"


# ---------------------------------------------------------------------------
# Nested Models
# ---------------------------------------------------------------------------

class SectionScores(BaseModel):
    """Score breakdown per resume section (0–10 scale)."""

    skills: int = Field(..., ge=0, le=10, description="Skills relevance score (0-10)")
    projects: int = Field(..., ge=0, le=10, description="Project quality score (0-10)")
    experience: int = Field(..., ge=0, le=10, description="Experience relevance score (0-10)")
    impact: int = Field(..., ge=0, le=10, description="Measurable impact score (0-10)")


# ---------------------------------------------------------------------------
# Primary Response Model
# ---------------------------------------------------------------------------

class ResumeAnalysisResponse(BaseModel):
    """
    Full structured analysis response returned by the /analyze endpoint.
    This schema is the single source of truth for all consumers.
    """

    status: ResumeStatus = Field(
        ...,
        description="JOB_READY or NOT_JOB_READY based on overall evaluation.",
    )
    overall_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Aggregate resume score in range 0–100.",
    )
    section_scores: SectionScores = Field(
        ...,
        description="Granular scores per section.",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Genuine, specific strengths identified in the resume.",
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Critical weaknesses that reduce candidacy.",
    )
    missing_elements: List[str] = Field(
        default_factory=list,
        description="Important sections or content missing from the resume.",
    )
    job_roles: List[str] = Field(
        default_factory=list,
        description="Suggested job roles. Empty when status is NOT_JOB_READY.",
    )
    domains: List[str] = Field(
        default_factory=list,
        description="Domains the candidate should focus on.",
    )
    improvement_plan: List[str] = Field(
        default_factory=list,
        description="Actionable, step-by-step improvement actions.",
    )
    final_verdict: str = Field(
        ...,
        description="Strict, honest one-paragraph summary verdict.",
    )

    # -----------------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------------

    @field_validator("job_roles")
    @classmethod
    def validate_job_roles(
        cls, v: List[str], info
    ) -> List[str]:
        """Enforce: NOT_JOB_READY candidates must have empty job_roles."""
        # Access sibling field via validation info
        status = info.data.get("status")
        if status == ResumeStatus.NOT_JOB_READY and v:
            return []
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "NOT_JOB_READY",
                "overall_score": 28,
                "section_scores": {
                    "skills": 4,
                    "projects": 2,
                    "experience": 1,
                    "impact": 1,
                },
                "strengths": ["Exposure to Python fundamentals"],
                "weaknesses": [
                    "No real-world projects with measurable outcomes",
                    "Skills list is composed entirely of generic buzzwords",
                    "Zero professional or internship experience",
                ],
                "missing_elements": [
                    "GitHub profile or portfolio link",
                    "Deployed projects",
                    "Quantifiable achievements",
                ],
                "job_roles": [],
                "domains": ["Web Development", "Backend Engineering"],
                "improvement_plan": [
                    "Build and deploy at least 2 complete projects with live URLs.",
                    "Contribute to open-source to demonstrate collaboration.",
                    "Replace generic skill listings with specific frameworks and versions.",
                    "Add 3–5 quantifiable impact statements to any experience entries.",
                ],
                "final_verdict": (
                    "The candidate lacks the real-world depth required by competitive employers. "
                    "Without deployed projects and measurable achievements, this resume will be "
                    "rejected by ATS filters and hiring managers alike."
                ),
            }
        }
    }


# ---------------------------------------------------------------------------
# Error Response Model
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str = Field(..., description="Human-readable error message.")
    error_type: str = Field(
        default="APIError",
        description="Machine-readable error classification.",
    )
