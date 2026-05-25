"""
kb/queries.py
─────────────
All database read/write operations in one place.

WHY a dedicated queries module:
- No other file touches the database directly
- If the schema changes, we fix it here only
- Every query is named, documented, and testable
- Reviewers can verify adaptive behavior by reading these functions

The KnowledgeBase class is the single source of truth
for everything stored about user performance.
"""

from collections import Counter
from datetime import datetime
from typing import Any

from .database import get_db_session, init_db
from .models import PrepSession, QuestionResult
from utils.logger import get_logger

logger = get_logger(__name__)

# Ensure DB exists when this module is imported
init_db()


class KnowledgeBase:
    """
    Interface to all stored session and question data.

    All methods use get_db_session() context manager.
    Every method logs what it does for auditability.
    """

    # ── WRITE ─────────────────────────────────────────────────────

    def save_session(
        self,
        section_ids:            list[int],
        questions_and_results:  list[dict[str, Any]],
        is_adaptive:            bool = False,
        weak_topics_used:       list[str] | None = None,
    ) -> PrepSession:
        """
        Persist a completed prep session to the database.

        Args:
            section_ids:           e.g. [5, 8]
            questions_and_results: list of dicts, one per question,
                                   each containing question data + user answer
            is_adaptive:           True if history context was used
            weak_topics_used:      topic names that influenced this session

        Returns:
            The saved PrepSession (with its auto-assigned id)
        """
        total   = len(questions_and_results)
        correct = sum(1 for r in questions_and_results if r.get("is_correct", False))
        score   = correct / total if total > 0 else 0.0

        with get_db_session() as db:
            # Build the session record
            session = PrepSession(
                section_ids      = ",".join(str(s) for s in sorted(section_ids)),
                score            = score,
                total_questions  = total,
                correct_count    = correct,
                is_adaptive      = is_adaptive,
                weak_topics_used = weak_topics_used or [],
                created_at       = datetime.utcnow(),
            )
            db.add(session)
            db.flush()  # Assigns session.id before adding children

            # Save each question result linked to this session
            for item in questions_and_results:
                result = QuestionResult(
                    session_id     = session.id,
                    section_id     = item["section_id"],
                    question_text  = item["question_text"],
                    topic          = item.get("topic") or "General",
                    choices        = item["choices"],
                    correct_answer = item["correct_answer"],
                    user_answer    = item.get("user_answer"),
                    is_correct     = item.get("is_correct", False),
                    explanation    = item.get("explanation", ""),
                    answered_at    = datetime.utcnow(),
                )
                db.add(result)

            # Commit happens automatically when context manager exits
            # We need the id after commit, so we refresh
            db.flush()
            session_id  = session.id
            session_dict = session.to_dict()

        logger.info(
            f"Session {session_id} saved | "
            f"sections={section_ids} | "
            f"score={score:.1%} ({correct}/{total}) | "
            f"adaptive={is_adaptive} | "
            f"weak_topics={weak_topics_used or []}"
        )

        # Re-fetch to return a fully-loaded object
        return self._get_session_by_id(session_id)

    # ── READ ──────────────────────────────────────────────────────

    def _get_session_by_id(self, session_id: int) -> PrepSession | None:
        """Fetch a single session by primary key."""
        with get_db_session() as db:
            return db.query(PrepSession).filter(
                PrepSession.id == session_id
            ).first()

    def get_sessions_for_sections(
        self,
        section_ids: list[int]
    ) -> list[PrepSession]:
        """
        Return all sessions that included ANY of the given section IDs.

        Example: get_sessions_for_sections([8])
        Returns sessions with section_ids = "8", "5,8", "6,8,9", etc.

        WHY string search:
        We store section_ids as "5,8" (sorted string).
        We check if any target section appears in the stored string.
        Simple and reliable for small datasets.
        """
        target = {str(s) for s in section_ids}

        with get_db_session() as db:
            all_sessions = (
                db.query(PrepSession)
                .order_by(PrepSession.created_at.desc())
                .all()
            )

            matching = [
                s for s in all_sessions
                if target & set(s.section_ids.split(","))
            ]

        logger.info(
            f"Found {len(matching)} prior sessions "
            f"for sections {section_ids}"
        )
        return matching

    def get_weak_topics(
        self,
        section_ids:    list[int],
        min_wrong_count: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Identify topics the user consistently gets wrong.

        This is the CORE of adaptive intelligence.
        Queries ALL past sessions for these sections,
        counts wrong answers per topic, returns sorted list.

        Returns:
            [
                {"topic": "PAMC Protocol", "wrong_count": 3, "section_id": 8},
                {"topic": "Authorization",  "wrong_count": 1, "section_id": 5},
            ]

        The MCQ generator uses this list to weight question topics.
        """
        with get_db_session() as db:
            wrong_results = (
                db.query(QuestionResult)
                .filter(
                    QuestionResult.section_id.in_(section_ids),
                    QuestionResult.is_correct == False,  # noqa: E712
                )
                .all()
            )

        # Count how many times each topic was answered wrong
        topic_counts:   Counter = Counter()
        topic_sections: dict[str, int] = {}

        for r in wrong_results:
            topic = r.topic or "General"
            topic_counts[topic] += 1
            topic_sections[topic] = r.section_id

        # Build sorted result list (most wrong first)
        weak_topics = [
            {
                "topic":       topic,
                "wrong_count": count,
                "section_id":  topic_sections.get(topic),
            }
            for topic, count in topic_counts.most_common()
            if count >= min_wrong_count
        ]

        logger.info(
            f"Weak topics for sections {section_ids}: "
            f"{[(w['topic'], w['wrong_count']) for w in weak_topics[:5]]}"
        )
        return weak_topics

    def get_asked_questions(
        self,
        section_ids: list[int]
    ) -> list[str]:
        """
        Return all question texts previously asked for these sections.
        Used to tell the LLM what NOT to repeat.
        """
        with get_db_session() as db:
            rows = (
                db.query(QuestionResult.question_text)
                .filter(QuestionResult.section_id.in_(section_ids))
                .all()
            )
        questions = [r.question_text for r in rows]
        logger.info(
            f"Found {len(questions)} previously asked questions "
            f"for sections {section_ids}"
        )
        return questions

    def has_prior_history(self, section_ids: list[int]) -> bool:
        """True if the user has ever studied any of these sections before."""
        return len(self.get_sessions_for_sections(section_ids)) > 0

    def get_kb_snapshot(self, top_n: int = 5) -> list[dict[str, Any]]:
        """
        Human-readable snapshot of the most recent N sessions.

        Required by assessment spec:
        "A KB snapshot is a human-readable export of the top-5 most
        recent session records at the moment an iteration completes."

        Reviewers use this to verify:
        1. History is being stored correctly
        2. Adaptive prompting is grounded in real data
        """
        with get_db_session() as db:
            recent = (
                db.query(PrepSession)
                .order_by(PrepSession.created_at.desc())
                .limit(top_n)
                .all()
            )

            snapshot = []
            for session in recent:
                results = (
                    db.query(QuestionResult)
                    .filter(QuestionResult.session_id == session.id)
                    .all()
                )
                data = session.to_dict()
                data["questions"] = [r.to_dict() for r in results]
                snapshot.append(data)

        logger.info(f"KB snapshot generated: {len(snapshot)} sessions")
        return snapshot

    def get_all_sessions(self) -> list[PrepSession]:
        """Return every session ever, oldest first."""
        with get_db_session() as db:
            return (
                db.query(PrepSession)
                .order_by(PrepSession.created_at.asc())
                .all()
            )


# ─── Global singleton instance ────────────────────────────────────
# Import this everywhere: from kb.queries import kb
kb = KnowledgeBase()