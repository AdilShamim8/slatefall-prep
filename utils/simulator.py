"""
utils/simulator.py
──────────────────
Simulates user answers for evaluation purposes.

WHY simulation (from assessment brief):
"You do not need to recruit a human tester. Simulate a realistic
mix of correct and incorrect responses for Scenario B to demonstrate
adaptive behavior."

Design decisions:
- Base accuracy: 60% (realistic learner, not perfect, not random)
- Weak topic penalty: 40% accuracy on previously-wrong topics
  This creates real weak topic data in the KB for iteration 2 and 3
- Reproducible: Optional seed parameter for consistent demo output
"""

import random
from typing import Any

from core.mcq_generator import MCQuestion
from utils.logger import get_logger

logger = get_logger(__name__)


class AnswerSimulator:
    """
    Simulates user answers with configurable accuracy.

    Realistic behavior:
    - Gets most questions right (accuracy=0.6 default)
    - Gets weak-topic questions wrong more often (lower accuracy)
    - Slight randomness — not perfectly predictable
    """

    def __init__(
        self,
        accuracy: float       = 0.6,
        seed:     int | None  = None,
    ):
        """
        Args:
            accuracy: Probability of correct answer (0.0-1.0)
            seed:     Random seed for reproducible outputs
        """
        if not 0.0 <= accuracy <= 1.0:
            raise ValueError(f"accuracy must be 0.0-1.0, got {accuracy}")

        self.accuracy = accuracy

        if seed is not None:
            random.seed(seed)
            logger.info(f"AnswerSimulator | accuracy={accuracy:.0%} | seed={seed}")
        else:
            logger.info(f"AnswerSimulator | accuracy={accuracy:.0%} | seed=random")

    def simulate_answer(
        self,
        question:         MCQuestion,
        weak_topic_names: list[str] | None = None,
    ) -> str:
        """
        Simulate an answer to a single question.

        If the question's topic is in weak_topic_names:
        → Use lower accuracy (simulates continued struggle)

        Returns: "A", "B", "C", or "D"
        """
        weak_topic_names = weak_topic_names or []

        # Lower accuracy for known weak topics
        if question.topic in weak_topic_names:
            effective_accuracy = min(self.accuracy, 0.35)
        else:
            effective_accuracy = self.accuracy

        if random.random() < effective_accuracy:
            return question.correct_answer
        else:
            wrong_choices = [
                c for c in ["A", "B", "C", "D"]
                if c != question.correct_answer
            ]
            return random.choice(wrong_choices)

    def simulate_batch(
        self,
        questions:        list[MCQuestion],
        weak_topic_names: list[str] | None = None,
    ) -> list[str]:
        """
        Simulate answers for a full list of questions.

        Returns: List of answer strings parallel to questions list
        """
        answers = [
            self.simulate_answer(q, weak_topic_names)
            for q in questions
        ]

        correct = sum(
            1 for q, a in zip(questions, answers)
            if a == q.correct_answer
        )
        logger.info(
            f"Simulated {len(answers)} answers | "
            f"{correct}/{len(answers)} correct "
            f"({correct/len(answers):.0%})"
        )

        return answers