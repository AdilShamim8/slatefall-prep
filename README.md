# Adaptive Document Preparation System
### SLATEFALL — Cloudly AI/ML Intern Assessment

# Project document: [Link](https://docs.google.com/document/d/14upXCJf8E4YKpWpLAjL9auZU-WjrQnbhZNs-x7GbelE/edit?usp=sharing)

An AI-powered study system that generates adaptive MCQs from the SLATEFALL 
operational dossier. Sessions adapt based on your performance history — 
focusing on weak areas and avoiding repetition of mastered content.

---

## Quick Start (Under 10 Minutes)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/slatefall-prep.git
cd slatefall-prep

# 2. Virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — add your GROQ_API_KEY
# Get free key at: https://console.groq.com

# 5. Add the PDF
# Place SLATEFALL_DOSSIER.pdf in the data/ folder

# 6. Verify
python main.py list-sections
```

---

## Evaluation Commands

```bash
# Scenario A — cold start
python main.py scenario-a -s 1 -s 2

# Scenario B — three adaptive iterations (main evaluation)
python main.py scenario-b

# Interactive — answer questions yourself
python main.py interactive -s 1 -s 2

# REST API
python main.py api
# Docs at: http://localhost:8000/docs
```

---

## Architecture

```
CLI (main.py)
     │
     ▼
SessionManager          ← orchestrates the session
     ├── AdaptiveEngine ← cold-start vs adaptive decision
     │        ├── KnowledgeBase (SQLite) ← reads history
     │        └── PDFParser (PyMuPDF)    ← reads sections
     └── MCQGenerator  ← builds prompts, calls LLM
              └── LLMClient (Groq API)   ← generates questions
```

---

## Stack Choices

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Groq + Llama 3 8B | Free tier, fast (700 tok/s), no GPU needed |
| PDF | PyMuPDF | Fast text extraction, reliable on machine-readable PDFs |
| DB | SQLite + SQLAlchemy | Zero setup, ACID, sufficient for local use |
| API | FastAPI + Pydantic | Auto-docs, type safety, async-ready |
| CLI | Click + Rich | Clean commands, beautiful terminal output |

---

## Knowledge Base Schema

**PrepSession**
- `id`, `section_ids` (sorted CSV: "5,8"), `created_at`, `score`
- `total_questions`, `correct_count`, `is_adaptive`, `weak_topics_used`

**QuestionResult**
- `id`, `session_id` (FK), `section_id`, `question_text`, `topic`
- `choices` (JSON), `correct_answer`, `user_answer`, `is_correct`, `explanation`

Key queries supported:
- Sessions by section → string overlap on `section_ids`
- Weak topics → `GROUP BY topic WHERE is_correct=0`  
- KB snapshot → `ORDER BY created_at DESC LIMIT 5`

---

## Adaptive Intelligence

1. **Cold start**: No history → broad, balanced questions
2. **Return run**: KB queried for weak topics + asked questions
3. Weak topics injected as **primary frame** in LLM prompt
4. Previously asked questions listed explicitly (avoid repetition)
5. 60%+ of adaptive questions target weak areas

---

## Section Mapping

Run `python main.py list-sections` to see detected sections.
If regex detection fails, system falls back to equal page splits.
See `core/pdf_parser.py` `_parse_sections()` to adjust patterns.

---

## Known Limitations

- Question deduplication uses exact string match (not semantic similarity)
- LLM sometimes returns fewer questions than requested (~10% of calls)
- Section detection depends on PDF heading format — verify with list-sections
- Simulated answers use fixed accuracy (documented, not real user data)
- LLM explanations may vary — grounded in text but not guaranteed accurate

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/test_kb.py -v          # KB tests only
pytest tests/test_mcq_generator.py  # MCQ tests only
```
