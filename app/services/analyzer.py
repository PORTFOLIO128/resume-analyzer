"""
Analyzer Service — Core Brain
Orchestrates the full resume analysis pipeline:
  parse → split → build prompt → call LLM → apply scoring → return structured JSON
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from app.models.response_model import ResumeAnalysisResponse, ResumeStatus, SectionScores
from app.services.llm_service import GrokLLMService, LLMServiceError
from app.services.parser import PDFParser, PDFParserError
from app.services.scoring import ResumeScorer
from app.services.splitter import ResumeSections, ResumeSplitter
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt (ATS Persona — used verbatim as requested)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an advanced ATS (Applicant Tracking System) and senior hiring manager with 15+ years of experience evaluating resumes for top technology companies.

Your task is to STRICTLY evaluate the given resume based on real-world hiring standards and return a structured JSON response.

==================================================
CORE OBJECTIVE
==================================================

Evaluate whether the candidate is truly job-ready for the current competitive job market.
You must act like a real hiring manager who rejects weak candidates.

==================================================
EVALUATION DIMENSIONS
==================================================

1. Skills Quality:
- Are the skills relevant to current industry needs?
- Are they specific (e.g., Django, REST APIs) or generic (e.g., hardworking)?
- Are there enough technical skills?

2. Project Quality:
- Are projects real-world or just tutorial/basic projects?
- Do they demonstrate problem-solving ability?
- Are there deployed links, GitHub references, or practical use?
- Do projects include measurable impact?

3. Experience Strength:
- Any internships or real work experience?
- Is the experience relevant to the domain?
- Does it show responsibility and contribution?

4. Resume Impact:
- Are there measurable achievements (numbers, %, results)?
- Does the resume stand out among average candidates?

5. Resume Completeness:
- Missing sections? (projects, experience, links)
- Weak structure or unclear formatting?

==================================================
STRICT DECISION RULES (CRITICAL)
==================================================

- Be brutally honest. Do NOT sugarcoat anything.
- Do NOT provide motivational or emotional statements.
- If the resume is weak → clearly mark: "NOT_JOB_READY"

MANDATORY CONDITIONS:

IF ANY OF THESE ARE TRUE:
- No real-world projects
- No measurable achievements
- No experience or internships
- Only basic or tutorial-level knowledge

THEN:
- status MUST be "NOT_JOB_READY"
- job_roles MUST be an empty list []
- Focus only on domains + improvement_plan

ONLY suggest job_roles IF:
- Candidate has strong projects + skills + readiness

==================================================
SCORING SYSTEM
==================================================

Give a score (0–10) for each:
- skills_score
- projects_score
- experience_score
- impact_score

Then calculate:
overall_score = average of all scores × 10 (range 0–100)

SCORING GUIDELINES:
0–3   → Very Weak
4–5   → Below Average
6–7   → Moderate
8–9   → Strong
10    → Exceptional

==================================================
CRITICAL ANALYSIS REQUIREMENTS
==================================================

You MUST identify:
- Strengths (only real strengths, not generic)
- Weaknesses (clear and critical issues)
- Missing elements (what is NOT present but required)
- Improvement plan (actionable steps, not vague advice)

==================================================
JOB ROLE SUGGESTION LOGIC
==================================================

IF status = NOT_JOB_READY:
  job_roles = []

IF status = JOB_READY:
  Suggest ONLY realistic roles (e.g., Junior Backend Developer)
  Avoid unrealistic roles (e.g., Senior Engineer)

==================================================
DOMAIN SUGGESTION LOGIC
==================================================

Always suggest domains the user can focus on:
Examples:
- Web Development
- Backend Engineering
- Data Analysis
- AI/ML (ONLY if relevant)

==================================================
OUTPUT FORMAT (STRICT JSON ONLY)
==================================================

Return ONLY valid JSON. No explanation, no text outside JSON.

{
  "status": "JOB_READY or NOT_JOB_READY",
  "overall_score": number (0–100),
  "section_scores": {
    "skills": number (0–10),
    "projects": number (0–10),
    "experience": number (0–10),
    "impact": number (0–10)
  },
  "strengths": ["only real strengths"],
  "weaknesses": ["clear and critical weaknesses"],
  "missing_elements": ["important missing items"],
  "job_roles": ["only if job ready"],
  "domains": ["relevant domains to focus"],
  "improvement_plan": ["clear step-by-step actions"],
  "final_verdict": "strict and honest summary"
}

==================================================
FINAL INSTRUCTION
==================================================

- Evaluate like a real hiring manager.
- Reject weak candidates confidently.
- Do NOT be polite.
- Do NOT hallucinate achievements.
- Be accurate, strict, and realistic.
- Output MUST be valid JSON only.
"""

# ---------------------------------------------------------------------------
# User Prompt Template
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """==================================================
RESUME CONTENT (STRUCTURED INPUT)
==================================================

Skills:
{skills}

Projects:
{projects}

Experience:
{experience}

Education:
{education}

==================================================
FINAL INSTRUCTION
==================================================

Evaluate like a real hiring manager. Be strict, accurate, and realistic.
Output MUST be valid JSON only. No extra text.
"""


