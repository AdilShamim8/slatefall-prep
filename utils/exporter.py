"""
utils/exporter.py
─────────────────
Exports session outputs to JSON files for assessment evaluation.

Required by assessment spec:
  outputs/scenario_b_iter1/questions_iter1.json
  outputs/scenario_b_iter1/kb_snapshot_iter1.json
  (same for iter2 and iter3)

The KB snapshot is what reviewers inspect to verify:
1. Sessions are stored correctly
2. Adaptive prompting used real history (not fabricated)
3. Weak topics accumulate across iterations
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from kb.queries import kb
from utils.logger import get_logger

logger = get_logger(__name__)


def export_iteration_outputs(
    iteration:     int,
    scenario:      str,
    session_result: Any,           # SessionResult object
    output_base:   Path | None = None,
) -> dict[str, Path]:
    """
    Write questions_iter{N}.json and kb_snapshot_iter{N}.json
    for one evaluation iteration.

    Args:
        iteration:      1, 2, or 3
        scenario:       "scenario_a" or "scenario_b"
        session_result: The completed SessionResult
        output_base:    Base directory (defaults to outputs/)

    Returns:
        Dict with paths to the two files written
    """
    from config import OUTPUTS_DIR
    base = output_base or OUTPUTS_DIR

    # Create iteration directory
    out_dir = base / f"{scenario}_iter{iteration}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── File 1: questions_iter{N}.json ────────────────────────────
    questions_data = {
        "metadata": {
            "iteration":        iteration,
            "scenario":         scenario,
            "session_id":       session_result.session_id,
            "section_ids":      session_result.section_ids,
            "is_adaptive":      session_result.is_adaptive,
            "total_questions":  session_result.total_count,
            "correct_answers":  session_result.correct_count,
            "score_percentage": f"{session_result.score:.1%}",
            "generated_at":     datetime.utcnow().isoformat(),
            "weak_topics_used": session_result.weak_topics_used,
        },
        "questions": session_result.questions,
    }

    q_path = out_dir / f"questions_iter{iteration}.json"
    _write_json(questions_data, q_path)
    logger.info(f"Questions exported → {q_path}")

    # ── File 2: kb_snapshot_iter{N}.json ─────────────────────────
    snapshot_data = {
        "metadata": {
            "iteration":        iteration,
            "scenario":         scenario,
            "snapshot_taken_at": datetime.utcnow().isoformat(),
            "current_session_id": session_result.session_id,
            "description": (
                "Top-5 most recent sessions at the moment this "
                "iteration completed. Reviewers use this to verify "
                "KB state and adaptive prompting grounds in real data."
            ),
        },
        "recent_sessions": kb.get_kb_snapshot(top_n=5),
    }

    s_path = out_dir / f"kb_snapshot_iter{iteration}.json"
    _write_json(snapshot_data, s_path)
    logger.info(f"KB snapshot exported → {s_path}")

    return {"questions": q_path, "kb_snapshot": s_path}


def _write_json(data: Any, path: Path) -> None:
    """Write data to JSON file with pretty formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)