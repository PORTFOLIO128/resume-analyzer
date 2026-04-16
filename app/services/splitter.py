"""
Resume Section Splitter Service
Splits raw resume text into labelled sections:
  skills, projects, experience, education
using keyword-based heuristic matching.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Container
# ---------------------------------------------------------------------------

@dataclass
class ResumeSections:
    """Holds text for each extracted resume section."""

    skills: str = ""
    projects: str = ""
    experience: str = ""
    education: str = ""
    raw_text: str = ""

    def as_dict(self) -> Dict[str, str]:
        return {
            "skills": self.skills,
            "projects": self.projects,
            "experience": self.experience,
            "education": self.education,
        }

    def is_empty(self) -> bool:
        return not any([self.skills, self.projects, self.experience, self.education])


# ---------------------------------------------------------------------------
# Section Keyword Mapping
# ---------------------------------------------------------------------------

SECTION_HEADERS: Dict[str, List[str]] = {
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "technologies",
        "tools",
        "tech stack",
        "programming languages",
        "competencies",
        "technical expertise",
        "areas of expertise",
    ],
    "projects": [
        "projects",
        "personal projects",
        "key projects",
        "academic projects",
        "side projects",
        "portfolio",
        "selected projects",
        "project experience",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "internships",
        "internship",
        "work history",
        "career history",
        "positions held",
    ],
    "education": [
        "education",
        "academic background",
        "academic qualifications",
        "qualifications",
        "degrees",
        "certifications",
        "courses",
        "coursework",
        "training",
    ],
}

# Build a flat lookup: lowercased header string → section key
HEADER_LOOKUP: Dict[str, str] = {
    alias: section
    for section, aliases in SECTION_HEADERS.items()
    for alias in aliases
}


# ---------------------------------------------------------------------------
# Splitter
# ---------------------------------------------------------------------------

class ResumeSplitter:
    """
    Splits resume plain text into labelled sections using header detection.
    Falls back to the full raw text if a section cannot be isolated.
    """

    # Matches lines that look like headings (short, may be ALL CAPS or Title Case)
    _HEADER_PATTERN = re.compile(
        r"^(?P<header>[A-Z][A-Za-z &/\-]{1,50})\s*[:\-]?\s*$",
        re.MULTILINE,
    )

    def split(self, text: str) -> ResumeSections:
        """
        Split raw resume text into sections.

        Args:
            text: Full extracted text from the resume.

        Returns:
            ResumeSections with each field populated as much as possible.
        """
        sections = ResumeSections(raw_text=text)
        lines = text.splitlines()
        current_section: str | None = None
        section_buffer: Dict[str, List[str]] = {k: [] for k in SECTION_HEADERS}

        for line in lines:
            stripped = line.strip()
            detected = self._detect_section_header(stripped)

            if detected:
                current_section = detected
                continue

            if current_section:
                section_buffer[current_section].append(line)

        # Populate ResumeSections from buffers
        for section_key in SECTION_HEADERS:
            content = "\n".join(section_buffer[section_key]).strip()
            if content:
                setattr(sections, section_key, content)

        # Fallback: if nothing was parsed, put everything into raw_text
        # (analyzer will use raw text directly in the prompt)
        if sections.is_empty():
            logger.warning(
                "Section splitter found no clear headers. "
                "Falling back to raw text for all sections."
            )

        logger.info(
            "Sections extracted — skills:%d chars | projects:%d chars | "
            "experience:%d chars | education:%d chars",
            len(sections.skills),
            len(sections.projects),
            len(sections.experience),
            len(sections.education),
        )
        return sections

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_section_header(line: str) -> str | None:
        """
        Check whether a line matches a known section header.

        Returns:
            The canonical section key (e.g. 'skills') or None.
        """
        normalized = line.lower().strip(" :-_")
        # Direct lookup
        if normalized in HEADER_LOOKUP:
            return HEADER_LOOKUP[normalized]

        # Partial match (e.g. "Technical Skills & Tools")
        for alias, section in HEADER_LOOKUP.items():
            if alias in normalized and len(normalized) < 50:
                return section

        return None
