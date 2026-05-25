"""
core/adaptive_engine.py
───────────────────────
Decides HOW to generate questions based on session history.

Two paths:
  Cold Start  → No prior history → fresh balanced questions
  Adaptive    → Prior history exists → target weak topics,
                avoid repeated questions

WHY this file exists separately:
  The decision logic (cold vs adaptive) is separate from
  the generation logic (mcq_generator) and the data logic (kb).
  Each file has ONE job. This one decides WHAT to do.
  mcq_generator decides HOW to do it.

TESTED: Verified no circular imports by importing in this order:
  config → utils.logger → kb.queries → core.pdf_parser → core.mcq_generator
"""

from typing import Any

# ── Internal imports (order matters — no circular deps) ──────────
import config
from utils.logger import get_logger
from kb.queries import kb
from core.pdf_parser import pdf_parser
from core.mcq_generator import MCQuestion, mcq_generator

logger = get_logger(__name__)


class AdaptiveEngine:
    """
    Orchestrates adaptive question generation.

    Single public method: prepare_session()
    Everything else is internal decision-making.
    """

    def prepare_session(
        self,
        section_ids:   list[int],
        n_per_section: int | None = None,
    ) -> tuple[list[MCQuestion], dict[str, Any]]:
        """
        Prepare questions for a study session.

        This is the core adaptive intelligence entry point.
        It checks history, loads context, and delegates
        question generation to mcq_generator.

        Args:
            section_ids:   e.g. [5, 8]
            n_per_section: questions per section (defaults to config)

        Returns:
            (questions, metadata)

            metadata keys:
              is_adaptive            → bool
              sections_studied       → list[int]
              weak_topics_used       → list[dict]
              previously_asked_count → int
              total_questions_generated → int
        """
        n_per_section = n_per_section or config.QUESTIONS_PER_SECTION

        # ── Step 1: Check KB for prior history ────────────────────
        has_history = kb.has_prior_history(section_ids)
        is_adaptive = has_history

        logger.info(
            f"AdaptiveEngine.prepare_session | "
            f"sections={section_ids} | "
            f"n_per_section={n_per_section} | "
            f"has_history={has_history} | "
            f"is_adaptive={is_adaptive}"
        )

        # ── Step 2: Load PDF sections ─────────────────────────────
        sections = pdf_parser.get_sections(section_ids)

        if not sections:
            available = pdf_parser.available_ids()
            raise ValueError(
                f"No sections found for IDs: {section_ids}\n"
                f"Available section IDs: {available}\n"
                f"Run: python main.py list-sections"
            )

        logger.info(
            f"Loaded {len(sections)} PDF sections: "
            f"{[s.section_id for s in sections]}"
        )

        # ── Step 3: Gather adaptive context if returning user ─────
        weak_topics:      list[dict[str, Any]] = []
        previously_asked: list[str]            = []

        if is_adaptive:
            # Get topics the user consistently gets wrong
            weak_topics = kb.get_weak_topics(
                section_ids,
                min_wrong_count=1
            )

            # Get question texts already asked (to avoid repetition)
            previously_asked = kb.get_asked_questions(section_ids)

            logger.info(
                f"Adaptive context loaded | "
                f"weak_topics={len(weak_topics)} | "
                f"previously_asked={len(previously_asked)}"
            )

            # Log each weak topic for full transparency
            if weak_topics:
                logger.info("Weak topics being targeted this session:")
                for wt in weak_topics[:8]:
                    logger.info(
                        f"  → topic='{wt['topic']}' | "
                        f"wrong_count={wt['wrong_count']} | "
                        f"section={wt.get('section_id', '?')}"
                    )
            else:
                logger.info(
                    "No weak topics found yet for these sections. "
                    "Prior sessions exist but all answers were correct."
                )

        else:
            logger.info(
                "Cold start — no prior history for these sections. "
                "Generating balanced coverage questions."
            )

        # ── Step 4: Generate questions ────────────────────────────
        questions = mcq_generator.generate(
            sections                = sections,
            n_questions_per_section = n_per_section,
            weak_topics             = weak_topics if is_adaptive else None,
            previously_asked        = previously_asked if is_adaptive else None,
            is_adaptive             = is_adaptive,
        )

        logger.info(
            f"Question generation complete | "
            f"generated={len(questions)} questions | "
            f"requested={n_per_section * len(sections)}"
        )

        # ── Step 5: Build and return metadata ─────────────────────
        # Metadata is stored in the session and shown in output files
        # so reviewers can verify adaptive behavior
        metadata: dict[str, Any] = {
            "is_adaptive":                is_adaptive,
            "sections_studied":           section_ids,
            "weak_topics_used":           weak_topics,
            "previously_asked_count":     len(previously_asked),
            "total_questions_generated":  len(questions),
        }

        return questions, metadata


# ─── Global singleton ─────────────────────────────────────────────
# Import this everywhere: from core.adaptive_engine import adaptive_engine
adaptive_engine = AdaptiveEngine()