"""Tests for Knowledge Base operations."""
import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path):
    """Provide isolated temp database for each test."""
    db_path = tmp_path / "test.db"
    with patch("config.DB_PATH", db_path):
        # Reset global state
        import kb.database as db_module
        db_module._engine = None
        db_module._SessionFactory = None
        db_module.init_db()

        from kb.queries import KnowledgeBase
        test_kb = KnowledgeBase()
        yield test_kb

        # Cleanup
        db_module._engine = None
        db_module._SessionFactory = None


def make_question(section_id=5, topic="Test Topic", is_correct=True):
    return {
        "section_id":    section_id,
        "question_text": f"Test question about {topic}?",
        "topic":         topic,
        "choices":       {"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
        "correct_answer": "A",
        "user_answer":   "A" if is_correct else "B",
        "is_correct":    is_correct,
        "explanation":   "Because A.",
    }


class TestKBSave:
    def test_save_returns_session_with_id(self, tmp_db):
        session = tmp_db.save_session(
            section_ids=[5],
            questions_and_results=[make_question()],
        )
        assert session.id is not None
        assert session.id > 0

    def test_score_calculated_correctly(self, tmp_db):
        questions = [
            make_question(is_correct=True),
            make_question(is_correct=True),
            make_question(is_correct=False),
        ]
        session = tmp_db.save_session([5], questions)
        assert abs(session.score - 2/3) < 0.001

    def test_is_adaptive_stored(self, tmp_db):
        session = tmp_db.save_session(
            section_ids=[5],
            questions_and_results=[make_question()],
            is_adaptive=True,
            weak_topics_used=["Test Topic"],
        )
        assert session.is_adaptive is True


class TestKBQuery:
    def test_get_sessions_for_sections(self, tmp_db):
        tmp_db.save_session([5, 8], [make_question(5)])
        tmp_db.save_session([6, 9], [make_question(6)])

        results = tmp_db.get_sessions_for_sections([8])
        assert len(results) == 1

    def test_has_prior_history_false_initially(self, tmp_db):
        assert tmp_db.has_prior_history([5]) is False

    def test_has_prior_history_true_after_save(self, tmp_db):
        tmp_db.save_session([5], [make_question(5)])
        assert tmp_db.has_prior_history([5]) is True

    def test_weak_topics_identifies_wrong_answers(self, tmp_db):
        questions = [
            make_question(5, "Hard Topic", is_correct=False),
            make_question(5, "Hard Topic", is_correct=False),
            make_question(5, "Easy Topic", is_correct=True),
        ]
        tmp_db.save_session([5], questions)

        weak = tmp_db.get_weak_topics([5])
        assert len(weak) >= 1
        assert weak[0]["topic"] == "Hard Topic"
        assert weak[0]["wrong_count"] == 2

    def test_kb_snapshot_returns_recent_first(self, tmp_db):
        tmp_db.save_session([1], [make_question(1)])
        tmp_db.save_session([2], [make_question(2)])

        snapshot = tmp_db.get_kb_snapshot(top_n=5)
        assert len(snapshot) == 2
        # Most recent should be first
        assert snapshot[0]["section_ids"] == "2"

    def test_get_asked_questions_returns_text(self, tmp_db):
        tmp_db.save_session([5], [make_question(5, "Topic A")])
        asked = tmp_db.get_asked_questions([5])
        assert len(asked) == 1
        assert "Topic A" in asked[0]