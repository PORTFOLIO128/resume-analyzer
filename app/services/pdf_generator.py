"""
PDF Generator Service
Converts a ResumeAnalysisResponse into a beautifully formatted, downloadable PDF report.
Uses ReportLab for layout and rendering.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.response_model import ResumeAnalysisResponse, ResumeStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand Colours
# ---------------------------------------------------------------------------

PRIMARY       = colors.HexColor("#1A1A2E")   # Deep navy
ACCENT        = colors.HexColor("#E94560")   # Vivid red
ACCENT_LIGHT  = colors.HexColor("#F5A623")   # Amber (for moderate)
SUCCESS       = colors.HexColor("#27AE60")   # Green (job-ready)
DANGER        = colors.HexColor("#E94560")   # Red (not ready)
MUTED         = colors.HexColor("#7F8C8D")   # Grey
BG_CARD       = colors.HexColor("#F4F6F9")   # Light card background
WHITE         = colors.white
BLACK         = colors.HexColor("#1C1C1C")


class PDFGenerator:
    """Generates a professionally styled PDF resume analysis report."""

    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN = 18 * mm

    def generate(self, analysis: ResumeAnalysisResponse) -> bytes:
        """
        Convert a ResumeAnalysisResponse into PDF bytes.

        Args:
            analysis: Fully validated analysis response model.

        Returns:
            PDF file as raw bytes, ready to stream to the client.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
            title="Resume Analysis Report",
            author="Resume Analyzer API",
        )

        styles = self._build_styles()
        story = self._build_story(analysis, styles)

        try:
            doc.build(story)
        except Exception as exc:
            logger.exception("Failed to build PDF: %s", exc)
            raise RuntimeError(f"PDF generation failed: {exc}") from exc

        pdf_bytes = buffer.getvalue()
        buffer.close()
        logger.info("PDF report generated — %d bytes.", len(pdf_bytes))
        return pdf_bytes

    # ------------------------------------------------------------------
    # Style Definitions
    # ------------------------------------------------------------------

    @staticmethod
    def _build_styles() -> dict:
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "ReportTitle",
                fontSize=26,
                textColor=WHITE,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
                spaceAfter=4,
            ),
            "subtitle": ParagraphStyle(
                "Subtitle",
                fontSize=11,
                textColor=colors.HexColor("#CBD3E3"),
                fontName="Helvetica",
                alignment=TA_CENTER,
                spaceAfter=0,
            ),
            "section_header": ParagraphStyle(
                "SectionHeader",
                fontSize=13,
                textColor=PRIMARY,
                fontName="Helvetica-Bold",
                spaceBefore=10,
                spaceAfter=4,
            ),
            "body": ParagraphStyle(
                "Body",
                fontSize=10,
                textColor=BLACK,
                fontName="Helvetica",
                leading=15,
                alignment=TA_JUSTIFY,
            ),
            "bullet": ParagraphStyle(
                "Bullet",
                fontSize=10,
                textColor=BLACK,
                fontName="Helvetica",
                leading=14,
                leftIndent=12,
                spaceAfter=2,
            ),
            "verdict": ParagraphStyle(
                "Verdict",
                fontSize=11,
                textColor=BLACK,
                fontName="Helvetica-Oblique",
                leading=16,
                alignment=TA_JUSTIFY,
                leftIndent=8,
                rightIndent=8,
            ),
            "score_label": ParagraphStyle(
                "ScoreLabel",
                fontSize=10,
                textColor=WHITE,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            ),
            "muted": ParagraphStyle(
                "Muted",
                fontSize=9,
                textColor=MUTED,
                fontName="Helvetica",
                alignment=TA_CENTER,
            ),
        }

    # ------------------------------------------------------------------
    # Report Story Builder
    # ------------------------------------------------------------------

    def _build_story(
        self, analysis: ResumeAnalysisResponse, styles: dict
    ) -> list:
        story = []

        # ---- Header Banner ----
        story += self._header_banner(analysis, styles)
        story.append(Spacer(1, 8 * mm))

        # ---- Score Dashboard ----
        story += self._score_table(analysis, styles)
        story.append(Spacer(1, 6 * mm))

        # ---- Sections ----
        story += self._list_section("✦  Strengths", analysis.strengths, styles, SUCCESS)
        story += self._list_section("✦  Weaknesses", analysis.weaknesses, styles, DANGER)
        story += self._list_section("✦  Missing Elements", analysis.missing_elements, styles, ACCENT_LIGHT)

        if analysis.job_roles:
            story += self._list_section("✦  Suggested Job Roles", analysis.job_roles, styles, SUCCESS)

        story += self._list_section("✦  Recommended Domains", analysis.domains, styles, PRIMARY)
        story += self._list_section("✦  Improvement Plan", analysis.improvement_plan, styles, ACCENT)

        # ---- Final Verdict ----
        story += self._final_verdict(analysis, styles)

        # ---- Footer ----
        story.append(Spacer(1, 10 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"Generated by Resume Analyzer API  •  {datetime.now().strftime('%B %d, %Y at %H:%M')}",
            styles["muted"],
        ))

        return story

    # ------------------------------------------------------------------
    # Component Builders
    # ------------------------------------------------------------------

    def _header_banner(self, analysis: ResumeAnalysisResponse, styles: dict) -> list:
        status_color = SUCCESS if analysis.status == ResumeStatus.JOB_READY else DANGER
        status_text = "✔ JOB READY" if analysis.status == ResumeStatus.JOB_READY else "✘ NOT JOB READY"

        banner_data = [[
            Paragraph("RESUME ANALYSIS REPORT", styles["title"]),
        ]]
        banner_table = Table(banner_data, colWidths=[self.PAGE_WIDTH - 2 * self.MARGIN])
        banner_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("ROUNDEDCORNERS", [6]),
        ]))

        # Status badge row
        badge_data = [[Paragraph(status_text, ParagraphStyle(
            "Badge",
            fontSize=12,
            fontName="Helvetica-Bold",
            textColor=WHITE,
            alignment=TA_CENTER,
        ))]]
        badge_table = Table(badge_data, colWidths=[120])
        badge_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), status_color),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROUNDEDCORNERS", [4]),
        ]))

        return [banner_table, Spacer(1, 4 * mm), badge_table, Spacer(1, 2 * mm)]

    def _score_table(self, analysis: ResumeAnalysisResponse, styles: dict) -> list:
        """4-column score card for section scores + overall."""
        sc = analysis.section_scores

        def score_cell(label: str, score: int, max_score: int = 10) -> Table:
            color = self._score_color(score, max_score)
            data = [[Paragraph(f"{score}/{max_score}", ParagraphStyle(
                "ScoreNum", fontSize=18, fontName="Helvetica-Bold",
                textColor=WHITE, alignment=TA_CENTER,
            ))], [Paragraph(label, ParagraphStyle(
                "ScoreLbl", fontSize=8, fontName="Helvetica",
                textColor=WHITE, alignment=TA_CENTER,
            ))]]
            t = Table(data, colWidths=[38 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), color),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ROUNDEDCORNERS", [5]),
            ]))
            return t

        cell_w = (self.PAGE_WIDTH - 2 * self.MARGIN) / 4

        section_row = [[
            score_cell("Skills", sc.skills),
            score_cell("Projects", sc.projects),
            score_cell("Experience", sc.experience),
            score_cell("Impact", sc.impact),
        ]]
        section_table = Table(
            section_row,
            colWidths=[cell_w] * 4,
            hAlign="CENTER",
        )
        section_table.setStyle(TableStyle([
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))

        overall_color = self._score_color(analysis.overall_score, 100)
        overall_data = [[Paragraph(
            f"Overall Score: {analysis.overall_score}/100",
            ParagraphStyle(
                "Overall", fontSize=14, fontName="Helvetica-Bold",
                textColor=WHITE, alignment=TA_CENTER,
            ),
        )]]
        overall_table = Table(
            overall_data,
            colWidths=[self.PAGE_WIDTH - 2 * self.MARGIN],
        )
        overall_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), overall_color),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("ROUNDEDCORNERS", [5]),
        ]))

        return [
            Paragraph("Score Dashboard", styles["section_header"]),
            HRFlowable(width="100%", thickness=1, color=PRIMARY),
            Spacer(1, 4 * mm),
            section_table,
            Spacer(1, 4 * mm),
            overall_table,
        ]

    def _list_section(
        self, title: str, items: List[str], styles: dict, color=PRIMARY
    ) -> list:
        if not items:
            return []
        elements = [
            Spacer(1, 3 * mm),
            Paragraph(title, ParagraphStyle(
                "DynHeader", fontSize=12, fontName="Helvetica-Bold",
                textColor=color, spaceBefore=4, spaceAfter=3,
            )),
            HRFlowable(width="100%", thickness=0.6, color=color, spaceAfter=4),
        ]
        for item in items:
            elements.append(Paragraph(f"• {item}", styles["bullet"]))
        return elements

    def _final_verdict(self, analysis: ResumeAnalysisResponse, styles: dict) -> list:
        if not analysis.final_verdict:
            return []
        return [
            Spacer(1, 4 * mm),
            Paragraph("✦  Final Verdict", ParagraphStyle(
                "VerdictHead", fontSize=13, fontName="Helvetica-Bold",
                textColor=PRIMARY, spaceBefore=6, spaceAfter=4,
            )),
            HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=6),
            Table(
                [[Paragraph(analysis.final_verdict, styles["verdict"])]],
                colWidths=[self.PAGE_WIDTH - 2 * self.MARGIN],
                style=TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), BG_CARD),
                    ("TOPPADDING",    (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
                    ("ROUNDEDCORNERS", [6]),
                ]),
            ),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_color(score: int, max_score: int) -> colors.Color:
        pct = score / max_score
        if pct >= 0.7:
            return SUCCESS
        elif pct >= 0.4:
            return ACCENT_LIGHT
        return DANGER