# ---------------------------------------------------------------------------
# Core Analyzer
# ---------------------------------------------------------------------------

class ResumeAnalyzer:
    """
    Orchestrates the complete resume analysis pipeline.
    This is the single entry point for all analysis requests.
    """

    def __init__(self) -> None:
        self._parser = PDFParser()
        self._splitter = ResumeSplitter()
        self._llm = GrokLLMService()
        self._scorer = ResumeScorer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(self, pdf_bytes: bytes) -> ResumeAnalysisResponse:
        """
        Full pipeline: PDF bytes → structured analysis JSON.

        Args:
            pdf_bytes: Raw bytes of the uploaded PDF resume.

        Returns:
            ResumeAnalysisResponse — fully validated Pydantic model.

        Raises:
            PDFParserError: If PDF is invalid or unreadable.
            LLMServiceError: If Grok API call fails.
            ValueError: If LLM returns malformed JSON.
        """
        # Step 1: Validate & parse PDF
        logger.info("Step 1/5 — Validating and parsing PDF …")
        self._parser.validate_pdf(pdf_bytes, settings.MAX_FILE_SIZE_BYTES)
        raw_text = self._parser.extract_text(pdf_bytes)

        # Step 2: Split into sections
        logger.info("Step 2/5 — Splitting resume into sections …")
        sections = self._splitter.split(raw_text)

        # Step 3: Build prompt & call LLM
        logger.info("Step 3/5 — Calling Grok LLM …")
        user_prompt = self._build_user_prompt(sections, raw_text)
        llm_raw = self._llm.call(SYSTEM_PROMPT, user_prompt)

        # Step 4: Parse LLM JSON response
        logger.info("Step 4/5 — Parsing LLM response …")
        llm_data = self._parse_llm_response(llm_raw)

        # Step 5: Apply rule-based scoring on top of LLM scores
        logger.info("Step 5/5 — Applying rule-based scoring adjustments …")
        llm_section_scores = SectionScores(
            skills=self._safe_int(llm_data.get("section_scores", {}).get("skills", 5)),
            projects=self._safe_int(llm_data.get("section_scores", {}).get("projects", 5)),
            experience=self._safe_int(llm_data.get("section_scores", {}).get("experience", 5)),
            impact=self._safe_int(llm_data.get("section_scores", {}).get("impact", 5)),
        )
        scoring_result = self._scorer.apply(llm_section_scores, sections)

        # Merge: scoring overrides LLM's overall_score + status + job_roles
        final_job_roles = (
            []
            if scoring_result.status == ResumeStatus.NOT_JOB_READY
            else llm_data.get("job_roles", [])
        )

        response = ResumeAnalysisResponse(
            status=scoring_result.status,
            overall_score=scoring_result.overall_score,
            section_scores=scoring_result.section_scores,
            strengths=llm_data.get("strengths", []),
            weaknesses=self._merge_weaknesses(
                llm_data.get("weaknesses", []),
                scoring_result.penalties_applied,
            ),
            missing_elements=llm_data.get("missing_elements", []),
            job_roles=final_job_roles,
            domains=llm_data.get("domains", []),
            improvement_plan=llm_data.get("improvement_plan", []),
            final_verdict=llm_data.get("final_verdict", ""),
        )

        logger.info(
            "Analysis complete — status: %s | score: %d",
            response.status.value,
            response.overall_score,
        )
        return response

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(sections: ResumeSections, raw_text: str) -> str:
        """Construct the user prompt from parsed sections with raw_text fallback."""
        return USER_PROMPT_TEMPLATE.format(
            skills=sections.skills or "(not found — see full resume below)",
            projects=sections.projects or "(not found — see full resume below)",
            experience=sections.experience or "(not found — see full resume below)",
            education=sections.education or "(not found — see full resume below)",
        ) + (
            f"\n\n[FULL RESUME TEXT FOR REFERENCE]\n{raw_text[:4000]}"
            if sections.is_empty()
            else ""
        )

    @staticmethod
    def _parse_llm_response(raw: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from the LLM response.
        Handles markdown code fences (```json ... ```) gracefully.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        # Attempt to find the first complete JSON object
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not json_match:
            logger.error("No JSON object found in LLM response: %r", raw[:500])
            raise ValueError(
                "The LLM did not return a valid JSON object. "
                "This is a transient error — please retry."
            )

        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error: %s\nRaw content: %r", exc, raw[:500])
            raise ValueError(
                f"Failed to parse LLM JSON response: {exc}. Please retry."
            ) from exc

    @staticmethod
    def _safe_int(value: Any, default: int = 5) -> int:
        """Safely coerce a value to int within 0–10."""
        try:
            return max(0, min(10, int(float(str(value)))))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _merge_weaknesses(llm_weaknesses: list, penalties: list) -> list:
        """Add rule-detected weaknesses not already present in LLM list."""
        existing_lower = {w.lower() for w in llm_weaknesses}
        merged = list(llm_weaknesses)
        for penalty in penalties:
            if penalty.lower() not in existing_lower:
                merged.append(penalty)
        return merged
