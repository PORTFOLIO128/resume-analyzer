"""
Rule-Based Scoring Service
Applies deterministic penalties to the LLM-produced scores
to ensure consistency and guard against hallucinated high scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.models.response_model import ResumeStatus, SectionScores
from app.services.splitter import ResumeSections

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    """Outcome after applying rule-based scoring adjustments."""
    section_scores: SectionScores
    overall_score: int
    status: ResumeStatus
    penalties_applied: list[str]


class ResumeScorer:
    """
    Applies rule-based deductions on top of LLM scores.
    Acts as a consistency layer — prevents the LLM from being too lenient.
    """

    # ------------------------------------------------------------------
    # Penalty Rules configuration
    # ------------------------------------------------------------------

    # Each rule: (readable_name, deduction_from_section_score, applies_to_section)
    PENALTY_RULES = [
        {
            "name": "No projects section detected",
            "section": "projects",
            "deduction": 4,
            "condition": lambda s: not s.projects.strip(),
        },
        {
            "name": "No experience or internship section detected",
            "section": "experience",
            "deduction": 4,
            "condition": lambda s: not s.experience.strip(),
        },
        {
            "name": "Projects section is very thin (< 100 chars)",
            "section": "projects",
            "deduction": 2,
            "condition": lambda s: 0 < len(s.projects.strip()) < 100,
        },
        {
            "name": "No measurable results detected (no % or numbers in experience)",
            "section": "impact",
            "deduction": 3,
            "condition": lambda s: not _has_measurable_results(s.experience + s.projects),
        },
        {
            "name": "Skills section is missing",
            "section": "skills",
            "deduction": 3,
            "condition": lambda s: not s.skills.strip(),
        },
        {
            "name": "Very short skills section (< 50 chars) — likely only generic terms",
            "section": "skills",
            "deduction": 2,
            "condition": lambda s: 0 < len(s.skills.strip()) < 50,
        },
        {
            "name": "No education section",
            "section": "experience",
            "deduction": 1,
            "condition": lambda s: not s.education.strip(),
        },
    ]

    def apply(
        self,
        llm_scores: SectionScores,
        sections: ResumeSections,
    ) -> ScoringResult:
        """
        Apply rule-based penalties to LLM scores and compute final result.

        Args:
            llm_scores:  Raw section scores from the LLM (0–10 each).
            sections:    Parsed resume sections.

        Returns:
            ScoringResult with adjusted scores, overall_score, and status.
        """
        scores = {
            "skills": llm_scores.skills,
            "projects": llm_scores.projects,
            "experience": llm_scores.experience,
            "impact": llm_scores.impact,
        }
        penalties_applied: list[str] = []

        for rule in self.PENALTY_RULES:
            try:
                if rule["condition"](sections):
                    section = rule["section"]
                    deduction = rule["deduction"]
                    before = scores[section]
                    scores[section] = max(0, scores[section] - deduction)
                    logger.info(
                        "Penalty applied — '%s': %s %d → %d",
                        rule["name"],
                        section,
                        before,
                        scores[section],
                    )
                    penalties_applied.append(rule["name"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error evaluating penalty rule '%s': %s", rule["name"], exc)

        # Clamp all scores to valid range
        scores = {k: max(0, min(10, v)) for k, v in scores.items()}

        overall_score = _calculate_overall(scores)
        status = (
            ResumeStatus.NOT_JOB_READY
            if overall_score < settings.JOB_READY_THRESHOLD
            else ResumeStatus.JOB_READY
        )

        logger.info(
            "Scoring complete — overall: %d | status: %s | penalties: %d",
            overall_score,
            status.value,
            len(penalties_applied),
        )

        return ScoringResult(
            section_scores=SectionScores(**scores),
            overall_score=overall_score,
            status=status,
            penalties_applied=penalties_applied,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_measurable_results(text: str) -> bool:
    """Return True if the text contains numeric/percentage indicators of impact."""
    import re
    # Matches things like: 20%, 3x, +15, reduced by 40, led a team of 5
    patterns = [
        r"\d+\s*%",
        r"\d+x\b",
        r"\$\s*\d+",
        r"\b\d{2,}\b",          # Any 2+ digit number
        r"\bteam of \d+",
        r"\breduced\b",
        r"\bimproved\b",
        r"\bincreased\b",
        r"\bachieved\b",
        r"\bdelivered\b",
    ]
    combined = "|".join(patterns)
    return bool(re.search(combined, text, re.IGNORECASE))


def _calculate_overall(scores: dict[str, int]) -> int:
    """
    Weighted average of section scores, scaled to 0–100.
    Weights: skills 25%, projects 30%, experience 30%, impact 15%
    """
    weights = {
        "skills": 0.25,
        "projects": 0.30,
        "experience": 0.30,
        "impact": 0.15,
    }
    weighted_sum = sum(scores[k] * weights[k] for k in weights)
    return round(weighted_sum * 10)  # Scale from 0-10 → 0-100
