"""Integration tests for session flow."""
import pytest
from unittest.mock import patch, MagicMock
from core.mcq_generator import MCQuestion


def make_mock_question(section_id=5, topic="Test"):
    return MCQuestion(
        question_text  = f"Test question for {topic}?",
        choices        = {"A": "Correct", "B": "Wrong1", "C": "Wrong2", "D": "Wrong3"},
        correct_answer = "A",
        explanation    = "A is correct.",
        topic          = topic,
        section_id     = section_id,
    )


class TestAnswerSimulator:
    def test_accuracy_boundary_always_correct(self):
        from utils.simulator import AnswerSimulator
        sim = AnswerSimulator(accuracy=1.0, seed=42)
        q = make_mock_question()
        for _ in range(20):
            assert sim.simulate_answer(q) == "A"

    def test_accuracy_zero_always_wrong(self):
        from utils.simulator import AnswerSimulator
        sim = AnswerSimulator(accuracy=0.0, seed=42)
        q = make_mock_question()
        for _ in range(20):
            assert sim.simulate_answer(q) != "A"

    def test_weak_topic_lowers_accuracy(self):
        from utils.simulator import AnswerSimulator
        sim = AnswerSimulator(accuracy=0.8, seed=42)
        q = make_mock_question(topic="Weak Topic")
        answers = [sim.simulate_answer(q, weak_topic_names=["Weak Topic"]) for _ in range(50)]
        correct_rate = sum(1 for a in answers if a == "A") / 50
        # With weak topic penalty, should be < 40%
        assert correct_rate < 0.55

    def test_batch_returns_same_count_as_questions(self):
        from utils.simulator import AnswerSimulator
        sim = AnswerSimulator(accuracy=0.6, seed=42)
        questions = [make_mock_question() for _ in range(10)]
        answers = sim.simulate_batch(questions)
        assert len(answers) == 10
        assert all(a in ("A", "B", "C", "D") for a in answers)


class TestSessionResult:
    def test_to_dict_has_all_keys(self):
        from core.session_manager import SessionResult
        result = SessionResult(
            session_id       = 1,
            section_ids      = [5, 8],
            questions        = [],
            score            = 0.6,
            correct_count    = 6,
            total_count      = 10,
            is_adaptive      = True,
            weak_topics_used = [],
        )
        d = result.to_dict()
        for key in ["session_id", "section_ids", "score", "is_adaptive",
                    "correct_count", "total_count", "percentage"]:
            assert key in d