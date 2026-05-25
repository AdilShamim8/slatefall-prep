"""
api/app.py
──────────
FastAPI application setup.

Start with: python main.py api
Then visit:  http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kb.database import init_db
from utils.logger import get_logger

logger = get_logger(__name__)

# Initialize DB on startup
init_db()

app = FastAPI(
    title       = "Adaptive Document Preparation System",
    description = "AI-powered adaptive MCQ generation from the SLATEFALL dossier.",
    version     = "1.0.0",
    docs_url    = "/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# Register routes
from api.routes import router  # noqa: E402
app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Adaptive Document Preparation System",
        "version": "1.0.0",
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}