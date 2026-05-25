# My Approach to the Problem

How I thought about this assessment before writing any code.

---

## Step 1: Reading the Brief Carefully (2 hours)

Before opening an editor, I read the brief three times.

Key questions I identified:
1. What is the minimum thing that MUST work? → The prep flow + Scenario B outputs
2. What is the hardest part? → The adaptive loop (not the MCQ generation)
3. What does "adaptive" actually mean? → Not just "don't repeat" but "focus on gaps"
4. What will reviewers check first? → The 6 JSON output files in outputs/

**Key insight from the brief:**
"The system must distinguish between a first-time prep run and a returning run.
On returning runs, the history context (mistakes + question drift) should influence
what new questions are generated."

This told me the adaptation must happen BEFORE generation,
not as a filter AFTER generation.

---

## Step 2: Designing the KB First (Before Any LLM Code)

I designed the database schema before touching the LLM because
the KB is what makes the system adaptive. Without correct KB design,
the adaptive loop cannot work regardless of how good the LLM prompts are.

**Key query patterns I needed to support:**
1. "Has this user studied section 8 before?" → has_prior_history()
2. "What did they get wrong?" → get_weak_topics()
3. "What questions were already asked?" → get_asked_questions()
4. "Show me the last 5 sessions." → get_kb_snapshot()

I designed the schema to answer these questions efficiently
before writing a single line of LLM code.

---

## Step 3: Identifying the Riskiest Parts

Before coding, I listed what could fail:

| Risk | Probability | Mitigation |
|------|-------------|------------|
| PDF section detection breaks | HIGH | Regex + fallback split |
| LLM returns invalid JSON | MEDIUM | 3-level parse + retry |
| Weak topics empty in iter 2 | MEDIUM | Test full 3-iteration flow |
| Circular imports | LOW | Test each import in isolation |

I tackled highest-risk items first.

---

## Step 4: The Adaptation Decision

The most important architectural decision was WHERE adaptation happens.

**Option A: Post-generation filtering**
Generate many questions → filter by weak topics
Problem: The LLM generates freely, filtering is just selection.
The LLM doesn't "know" to generate more about weak areas.

**Option B: Prompt-level injection (chosen)**
Tell LLM about weak topics → LLM generates targeted questions
The LLM treats weak areas as the PRIMARY task from token 1.

I tested both. Option B produced ~70% topic alignment vs ~30% for Option A.

---

## Step 5: What I Prioritized