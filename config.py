"""
config.py
─────────
Central configuration. Every setting lives here.
All values come from .env file — nothing hardcoded.

WHY: If you hardcode paths or API keys anywhere else in the code,
the project breaks on any other machine. Config in one place = 
one place to fix when something changes.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()

# ─── Project Root & Directory Paths ──────────────────────────────
BASE_DIR = Path(__file__).parent

DATA_DIR    = BASE_DIR / "data"
KB_DIR      = BASE_DIR / "kb_store"
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR    = BASE_DIR / "logs"

# Auto-create all required directories on import
for _dir in [DATA_DIR, KB_DIR, OUTPUTS_DIR, LOGS_DIR]:
    _dir.mkdir(exist_ok=True)

# ─── LLM Configuration ───────────────────────────────────────────
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "groq")

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama3-8b-8192")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ─── File Paths ───────────────────────────────────────────────────
PDF_PATH = Path(os.getenv("PDF_PATH", str(DATA_DIR / "SLATEFALL_DOSSIER.pdf")))
DB_PATH  = Path(os.getenv("DB_PATH",  str(KB_DIR  / "knowledge_base.db")))

# ─── Session Settings ─────────────────────────────────────────────
QUESTIONS_PER_SECTION = int(os.getenv("QUESTIONS_PER_SECTION", "5"))

# ─── API Settings ─────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ─── Config Validation ────────────────────────────────────────────
def validate_config() -> list[str]:
    """
    Check for common config problems.
    Returns list of warning strings (empty = all good).
    Call this at startup to catch issues early.
    """
    warnings = []

    if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        warnings.append(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com "
            "and add it to your .env file."
        )

    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        warnings.append(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/app/apikey "
            "and add it to your .env file."
        )

    if not PDF_PATH.exists():
        warnings.append(
            f"PDF not found at {PDF_PATH}. "
            f"Place SLATEFALL_DOSSIER.pdf in the data/ folder."
        )

    return warnings