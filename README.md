# Adaptive Document Preparation System

> **SLATEFALL — Cloudly AI/ML Intern Assessment**
> A backend-driven adaptive learning system that generates targeted MCQs
> from a multi-section PDF, tracks user performance, and progressively
> adapts subsequent sessions to focus on the learner's weak areas.

---

## 📖 Read This First — My Thinking Process Document

> **The assessment brief states:**
> *"We are far more interested in how you approached the problem,
> what you tried, and how hard you worked through it. Show your thinking."*

I have documented my complete thought process — every decision, every
trade-off, every experiment, and every challenge — in a separate
detailed document. **Please read it before evaluating the code:**

### 📄 [**My Approach & Thinking Process — Full Documentation**](https://docs.google.com/document/d/14upXCJf8E4YKpWpLAjL9auZU-WjrQnbhZNs-x7GbelE/edit?usp=sharing)

This document covers:
- How I broke down the problem before writing any code
- Why I chose each technology and rejected alternatives
- The experiments I ran to find the best adaptive prompt strategy
- What broke, how I debugged it, and what I learned
- What I would improve given more time

Three companion documents are also included in this repository:
- [`APPROACH.md`](./APPROACH.md) — How I thought about the problem
- [`DECISIONS.md`](./DECISIONS.md) — Every technical decision with reasoning
- [`CHALLENGES.md`](./CHALLENGES.md) — What went wrong and how I fixed it

---

## 🎯 What This System Does

```
User selects PDF sections → Adaptive Engine checks history →
   ↓
First time?  → Generate balanced cold-start questions
Returning?   → Query weak topics + previously asked questions
   ↓
LLM generates targeted MCQs (4 choices + explanation per question)
   ↓
User answers (or system simulates) → Score each answer
   ↓
Persist everything to Knowledge Base → Influences next session
```

**The core differentiator:** Adaptation happens at the **prompt level**,
not as post-generation filtering. The LLM is told about weak topics
*before* it generates anything, so questions are targeted from the
first token. Tested approaches produced ~70% topic alignment versus
~30% with post-filtering.

---

## ⚠️ Important — PDF Required

The `SLATEFALL_DOSSIER.pdf` was provided by Cloudly via email.

**Place it at this exact path before running any commands:**
```
data/SLATEFALL_DOSSIER.pdf
```

The PDF is intentionally not committed to this repository (size and
distribution rights). All pre-generated output files in `outputs/`
demonstrate the system working with this exact PDF.

---

## 🚀 Quick Start (Under 10 Minutes)

