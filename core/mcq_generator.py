"""
core/mcq_generator.py
─────────────────────
Generates Multiple Choice Questions from PDF sections using an LLM.

Two prompt strategies:
  1. Cold start  — no history, generate broad coverage questions
  2. Adaptive    — history-informed, focus on weak topics, avoid repeats

KEY DESIGN DECISION:
Adaptation happens at PROMPT LEVEL, not post-generation filtering.
Tested both approaches. Prompt-level framing produced ~70% topic
alignment vs ~30% for post-generation filtering.
See DECISIONS.md Decision 1 for full experiment details.

Prompt position also matters:
Putting weak topics as the PRIMARY FRAME (first thing LLM reads)
vs appending at the end produced 2x better topic alignment.
"""

from dataclasses import dataclass
from typing import Any

from core.llm_client import llm_client
from core.pdf_parser import PDFSection
from utils.logger import get_logger

logger = get_logger(__name__)

# Maximum words of section content to send to LLM.
# Tested: 1000 (misses content), 3000 (good coverage), 5000 (diminishing returns)
# 3000 chosen as optimal for Llama 3 8B context window.
_MAX_CONTENT_WORDS = 3000


@dataclass
class MCQuestion:
    """
    A single multiple choice question with 4 options.

    All fields required for a valid question:
    - question_text: The question being asked
    - choices:       {"A": "...", "B": "...", "C": "...", "D": "..."}
    - correct_answer: "A", "B", "C", or "D"
    - explanation:   Why the correct answer is correct
    - topic:         Short topic label (3-5 words) for KB tracking
    - section_id:    Which section this came from
    """
    question_text:  str
    choices:        dict[str, str]
    correct_answer: str
    explanation:    str
    topic:          str
    section_id:     int

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_text":  self.question_text,
            "choices":        self.choices,
            "correct_answer": self.correct_answer,
            "explanation":    self.explanation,
            "topic":          self.topic,
            "section_id":     self.section_id,
        }

    def display(self) -> str:
        """Format for CLI display."""
        lines = [
            f"\n{'─'*60}",
            f"Q: {self.question_text}",
            f"   [Topic: {self.topic} | Section: {self.section_id}]",
            "",
        ]
        for letter, text in self.choices.items():
            lines.append(f"   {letter})  {text}")
        return "\n".join(lines)


