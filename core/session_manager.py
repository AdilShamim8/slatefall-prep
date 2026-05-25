"""
core/session_manager.py
───────────────────────
Orchestrates a complete prep session end-to-end.

Flow:
  1. Ask AdaptiveEngine to prepare questions
  2. Present questions (interactive CLI or auto-simulate)
  3. Score answers
  4. Save everything to KB
  5. Return complete SessionResult

The SessionManager is the "conductor" — it coordinates all other
components but contains minimal business logic itself.
"""

from dataclasses import dataclass, field
from typing import Any

from core.adaptive_engine import adaptive_engine
from core.mcq_generator import MCQuestion
from kb.queries import kb
from utils.logger import get_logger
from utils.simulator import AnswerSimulator

logger = get_logger(__name__)


@dataclass
class SessionResult:
    """
    Complete results from one prep session.
    Passed to exporter to generate output JSON files.
    """
    session_id:       int
    section_ids:      list[int]
    questions:        list[dict[str, Any]]   # question dicts with user answers
    score:            float
    correct_count:    int
    total_count:      int
    is_adaptive:      bool
    weak_topics_used: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id":       self.session_id,
            "section_ids":      self.section_ids,
            "score":            round(self.score, 4),
            "correct_count":    self.correct_count,
            "total_count":      self.total_count,
            "percentage":       f"{self.score:.1%}",
            "is_adaptive":      self.is_adaptive,
            "weak_topics_used": self.weak_topics_used,
            "questions":        self.questions,
        }


class SessionManager:
    """Runs complete prep sessions."""

    def run_session(
        self,
        section_ids:          list[int],
        n_per_section:        int   = 5,
        simulate_answers:     bool  = False,
        simulation_accuracy:  float = 0.6,
        interactive:          bool  = True,
    ) -> SessionResult:
        """
        Run one complete prep session.

        Args:
            section_ids:         Sections to study
            n_per_section:       Questions per section
            simulate_answers:    If True, auto-generate answers (Scenario B)
            simulation_accuracy: Accuracy for simulated answers
            interactive:         If True, prompt user via CLI

        Returns:
            SessionResult with all question data and scores
        """
        logger.info(
            f"Session starting | sections={section_ids} | "
            f"n_per_section={n_per_section} | "
            f"simulate={simulate_answers}"
        )

        # ── Step 1: Generate questions ────────────────────────────
        questions, metadata = adaptive_engine.prepare_session(
            section_ids   = section_ids,
            n_per_section = n_per_section,
        )

        if not questions:
            raise RuntimeError(
                "No questions were generated. "
                "Check LLM configuration and PDF parsing."
            )

        is_adaptive      = metadata["is_adaptive"]
        weak_topics_used = metadata.get("weak_topics_used", [])

        # ── Step 2: Collect / simulate answers ───────────────────
        simulator = AnswerSimulator(
            accuracy=simulation_accuracy,
            seed=42 if simulate_answers else None,
        )

        weak_topic_names = [wt["topic"] for wt in weak_topics_used]
        questions_with_results: list[dict[str, Any]] = []

        for i, question in enumerate(questions):
            if simulate_answers:
                user_answer = simulator.simulate_answer(question, weak_topic_names)

            elif interactive:
                user_answer = self._ask_user(question, i + 1, len(questions))

            else:
                # API mode — answer will be submitted separately
                user_answer = None

            is_correct = (user_answer == question.correct_answer) if user_answer else False

            # Build complete question record
            q_record = question.to_dict()
            q_record.update({
                "user_answer":    user_answer,
                "is_correct":     is_correct,
                "question_number": i + 1,
            })
            questions_with_results.append(q_record)

            # Show result in interactive mode
            if interactive and not simulate_answers and user_answer:
                self._show_result(question, user_answer, is_correct)

        # ── Step 3: Calculate score ───────────────────────────────
        total   = len(questions_with_results)
        correct = sum(1 for q in questions_with_results if q["is_correct"])
        score   = correct / total if total > 0 else 0.0

        # ── Step 4: Save to KB ────────────────────────────────────
        saved = kb.save_session(
            section_ids           = section_ids,
            questions_and_results = questions_with_results,
            is_adaptive           = is_adaptive,
            weak_topics_used      = weak_topic_names,
        )

        logger.info(
            f"Session {saved.id} complete | "
            f"score={score:.1%} ({correct}/{total}) | "
            f"adaptive={is_adaptive}"
        )

        # ── Step 5: Return result ─────────────────────────────────
        return SessionResult(
            session_id       = saved.id,
            section_ids      = section_ids,
            questions        = questions_with_results,
            score            = score,
            correct_count    = correct,
            total_count      = total,
            is_adaptive      = is_adaptive,
            weak_topics_used = weak_topics_used,
        )

    # ── Interactive CLI helpers ───────────────────────────────────

    def _ask_user(
        self,
        question:     MCQuestion,
        question_num: int,
        total:        int,
    ) -> str:
        """Display a question and collect the user's answer."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        console.print(f"\n[bold cyan]Question {question_num} of {total}[/bold cyan]")
        console.print(Panel(question.question_text, expand=False))
        console.print(f"[dim]Section {question.section_id} — {question.topic}[/dim]\n")

        for letter, text in question.choices.items():
            console.print(f"  [yellow]{letter})[/yellow]  {text}")

        while True:
            ans = input("\n  Your answer (A/B/C/D): ").strip().upper()
            if ans in ("A", "B", "C", "D"):
                return ans
            print("  Please enter A, B, C, or D.")

    def _show_result(
        self,
        question:   MCQuestion,
        user_answer: str,
        is_correct:  bool,
    ) -> None:
        """Show whether the answer was right or wrong."""
        from rich.console import Console

        console = Console()

        if is_correct:
            console.print("\n  [bold green]✓ Correct![/bold green]")
        else:
            console.print("\n  [bold red]✗ Incorrect[/bold red]")
            console.print(
                f"  Correct answer: "
                f"[bold green]{question.correct_answer})[/bold green] "
                f"{question.choices[question.correct_answer]}"
            )
            console.print(
                f"\n  [italic]Explanation:[/italic] "
                f"{question.explanation}"
            )


# ─── Global singleton ─────────────────────────────────────────────
session_manager = SessionManager()