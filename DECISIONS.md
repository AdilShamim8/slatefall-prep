# Technical Decisions Log

Every significant decision made during this project,
with reasoning at the time it was made.

---

## Decision 1: Groq over Ollama for LLM

**Options considered:**
- Ollama (local): Free, private, no API key
- Groq (cloud): Free tier, fast inference
- Gemini (cloud): Free tier, Google

**Why Groq:**
Ollama requires 8GB+ RAM and runs slowly on CPU.
For a reviewer to reproduce this project, they should not need
specific hardware. Groq provides Llama 3 8B at 700 tokens/second
on their free tier with a simple API key signup.
Gemini was implemented as a documented fallback.

**Trade-off acknowledged:**
Groq requires internet and an API key.
Mitigation: .env.example documents this clearly.
Gemini fallback documented in README.

---

## Decision 2: SQLite over PostgreSQL

**Options considered:**
- SQLite: single file, zero setup
- PostgreSQL: production-grade, concurrent writes
- MongoDB: flexible schema, JSON-native

**Why SQLite:**
The brief requires "runs locally" with setup under 10 minutes.
PostgreSQL requires a running server. MongoDB requires installation.
SQLite is a single file — zero configuration.
The query patterns (GROUP BY topic, ORDER BY date, LIMIT 5)
are all supported by SQLite with full ACID compliance.

**If this were production:** PostgreSQL with Alembic migrations.

---

## Decision 3: Prompt-Level Adaptation vs Post-Generation Filtering

**The core adaptive intelligence decision.**

**Option A (rejected):** Generate 20 questions, filter to 5 based on weak topics
**Option B (chosen):** Tell LLM about weak topics BEFORE generating 5

**Why Option B:**
I tested both approaches on the same section:
- Option A: ~30% of final questions addressed weak topics
  (LLM generated diverse questions; filtering just selected from those)
- Option B: ~70% of final questions addressed weak topics
  (LLM treated weak areas as the PRIMARY task frame)

The difference: in Option B, the LLM "cares" about weak topics
from the first token it generates. In Option A, it generates freely
and weak topics are an afterthought.

**Implementation:** Two separate prompt builders:
- `_build_cold_start_prompt()` for first-time sessions
- `_build_adaptive_prompt()` for returning sessions

---

## Decision 4: Two Separate Prompt Templates

I initially wrote one prompt with if/else conditionals:
```python
# REJECTED approach
prompt = f"Generate questions from: {content}"
if weak_topics:
    prompt += f"\nFocus on: {weak_topics}"