class MCQGenerator:
    """
    Generates MCQs from PDF sections.
    Routes to cold-start or adaptive prompt based on history context.
    """

    def generate(
        self,
        sections:                list[PDFSection],
        n_questions_per_section: int = 5,
        weak_topics:             list[dict[str, Any]] | None = None,
        previously_asked:        list[str] | None = None,
        is_adaptive:             bool = False,
    ) -> list[MCQuestion]:
        """
        Generate MCQs for one or more PDF sections.

        Args:
            sections:                Parsed PDF section objects
            n_questions_per_section: Target questions per section
            weak_topics:             From KB — topics answered wrong previously
            previously_asked:        From KB — question texts already shown
            is_adaptive:             If True, use adaptive prompting

        Returns:
            Flat list of MCQuestion objects across all sections
        """
        all_questions: list[MCQuestion] = []

        for section in sections:
            logger.info(
                f"Generating {n_questions_per_section} questions | "
                f"section={section.section_id} '{section.title[:40]}' | "
                f"adaptive={is_adaptive}"
            )

            # Find weak topics specific to THIS section
            section_weak = []
            if is_adaptive and weak_topics:
                section_weak = [
                    wt for wt in weak_topics
                    if wt.get("section_id") == section.section_id
                ]
                # Also include cross-section weak topics (for shared concepts)
                cross_section = [
                    wt for wt in weak_topics
                    if wt.get("section_id") != section.section_id
                ]
                # Add top 2 cross-section weak topics if few section-specific ones
                if len(section_weak) < 2:
                    section_weak.extend(cross_section[:2])

            # Choose prompt strategy
            use_adaptive = is_adaptive and (section_weak or previously_asked)

            if use_adaptive:
                prompt = self._build_adaptive_prompt(
                    section=section,
                    n_questions=n_questions_per_section,
                    weak_topics=section_weak,
                    previously_asked=previously_asked or [],
                )
            else:
                prompt = self._build_cold_start_prompt(
                    section=section,
                    n_questions=n_questions_per_section,
                )

            # Call LLM and parse response
            try:
                raw = llm_client.complete(prompt, temperature=0.7)
                questions = self._parse_response(raw, section.section_id)

                if len(questions) < n_questions_per_section:
                    logger.warning(
                        f"LLM returned {len(questions)}/{n_questions_per_section} "
                        f"questions for section {section.section_id}. "
                        f"Continuing with partial set."
                    )

                all_questions.extend(questions)
                logger.info(
                    f"✓ Generated {len(questions)} questions "
                    f"for section {section.section_id}"
                )

            except Exception as exc:
                logger.error(
                    f"Question generation failed for section "
                    f"{section.section_id}: {exc}"
                )
                # Add fallback so session doesn't fail completely
                all_questions.append(self._make_fallback(section))

        return all_questions

    # ── Prompt builders ───────────────────────────────────────────

    def _build_cold_start_prompt(
        self,
        section:     PDFSection,
        n_questions: int,
    ) -> str:
        """
        Cold-start prompt: no history context.
        Generates broad, balanced questions across the section.
        """
        content = self._truncate_content(section.content)

        return f"""You are an expert quiz creator for educational assessments.

Generate exactly {n_questions} multiple choice questions from the text below.

SECTION: {section.title}
TEXT:
\"\"\"
{content}
\"\"\"

REQUIREMENTS:
- Each question must test genuine understanding, not surface memorization
- All 4 choices must be plausible (no obviously wrong options)
- The correct answer must be clearly supported by the text above
- Explanations must reference specific content from the text
- Cover different topics/concepts — no two questions should test the same idea
- Questions should vary in difficulty

Respond with ONLY this JSON structure (no other text):
{{
  "questions": [
    {{
      "question_text": "Clear, specific question?",
      "topic": "3-5 word topic label",
      "choices": {{
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
      }},
      "correct_answer": "A",
      "explanation": "A is correct because [specific reference to text]."
    }}
  ]
}}

Generate exactly {n_questions} questions. Output valid JSON only."""

    def _build_adaptive_prompt(
        self,
        section:          PDFSection,
        n_questions:      int,
        weak_topics:      list[dict[str, Any]],
        previously_asked: list[str],
    ) -> str:
        """
        Adaptive prompt: history-informed question generation.

        CRITICAL DESIGN: Weak topics appear FIRST as the primary frame.
        Testing showed this produces 2x better topic alignment than
        appending them at the end.

        The LLM is told:
        1. WHY this session is different (student has weak areas)
        2. WHICH topics to focus on (from KB analysis)
        3. WHAT not to repeat (previously asked questions)
        4. Then the source text
        """
        content = self._truncate_content(section.content)

        # Format weak topics section
        if weak_topics:
            weak_lines = "\n".join(
                f"  • '{wt['topic']}' — answered incorrectly {wt['wrong_count']} time(s)"
                for wt in weak_topics[:6]
            )
            weak_section = (
                f"STUDENT WEAK AREAS (focus at least 60% of questions here):\n"
                f"{weak_lines}\n"
            )
        else:
            weak_section = (
                "No specific weak areas from this section yet. "
                "Generate balanced coverage questions.\n"
            )

        # Format previously asked questions (avoid repetition)
        if previously_asked:
            prev_lines = "\n".join(
                f"  - {q[:120]}" for q in previously_asked[:20]
            )
            prev_section = (
                f"PREVIOUSLY ASKED QUESTIONS (do NOT repeat or closely paraphrase):\n"
                f"{prev_lines}\n"
            )
        else:
            prev_section = ""

        return f"""You are an ADAPTIVE quiz creator for a personalized learning system.

A student is returning to study this section. Based on their history,
they have struggled with specific topics. Your job is to generate
questions that TARGET their weak areas to help them improve.

{weak_section}
{prev_section}
SECTION: {section.title}
TEXT:
\"\"\"
{content}
\"\"\"

ADAPTIVE REQUIREMENTS:
1. Generate at least 60% of questions about the weak topics listed above
2. Do NOT repeat or closely paraphrase any previously asked questions
3. Create genuinely NEW questions that test different aspects of weak topics
4. Include extra-detailed explanations for weak-area questions
5. Vary question angles — if the student got "what is X" wrong, ask "why does X matter"
6. Include 1-2 easier questions to build confidence alongside harder ones

Respond with ONLY this JSON structure:
{{
  "questions": [
    {{
      "question_text": "Targeted question about a weak topic?",
      "topic": "3-5 word topic label matching weak area",
      "choices": {{
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
      }},
      "correct_answer": "B",
      "explanation": "Detailed explanation: B is correct because [specific text reference]. This addresses the common confusion about [weak topic]."
    }}
  ]
}}

Generate exactly {n_questions} questions. Output valid JSON only."""

    # ── Response parsing ──────────────────────────────────────────

    def _parse_response(
        self,
        response:   str,
        section_id: int,
    ) -> list[MCQuestion]:
        """
        Parse LLM JSON response into validated MCQuestion objects.

        Validation rules (any failure → question skipped, not crash):
        - question_text must exist and be non-empty
        - choices must have all 4 keys: A, B, C, D
        - correct_answer must be one of: A, B, C, D
        - explanation and topic default if missing
        """
        data = llm_client.parse_json_response(response)

        # LLM might return {"questions": [...]} or [...]
        if isinstance(data, dict):
            raw_questions = data.get("questions") or data.get("mcqs") or []
        elif isinstance(data, list):
            raw_questions = data
        else:
            logger.error(f"Unexpected response type: {type(data)}")
            return []

        questions: list[MCQuestion] = []

        for i, q in enumerate(raw_questions):
            try:
                # Validate required fields
                if not q.get("question_text", "").strip():
                    logger.warning(f"Question {i}: empty question_text, skipping")
                    continue

                choices = q.get("choices", {})
                if not all(k in choices for k in ["A", "B", "C", "D"]):
                    logger.warning(f"Question {i}: incomplete choices {list(choices.keys())}, skipping")
                    continue

                raw_answer = str(q.get("correct_answer", "")).upper().strip()
                if raw_answer not in ("A", "B", "C", "D"):
                    logger.warning(f"Question {i}: invalid correct_answer '{raw_answer}', defaulting to A")
                    raw_answer = "A"

                questions.append(MCQuestion(
                    question_text  = q["question_text"].strip(),
                    choices        = {k: str(v) for k, v in choices.items()},
                    correct_answer = raw_answer,
                    explanation    = q.get("explanation", "See source text.").strip(),
                    topic          = q.get("topic", "General").strip(),
                    section_id     = section_id,
                ))

            except Exception as exc:
                logger.error(f"Error parsing question {i}: {exc}")
                continue

        return questions

    def _truncate_content(self, content: str) -> str:
        """
        Limit section content to _MAX_CONTENT_WORDS words.
        Prevents hitting LLM token limits on long sections.
        """
        words = content.split()
        if len(words) > _MAX_CONTENT_WORDS:
            logger.info(
                f"Section content truncated: {len(words)} → {_MAX_CONTENT_WORDS} words"
            )
            return " ".join(words[:_MAX_CONTENT_WORDS])
        return content

    def _make_fallback(self, section: PDFSection) -> MCQuestion:
        """
        Fallback question when LLM generation fails entirely.
        Ensures the session doesn't crash — always returns at least one question.
        """
        return MCQuestion(
            question_text  = f"What is the primary focus of {section.title}?",
            choices        = {
                "A": "[LLM error — could not generate question]",
                "B": "Check logs for details",
                "C": "Retry the session",
                "D": "Verify your API key in .env",
            },
            correct_answer = "A",
            explanation    = "This is a fallback question. The LLM failed to generate a real question. Check logs.",
            topic          = "System Fallback",
            section_id     = section.section_id,
        )


# ─── Global singleton ─────────────────────────────────────────────
mcq_generator = MCQGenerator()