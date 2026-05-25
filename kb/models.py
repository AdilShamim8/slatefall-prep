"""
kb/models.py
────────────
Database table definitions using SQLAlchemy ORM.

Think of each class as a spreadsheet:
- PrepSession  → one row per study session
- QuestionResult → one row per question asked in any session

WHY this schema:
The brief requires these query patterns:
  1. "given section IDs, get all prior sessions" → PrepSession.section_ids
  2. "get question-level results" → QuestionResult FK to PrepSession
  3. "find consistently wrong topics" → GROUP BY topic WHERE is_correct=False
  4. "KB snapshot of last 5 sessions" → ORDER BY created_at DESC LIMIT 5

Every column exists because a query pattern requires it.
No column was added speculatively.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float,
    ForeignKey, Integer, JSON, String, Text
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class all table models inherit from."""
    pass


class PrepSession(Base):
    """
    One row = one complete study session.

    Example row:
        id=3, section_ids="5,8", score=0.60,
        total_questions=10, correct_count=6,
        is_adaptive=True,
        weak_topics_used=["PAMC Protocol", "Authorization Levels"]
    """
    __tablename__ = "prep_sessions"

    id               = Column(Integer, primary_key=True, autoincrement=True)

    # Sorted comma-separated: "5,8" not "8,5" — ensures consistent matching
    section_ids      = Column(String,  nullable=False, index=True)

    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    score            = Column(Float,   default=0.0,  nullable=False)
    total_questions  = Column(Integer, default=0,    nullable=False)
    correct_count    = Column(Integer, default=0,    nullable=False)

    # Was this session generated using history context?
    # False = cold start (first time), True = adaptive (returning user)
    is_adaptive      = Column(Boolean, default=False, nullable=False)

    # Which weak topics influenced question generation?
    # Stored as JSON list: ["Topic A", "Topic B"]
    # Allows reviewer to verify adaptation was grounded in real data
    weak_topics_used = Column(JSON, default=list)

    # One session → many question results
    results = relationship(
        "QuestionResult",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON export."""
        return {
            "id":               self.id,
            "section_ids":      self.section_ids,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
            "score":            round(self.score, 4),
            "total_questions":  self.total_questions,
            "correct_count":    self.correct_count,
            "percentage":       f"{self.score:.1%}",
            "is_adaptive":      self.is_adaptive,
            "weak_topics_used": self.weak_topics_used or [],
        }

    def __repr__(self) -> str:
        return (
            f"PrepSession(id={self.id}, sections={self.section_ids}, "
            f"score={self.score:.1%}, adaptive={self.is_adaptive})"
        )


class QuestionResult(Base):
    """
    One row = one question asked + the user's answer.

    Example row:
        session_id=3, section_id=8,
        question_text="What is the PAMC threshold?",
        topic="PAMC Authorization Levels",
        choices={"A":"...", "B":"...", "C":"...", "D":"..."},
        correct_answer="B", user_answer="A", is_correct=False,
        explanation="B is correct because the dossier states..."
    """
    __tablename__ = "question_results"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    session_id     = Column(Integer, ForeignKey("prep_sessions.id"), nullable=False, index=True)
    section_id     = Column(Integer, nullable=False, index=True)

    question_text  = Column(Text,    nullable=False)

    # Topic label extracted by LLM (e.g. "PAMC Protocol Phases")
    # Critical for weak topic analysis: GROUP BY topic WHERE is_correct=False
    topic          = Column(String,  nullable=True,  default="General")

    # {"A": "option text", "B": "...", "C": "...", "D": "..."}
    choices        = Column(JSON,    nullable=False)

    correct_answer = Column(String(1), nullable=False)   # "A", "B", "C", or "D"
    user_answer    = Column(String(1), nullable=True)    # None if not yet answered
    is_correct     = Column(Boolean,   default=False,  nullable=False)
    explanation    = Column(Text,      nullable=True)
    answered_at    = Column(DateTime,  default=datetime.utcnow)

    # Relationship back to parent session
    session = relationship("PrepSession", back_populates="results")

    def to_dict(self) -> dict:
        """Serialize to dict for JSON export."""
        return {
            "id":            self.id,
            "session_id":    self.session_id,
            "section_id":    self.section_id,
            "question_text": self.question_text,
            "topic":         self.topic or "General",
            "choices":       self.choices,
            "correct_answer":self.correct_answer,
            "user_answer":   self.user_answer,
            "is_correct":    self.is_correct,
            "explanation":   self.explanation or "",
        }

    def __repr__(self) -> str:
        status = "✓" if self.is_correct else "✗"
        return (
            f"QuestionResult({status} section={self.section_id}, "
            f"topic='{self.topic}', got={self.user_answer})"
        )