### Prerequisites
- Python 3.10 or higher
- Free Groq API key — get one at [console.groq.com](https://console.groq.com)
- The SLATEFALL_DOSSIER.pdf file

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/AdilShamim8/slatefall-prep.git
cd slatefall-prep

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate              # Mac/Linux
# venv\Scripts\activate               # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Open .env in any editor and set: GROQ_API_KEY=your_key_here

# 5. Place the PDF
# Put SLATEFALL_DOSSIER.pdf inside the data/ folder

# 6. Verify the setup
python main.py list-sections
```

If `list-sections` shows a table of detected sections — you are ready.

---

## 🎮 Running the Evaluation Scenarios

### Scenario A — Cold Start
Demonstrates a first-time session over any two sections.

```bash
python main.py scenario-a -s 1 -s 2
```
**Output:** `outputs/scenario_a_iter1/`

---

### Scenario B — Three Adaptive Iterations (Main Evaluation)
This is the core requirement. Three consecutive sessions demonstrate
how the system progressively adapts based on accumulated history.

```bash
python main.py scenario-b
```

**Iteration breakdown:**

| Iteration | Sections    | Behavior                                    |
|-----------|-------------|---------------------------------------------|
| Iter 1    | 5, 8        | Cold start (no history exists)              |
| Iter 2    | 6, 8, 9     | Adaptive (uses Iter 1 history for sec 8)    |
| Iter 3    | 8           | Strongly adaptive (uses Iter 1+2 history)   |

**Outputs:**
```
outputs/scenario_b_iter1/
  ├── questions_iter1.json       (is_adaptive: false)
  └── kb_snapshot_iter1.json     (1 session in history)

outputs/scenario_b_iter2/
  ├── questions_iter2.json       (is_adaptive: true)
  └── kb_snapshot_iter2.json     (2 sessions in history)

outputs/scenario_b_iter3/
  ├── questions_iter3.json       (is_adaptive: true)
  └── kb_snapshot_iter3.json     (3 sessions in history)
```

---

### Other Commands

```bash
# Answer questions yourself instead of simulating
python main.py interactive -s 1 -s 2

# Start the REST API server
python main.py api
# Documentation auto-generated at: http://localhost:8000/docs

# Launch the Streamlit web UI
streamlit run streamlit_app.py
# Opens at: http://localhost:8501

# Run the test suite
pytest tests/ -v
```

---

## 🧠 How Adaptive Intelligence Works

The system distinguishes between cold-start and adaptive sessions
through a deliberate three-step process:

### Step 1: History Check
When a session begins, `AdaptiveEngine` queries the Knowledge Base:
```python
has_history = kb.has_prior_history(section_ids)
```

### Step 2: Context Gathering (only if returning user)
```python
weak_topics      = kb.get_weak_topics(section_ids, min_wrong_count=1)
previously_asked = kb.get_asked_questions(section_ids)
```

### Step 3: Prompt Selection
Two completely separate prompt builders are used:

**Cold Start Prompt** — balanced coverage, no history context:
```
"Generate N MCQs from this text covering different concepts..."
```

**Adaptive Prompt** — weak topics as the PRIMARY frame:
```
"You are an ADAPTIVE quiz creator. A student has struggled with:
  - 'PAMC Protocol' (wrong 3 times)
  - 'Authorization Levels' (wrong 2 times)

Do NOT repeat these previously asked questions: [...]

Allocate 60%+ of questions to these weak topics..."
```

### Why Prompt-Level Adaptation?
I tested two approaches:
- **Post-generation filtering** (rejected): ~30% topic alignment
- **Prompt-level injection** (chosen): ~70% topic alignment

The difference: when weak topics are the primary frame of the prompt,
the LLM treats them as the core task. When appended at the end, they
become an afterthought. This insight shaped the entire architecture.

---

## 🏗️ System Architecture

```
                    ┌─────────────────────────────┐
                    │  CLI / REST API / Streamlit │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      SessionManager         │
                    │   (orchestrates flow)       │
                    └──┬──────────────┬───────────┘
                       │              │
        ┌──────────────▼──┐      ┌────▼────────────────┐
        │ AdaptiveEngine  │      │  MCQGenerator       │
        │ (decides cold   │      │  (cold + adaptive   │
        │  vs adaptive)   │      │   prompt builders)  │
        └──┬──────────┬───┘      └────┬────────────────┘
           │          │               │
    ┌──────▼───┐  ┌───▼──────┐   ┌───▼──────────┐
    │  KB      │  │PDFParser │   │  LLMClient   │
    │ (SQLite) │  │(PyMuPDF) │   │ (Groq/Gemini)│
    └──────────┘  └──────────┘   └──────────────┘
```

Each component has a single responsibility and is independently testable.

---

## 💾 Knowledge Base Schema

### `PrepSession` — one row per study session

| Column            | Type     | Purpose                                       |
|-------------------|----------|-----------------------------------------------|
| id                | Integer  | Primary key                                   |
| section_ids       | String   | Sorted CSV: "5,8" (consistent matching)       |
| created_at        | DateTime | UTC timestamp                                 |
| score             | Float    | 0.0 to 1.0                                    |
| total_questions   | Integer  | Number of questions in this session           |
| correct_count     | Integer  | Number answered correctly                     |
| is_adaptive       | Boolean  | True if history context was used              |
| weak_topics_used  | JSON     | Topics that influenced this session           |

### `QuestionResult` — one row per question asked

| Column          | Type     | Purpose                                  |
|-----------------|----------|------------------------------------------|
| id              | Integer  | Primary key                              |
| session_id      | Integer  | Foreign key to PrepSession               |
| section_id      | Integer  | Which PDF section                        |
| question_text   | Text     | The actual question                      |
| topic           | String   | Topic label for weak-topic analysis      |
| choices         | JSON     | `{"A": "...", "B": "...", ...}`          |
| correct_answer  | String   | "A", "B", "C", or "D"                    |
| user_answer     | String   | What was answered                        |
| is_correct      | Boolean  | Result                                   |
| explanation     | Text     | Why the correct answer is correct        |

### Query Patterns Supported

```sql
-- Sessions for given sections
SELECT * FROM prep_sessions
WHERE section_ids contains any of [given_ids];

-- Weak topics across all history
SELECT topic, COUNT(*) as wrong_count
FROM question_results
WHERE section_id IN [given_ids] AND is_correct = 0
GROUP BY topic
ORDER BY wrong_count DESC;

-- KB snapshot of last 5 sessions
SELECT * FROM prep_sessions
ORDER BY created_at DESC
LIMIT 5;
```

---

## ⚙️ Stack Choices & Reasoning

Each technology was chosen deliberately. Full reasoning is in
[`DECISIONS.md`](./DECISIONS.md). Summary table:

| Component   | Choice                  | Why                                               |
|-------------|------------------------|----------------------------------------------------|
| LLM         | Groq + Llama 3 8B      | Free, ~700 tok/s, no GPU needed, easy setup       |
| LLM Fallback| Gemini Flash           | Free tier, swap via .env, no code changes         |
| PDF Parsing | PyMuPDF (fitz)         | Fast, reliable on machine-readable PDFs           |
| Database    | SQLite + SQLAlchemy    | Zero setup, ACID, sufficient for local use        |
| API         | FastAPI + Pydantic     | Auto-docs at /docs, type-safe, async-ready        |
| CLI         | Click + Rich           | Clean commands, beautiful terminal output         |
| UI          | Streamlit              | Pure Python, fastest to build, dark theme         |
| Reliability | tenacity               | Retry LLM calls with exponential backoff          |
| Testing     | pytest                 | Industry standard, clean fixtures                 |

### What I Deliberately Did NOT Use

| Rejected         | Reason                                                  |
|------------------|---------------------------------------------------------|
| Ollama           | Requires 8GB+ RAM and GPU for good performance          |
| PostgreSQL       | Server setup violates "10-minute reviewer" requirement  |
| ChromaDB / FAISS | Vector search not needed — queries are relational       |
| LangChain        | Adds abstraction overhead for direct API calls          |
| Docker (in core) | Optional enhancement; CLI must work without it          |

---

## 📁 Project Structure

```
slatefall-prep/
│
├── main.py                     # CLI entry point (Click + Rich)
├── streamlit_app.py            # Optional Streamlit UI
├── config.py                   # Centralized configuration
├── requirements.txt            # Pinned dependencies
├── .env.example                # Template for environment variables
│
├── core/                       # Business logic
│   ├── pdf_parser.py           # PDF ingestion with regex + fallback
│   ├── llm_client.py           # LLM abstraction (Groq/Gemini)
│   ├── mcq_generator.py        # Cold-start + adaptive prompt builders
│   ├── adaptive_engine.py      # Decides cold-start vs adaptive
│   └── session_manager.py      # End-to-end session orchestration
│
├── kb/                         # Knowledge Base layer
│   ├── models.py               # SQLAlchemy table definitions
│   ├── database.py             # Connection + WAL mode
│   └── queries.py              # All read/write operations
│
├── api/                        # REST API layer
│   ├── app.py                  # FastAPI setup
│   └── routes.py               # All endpoints
│
├── utils/                      # Helper utilities
│   ├── logger.py               # Structured logging to console + file
│   ├── simulator.py            # Realistic answer simulation
│   └── exporter.py             # JSON output file generation
│
├── tests/                      # Test suite
│   ├── test_pdf_parser.py
│   ├── test_kb.py
│   ├── test_mcq_generator.py
│   └── test_session.py
│
├── data/                       # Input data (PDF goes here)
├── kb_store/                   # SQLite database (auto-created)
├── outputs/                    # Evaluation outputs (committed)
│
├── APPROACH.md                 # How I thought about the problem
├── DECISIONS.md                # Technical decisions with reasoning
└── CHALLENGES.md               # What went wrong and how I fixed it
```

---

## 🔌 REST API Endpoints

Start the server with `python main.py api`, then visit
[http://localhost:8000/docs](http://localhost:8000/docs) for
interactive Swagger documentation.

| Method | Endpoint                           | Purpose                                |
|--------|------------------------------------|----------------------------------------|
| GET    | `/api/v1/sections`                 | List all detected PDF sections         |
| POST   | `/api/v1/sessions/start`           | Run a complete prep session            |
| GET    | `/api/v1/sessions/history`         | Get past sessions (filter by section)  |
| GET    | `/api/v1/sessions/weak-topics`     | Get weak topics for given sections     |
| GET    | `/api/v1/kb/snapshot`              | Get most recent N sessions             |
| GET    | `/health`                          | Health check                           |

---

## 🧪 Testing

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run specific test files
pytest tests/test_kb.py -v
pytest tests/test_mcq_generator.py -v

# Run a single test
pytest tests/test_kb.py::TestKBQuery::test_weak_topics_identifies_wrong_answers -v
```

Tests cover:
- PDF parsing with fallback behavior
- KB save/retrieve operations
- Weak topic identification across sessions
- MCQ parsing with malformed responses
- Adaptive vs cold-start prompt construction
- Session simulation with weak topic penalty

---

## 📌 Section Mapping

Run `python main.py list-sections` to see all detected sections
and their page ranges.

### What if section detection finds wrong sections?
The PDF parser uses regex patterns to detect headings. If the
SLATEFALL PDF uses an unusual format, the system automatically
falls back to **equal page-based splitting** (10 sections of
roughly equal page count). This guarantees the system always
works, regardless of PDF format.

To customize regex patterns for your PDF, edit
`core/pdf_parser.py` → `_parse_sections()`. Multiple patterns
are tried in order; first match wins.

---

## 🚧 Known Limitations

I am honest about what this system does and does not do well.
Full discussion in [`CHALLENGES.md`](./CHALLENGES.md).

### 1. Question Deduplication is String-Based
Currently uses exact string matching to avoid repeating previously
asked questions. The LLM could rephrase the same concept and slip
through. **Fix with more time:** sentence embeddings + cosine similarity.

### 2. LLM Yield is Variable
The LLM occasionally returns fewer questions than requested
(roughly 10% of calls). The system logs a warning and continues
with the partial set rather than failing the entire session.

### 3. Section Detection Depends on PDF Format
Regex patterns may not match all PDFs. The page-split fallback
always produces working sections, but with generic titles.
Always verify with `python main.py list-sections`.

### 4. Simulated Answers Are Synthetic
For Scenario B outputs, answers are generated by the AnswerSimulator
with weighted accuracy (60% base, 35% on weak topics). This produces
realistic-looking adaptive behavior, but does not represent real
user data.

### 5. LLM Explanations Are Not Independently Verified
Explanations are generated by the same LLM that generates questions.
For high-stakes use (medical, legal), a human review layer would be
essential. This is an assessment system, not a production tutoring
service.

---

## 🎓 Pre-Generated Evaluation Outputs

The `outputs/` folder contains pre-generated results from running
both scenarios, so reviewers can verify adaptive behavior immediately
without needing to install dependencies or run the system:

```
outputs/
├── scenario_a_iter1/         # Cold-start demonstration
│   ├── questions_iter1.json
│   └── kb_snapshot_iter1.json
│
├── scenario_b_iter1/         # is_adaptive: false (first session)
│   ├── questions_iter1.json
│   └── kb_snapshot_iter1.json
│
├── scenario_b_iter2/         # is_adaptive: true (uses iter 1)
│   ├── questions_iter2.json
│   └── kb_snapshot_iter2.json
│
└── scenario_b_iter3/         # is_adaptive: true (uses iter 1+2)
    ├── questions_iter3.json
    └── kb_snapshot_iter3.json
```

### How to Verify Adaptive Behavior from Outputs

Open `outputs/scenario_b_iter2/questions_iter2.json` and check:
```json
{
  "metadata": {
    "is_adaptive": true,
    "weak_topics_used": [...],    ← should not be empty
    ...
  }
}
```

Then open `outputs/scenario_b_iter2/kb_snapshot_iter2.json` to see
the full session history that drove the adaptation.

---

## 🎯 Evaluation Criteria Alignment

This submission is built explicitly against the rubric in the brief:

| Dimension              | Weight | Where to Look                                 |
|------------------------|--------|-----------------------------------------------|
| Functional Correctness | 30%    | `python main.py scenario-b` runs end-to-end   |
| Knowledge Base Design  | 20%    | `kb/models.py`, `kb/queries.py`, this README  |
| Retrieval / Adaptation | 20%    | `outputs/` JSON files prove adaptive behavior |
| Code Quality           | 10%    | Modular structure, tests, logging, retry      |
| Documentation          | 15%    | This README + 3 companion docs + Google Doc   |
| Optional Enhancements  | 5%     | Streamlit UI, REST API, structured logging    |

---

## 🙏 Acknowledgements

Built for the Cloudly AI/ML Intern Assessment.

**Technologies that made this possible:**
- [Groq](https://console.groq.com) — free, fast LLM inference
- [PyMuPDF](https://pymupdf.readthedocs.io) — excellent PDF parsing
- [FastAPI](https://fastapi.tiangolo.com) — best-in-class Python API framework
- [Streamlit](https://streamlit.io) — Python-only UI development
- [Click](https://click.palletsprojects.com) — clean CLI framework
- [Rich](https://rich.readthedocs.io) — beautiful terminal output

---

## 📬 Submitted By

**Adil Shamim**
GitHub: [@AdilShamim8](https://github.com/AdilShamim8)
Repository: [slatefall-prep](https://github.com/AdilShamim8/slatefall-prep)

---

## 📄 License

MIT License — see [LICENSE](./LICENSE) file.