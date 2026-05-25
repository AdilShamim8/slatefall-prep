"""
api/routes.py
─────────────
All REST API endpoints.

Endpoints:
  GET  /api/v1/sections              — list available PDF sections
  POST /api/v1/sessions/start        — run a prep session
  GET  /api/v1/sessions/history      — get past sessions
  GET  /api/v1/sessions/weak-topics  — get weak topics for sections
  GET  /api/v1/kb/snapshot           — get KB snapshot
"""

import traceback

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.pdf_parser import pdf_parser
from core.session_manager import session_manager
from kb.queries import kb
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ─── Request / Response Models ────────────────────────────────────

class StartSessionRequest(BaseModel):
    section_ids:          list[int] = Field(..., example=[5, 8])
    n_per_section:        int       = Field(default=5, ge=1, le=20)
    simulate_answers:     bool      = Field(default=True)
    simulation_accuracy:  float     = Field(default=0.6, ge=0.0, le=1.0)


# ─── Endpoints ────────────────────────────────────────────────────

@router.get("/sections", tags=["PDF"])
def list_sections():
    """List all sections detected in the SLATEFALL PDF."""
    try:
        pdf_parser.load()
        sections = pdf_parser.get_all_sections()
        return {
            "total_sections": len(sections),
            "sections":       [s.to_dict() for s in sections],
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/start", tags=["Sessions"])
def start_session(req: StartSessionRequest):
    """
    Start a prep session over the specified sections.
    Automatically adapts if prior history exists.
    """
    try:
        result = session_manager.run_session(
            section_ids         = req.section_ids,
            n_per_section       = req.n_per_section,
            simulate_answers    = req.simulate_answers,
            simulation_accuracy = req.simulation_accuracy,
            interactive         = False,
        )
        return result.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/history", tags=["Sessions"])
def get_history(section_ids: str = Query(default=None, example="5,8")):
    """
    Get session history. Optionally filter by section IDs.
    section_ids: comma-separated, e.g. "5,8"
    """
    try:
        if section_ids:
            ids = [int(x.strip()) for x in section_ids.split(",")]
        else:
            ids = list(range(1, 11))

        sessions = kb.get_sessions_for_sections(ids)
        return {
            "total":    len(sessions),
            "sessions": [s.to_dict() for s in sessions],
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/weak-topics", tags=["Sessions"])
def get_weak_topics(section_ids: str = Query(..., example="5,8")):
    """Get weak topics for given sections. section_ids: comma-separated."""
    try:
        ids   = [int(x.strip()) for x in section_ids.split(",")]
        topics = kb.get_weak_topics(ids)
        return {"section_ids": ids, "weak_topics": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kb/snapshot", tags=["Knowledge Base"])
def get_kb_snapshot(top_n: int = Query(default=5, ge=1, le=20)):
    """Get the most recent N sessions as a human-readable snapshot."""
    try:
        snapshot = kb.get_kb_snapshot(top_n=top_n)
        return {"total_sessions_in_snapshot": len(snapshot), "sessions": snapshot}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))