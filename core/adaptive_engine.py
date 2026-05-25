"""
core/adaptive_engine.py
───────────────────────
Decides HOW to generate questions based on session history.

This is the core adaptive intelligence of the system.

Cold start (no prior history):
  → Generate fresh, balanced questions

Adaptive (returning user):
  → Query KB for weak topics and previously asked questions
  → Pass this context to MCQ generator
  → LLM generates questions that TARGET weak areas

The adaptation is TRANSPARENT:
Every decision is logged and stored in the KB snapshot,
so reviewers can trace exactly why questions were generated.
"""

from typing import Any

from core.mcq_generator import MCQuestion, mcq_generator
from core.pdf_parser import pdf_parser
from kb.queries import kb
from utils.logger import get_logger
import config

logger = get_logger(__name__)


class AdaptiveEngine:
    """Orchestrates adaptive question generation."""

    def prepare_session(
        self,
        section_ids:   list[int],
        n_per_section: int | None = None,
    ) -> tuple[list[MCQuestion], dict[str, Any]]:
        """
        Prepare questions for a study session.

        Returns: (questions, metadata)
        """
        n_per_section = n_per_section or config.QUESTIONS_PER_SECTION

        # ── Step 1: Check history ─────────────────────────────────
        has_history = kb.has_prior_history(section_ids)
        is_adaptive = has_history

        logger.info(
            f"Preparing session | sections={section_ids} | "
            f"n_per_section={n_per_section} | "
            f"is_adaptive={is_adaptive}"
        )

        # ── Step 2: Load PDF sections ─────────────────────────────
        sections = pdf_parser.get_sections(section_ids)

        if not sections:
            available = pdf_parser.available_ids()
            raise ValueError(
                f"No sections found for IDs {section_ids}. "
                f"Available: {available}\n"
                f"Run: python main.py list-sections"
            )

        # ── Step 3: Gather adaptive context ───────────────────────
        weak_topics:      list[dict[str, Any]] = []
        previously_asked: list[str]            = []

        if is_adaptive:
            weak_topics      = kb.get_weak_topics(section_ids, min_wrong_count=1)
            previously_asked = kb.get_asked_questions(section_ids)

            logger.info(
                f"Adaptive context | "
                f"weak_topics={len(weak_topics)} | "
                f"prev_asked={len(previously_asked)}"
            )

            for wt in weak_topics[:5]:
                logger.info(
                    f"  Weak topic → '{wt['topic']}' "
                    f"(wrong {wt['wrong_count']}x, section {wt['section_id']})"
                )

        # ── Step 4: Generate questions ────────────────────────────
        questions = mcq_generator.generate(
            sections                = sections,
            n_questions_per_section = n_per_section,
            weak_topics             = weak_topics if is_adaptive else None,
            previously_asked        = previously_asked if is_adaptive else None,
            is_adaptive             = is_adaptive,
        )

        # ── Step 5: Return with metadata ──────────────────────────
        metadata: dict[str, Any] = {
            "is_adaptive":               is_adaptive,
            "sections_studied":          section_ids,
            "weak_topics_used":          weak_topics,
            "previously_asked_count":    len(previously_asked),
            "total_questions_generated": len(questions),
        }

        return questions, metadata


# ─── Global singleton ─────────────────────────────────────────────
adaptive_engine = AdaptiveEngine()