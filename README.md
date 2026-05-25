# Adaptive Document Preparation System
### SLATEFALL — Cloudly AI/ML Intern Assessment
**Submitted by:** Adil Shamim

An AI-powered adaptive study system that generates MCQs from the
SLATEFALL operational dossier, tracks performance history, and
focuses each subsequent session on the user's weak areas.

---

## ⚠️ Important: PDF Required

The `SLATEFALL_DOSSIER.pdf` was provided by Cloudly via email.
Place it at `data/SLATEFALL_DOSSIER.pdf` before running any commands.

---

## Quick Start (Under 10 Minutes)

```bash
# 1. Clone
git clone https://github.com/AdilShamim8/slatefall-prep.git
cd slatefall-prep

# 2. Virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env → add your GROQ_API_KEY
# Free key at: https://console.groq.com

# 5. Add PDF
# Place SLATEFALL_DOSSIER.pdf in data/

# 6. Verify
python main.py list-sections
```

---

## Running the Evaluation Scenarios

### Scenario A — Cold Start
```bash
python main.py scenario-a -s 1 -s 2
# Output: outputs/scenario_a_iter1/
```

### Scenario B — Three Adaptive Iterations (Main Evaluation)
```bash
python main.py scenario-b
# Output:
#   outputs/scenario_b_iter1/  ← is_adaptive: false (cold start)
#   outputs/scenario_b_iter2/  ← is_adaptive: true  (uses iter 1 history)
#   outputs/scenario_b_iter3/  ← is_adaptive: true  (uses iter 1+2 history)
```

### Interactive Mode (Answer Questions Yourself)
```bash
python main.py interactive -s 1 -s 2
```

### REST API
```bash
python main.py api
# Docs at: http://localhost:8000/docs
```

### Streamlit UI (Optional)
```bash
streamlit run streamlit_app.py
# Opens at: http://localhost:8501
```

### Tests
```bash
pytest tests/ -v
```

---

## How Adaptive Intelligence Works

```
Session 1 (sections 5, 8) — Cold Start:
  KB is empty → generate balanced questions
  User answers → 4/10 correct
  KB stores: wrong answers on "PAMC Protocol" (3x), "Authorization" (1x)

Session 2 (sections 6, 8, 9) — Adaptive:
  KB has history → query weak topics for section 8
  Adaptive prompt: "Focus 60% of questions on PAMC Protocol"
  Previously asked questions listed → LLM avoids repeating them
  Result: targeted questions on user's actual weak areas

Session 3 (section 8 only) — Adaptive:
  KB now has 2 sessions of history
  More weak topics accumulated → stronger adaptation signal
  Questions specifically target persistent weak areas
```

The adaptation happens at **prompt level** — the LLM receives
the weak topic context before generating, not after.

---

## Project Architecture

```
CLI (main.py)  ←→  REST API (api/)  ←→  Streamlit UI
                        |
                  SessionManager
                  (core/session_manager.py)
                        |
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
    AdaptiveEngine   PDFParser    MCQGenerator
    (checks KB)     (reads PDF)  (builds prompts)
          |                           |
     KnowledgeBase               LLMClient
     (SQLite)                    (Groq API)
```

---

## Knowledge Base Schema

**PrepSession** — one row per study session
```
id | section_ids | created_at | score | total_questions
   | correct_count | is_adaptive | weak_topics_used (JSON)
```

**QuestionResult** — one row per question asked
```
id | session_id (FK) | section_id | question_text | topic
   | choices (JSON) | correct_answer | user_answer
   | is_correct | explanation
```

**Key query patterns:**
- Sessions by section → string match on `section_ids` column
- Weak topics → `GROUP BY topic WHERE is_correct=0 ORDER BY count DESC`
- KB snapshot → `ORDER BY created_at DESC LIMIT 5`

---

## Stack Choices & Reasoning

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Groq + Llama 3 8B | Free tier, 700 tok/s, no GPU needed |
| PDF | PyMuPDF | Fast, reliable text extraction |
| Database | SQLite + SQLAlchemy | Zero setup, ACID, sufficient locally |
| API | FastAPI + Pydantic | Auto-docs, type safety, validation |
| CLI | Click + Rich | Clean commands, beautiful output |
| UI | Streamlit | Pure Python, fast to build |

---

## Section Mapping

Run `python main.py list-sections` to see all detected sections.

If the PDF heading format does not match the regex patterns,
the system falls back to equal page-based splitting (10 sections).
The fallback always produces working sections regardless of PDF format.

---

## Known Limitations

1. **Question deduplication** uses exact string matching, not semantic
   similarity. Two questions about the same concept with different wording
   could both appear. Fix: sentence embeddings + cosine similarity.

2. **LLM yield variability** — LLM sometimes returns fewer questions
   than requested (~10% of calls). System continues with partial set
   and logs a warning.

3. **Section detection** depends on regex pattern matching PDF headings.
   Run `list-sections` to verify detection worked. Fallback always active.

4. **Simulated answers** use fixed accuracy (60% correct, 35% on weak
   topics). This is artificial but creates realistic KB data for
   demonstrating adaptive behavior.

---

## Pre-Generated Evaluation Outputs

The `outputs/` folder contains pre-generated results
from running both scenarios, so reviewers can verify
adaptive behavior without running the full system:

```
outputs/scenario_a_iter1/   ← cold start demo
outputs/scenario_b_iter1/   ← iter 1: is_adaptive=false
outputs/scenario_b_iter2/   ← iter 2: is_adaptive=true
outputs/scenario_b_iter3/   ← iter 3: is_adaptive=true, more weak topics
```