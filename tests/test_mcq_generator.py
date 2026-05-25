"""Tests for MCQ generation."""
import pytest
from core.mcq_generator import MCQGenerator, MCQuestion
from core.pdf_parser import PDFSection


@pytest.fixture
def generator():
    return MCQGenerator()


@pytest.fixture
def section():
    return PDFSection(
        section_id=5,
        title="Test Section",
        content=(
            "The PAMC protocol operates in three phases. "
            "Phase one is initialization. Phase two is execution. "
            "Phase three is termination. Authorization requires dual approval."
        ),
        start_page=20,
        end_page=25,
    )


VALID_RESPONSE = '''
{
  "questions": [
    {
      "question_text": "How many phases does PAMC have?",
      "topic": "PAMC Protocol Phases",
      "choices": {
        "A": "Two phases",
        "B": "Three phases",
        "C": "Four phases",
        "D": "Five phases"
      },
      "correct_answer": "B",
      "explanation": "The text states three phases."
    }
  ]
}
'''


class TestResponseParsing:
    def test_parse_valid_json(self, generator, section):
        questions = generator._parse_response(VALID_RESPONSE, section_id=5)
        assert len(questions) == 1
        assert questions[0].correct_answer == "B"
        assert questions[0].section_id == 5

    def test_parse_markdown_wrapped_json(self, generator):
        wrapped = f"```json\n{VALID_RESPONSE}\n```"
        questions = generator._parse_response(wrapped, section_id=5)
        assert len(questions) == 1

    def test_skip_question_missing_choices(self, generator):
        bad = '{"questions": [{"question_text": "Q?", "correct_answer": "A", "explanation": "E"}]}'
        questions = generator._parse_response(bad, section_id=5)
        assert len(questions) == 0

    def test_skip_question_invalid_correct_answer(self, generator):
        bad = '''{"questions": [{
            "question_text": "Q?",
            "choices": {"A":"a","B":"b","C":"c","D":"d"},
            "correct_answer": "X",
            "explanation": "E"
        }]}'''
        # Should default to "A" not crash
        questions = generator._parse_response(bad, section_id=5)
        assert len(questions) == 1
        assert questions[0].correct_answer == "A"

    def test_fallback_question_is_valid(self, generator, section):
        fallback = generator._make_fallback(section)
        assert isinstance(fallback, MCQuestion)
        assert fallback.section_id == 5
        assert len(fallback.choices) == 4
        assert fallback.correct_answer in ("A", "B", "C", "D")


class TestPromptBuilders:
    def test_cold_start_prompt_contains_content(self, generator, section):
        prompt = generator._build_cold_start_prompt(section, n_questions=5)
        assert "PAMC" in prompt
        assert "5" in prompt
        assert "JSON" in prompt

    def test_adaptive_prompt_contains_weak_topics(self, generator, section):
        weak = [{"topic": "PAMC Phases", "wrong_count": 3, "section_id": 5}]
        prompt = generator._build_adaptive_prompt(
            section=section,
            n_questions=5,
            weak_topics=weak,
            previously_asked=["Old question?"],
        )
        assert "PAMC Phases" in prompt
        assert "Old question?" in prompt
        assert "60%" in prompt

    def test_content_truncation(self, generator):
        long_content = "word " * 5000
        truncated = generator._truncate_content(long_content)
        assert len(truncated.split()) <= 3000