"""
streamlit_app.py
────────────────
Streamlit UI for the Adaptive Document Preparation System.

Run with:
    streamlit run streamlit_app.py

Pages:
    🏠 Home          → Project overview + quick start
    📚 Study Session → Run prep sessions interactively
    📊 My Progress   → View history and weak topics
    🗂️ Knowledge Base → Inspect the KB snapshots
    ⚙️ Settings      → Configure section count, accuracy
"""

import json
import time
from pathlib import Path

import streamlit as st

# ─── Page Configuration (must be first Streamlit call) ───────────
st.set_page_config(
    page_title  = "SLATEFALL Prep System",
    page_icon   = "📖",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ─── Custom CSS for better styling ───────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .main { background-color: #0e1117; }

    /* Card styling */
    .stat-card {
        background: linear-gradient(135deg, #1e2130, #262d40);
        border: 1px solid #3d4460;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin: 5px;
    }

    /* Question card */
    .question-card {
        background: #1e2130;
        border-left: 4px solid #4f8ef7;
        border-radius: 8px;
        padding: 20px;
        margin: 10px 0;
    }

    /* Correct answer highlight */
    .correct-answer {
        background: rgba(0, 200, 100, 0.1);
        border: 1px solid #00c864;
        border-radius: 8px;
        padding: 10px;
        margin: 5px 0;
    }

    /* Wrong answer highlight */
    .wrong-answer {
        background: rgba(255, 70, 70, 0.1);
        border: 1px solid #ff4646;
        border-radius: 8px;
        padding: 10px;
        margin: 5px 0;
    }

    /* Adaptive badge */
    .adaptive-badge {
        background: linear-gradient(135deg, #4f8ef7, #7b5ea7);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
    }

    /* Cold start badge */
    .cold-badge {
        background: #2d3748;
        color: #a0aec0;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
    }

    /* Score display */
    .score-display {
        font-size: 48px;
        font-weight: bold;
        text-align: center;
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Better button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* Progress bar color */
    .stProgress > div > div {
        background: linear-gradient(90deg, #4f8ef7, #7b5ea7);
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State Initialization ────────────────────────────────
# st.session_state persists data between reruns (like a global variable)

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "page":                "home",
        "current_questions":   [],
        "current_answers":     {},
        "session_submitted":   False,
        "session_result":      None,
        "selected_sections":   [],
        "n_per_section":       5,
        "simulation_accuracy": 0.6,
        "quiz_started":        False,
        "current_q_index":     0,
        "mode":                "simulate",   # "simulate" or "interactive"
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()


# ─── Import project modules ───────────────────────────────────────
# We import here so errors show nicely in the UI

@st.cache_resource
def load_system():
    """
    Load all system components once and cache them.
    @st.cache_resource means this runs only ONCE per app session.
    Returns None components if something fails.
    """
    errors = []

    try:
        from kb.database import init_db
        init_db()
    except Exception as e:
        errors.append(f"Database init failed: {e}")

    try:
        from core.pdf_parser import pdf_parser
        pdf_parser.load()
    except FileNotFoundError:
        errors.append(
            "PDF not found. Place SLATEFALL_DOSSIER.pdf in the data/ folder."
        )
        pdf_parser = None
    except Exception as e:
        errors.append(f"PDF loading failed: {e}")
        pdf_parser = None

    try:
        from core.session_manager import session_manager
    except Exception as e:
        errors.append(f"Session manager failed: {e}")
        session_manager = None

    try:
        from kb.queries import kb
    except Exception as e:
        errors.append(f"Knowledge base failed: {e}")
        kb = None

    return {
        "pdf_parser":     pdf_parser,
        "session_manager": session_manager,
        "kb":             kb,
        "errors":         errors,
    }


# Load system
system = load_system()


# ─── Sidebar Navigation ───────────────────────────────────────────

def render_sidebar():
    """Render the sidebar with navigation and system status."""
    with st.sidebar:
        # Logo / Title
        st.markdown("""
        <div style='text-align: center; padding: 20px 0;'>
            <h1 style='font-size: 28px; margin: 0;'>📖</h1>
            <h2 style='font-size: 18px; margin: 5px 0; color: #4f8ef7;'>
                SLATEFALL Prep
            </h2>
            <p style='font-size: 12px; color: #666; margin: 0;'>
                Adaptive Study System
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Navigation
        st.markdown("**Navigation**")

        pages = {
            "🏠 Home":            "home",
            "📚 Study Session":   "study",
            "📊 My Progress":     "progress",
            "🗂️ Knowledge Base":  "kb_view",
            "🧪 Run Scenarios":   "scenarios",
            "⚙️ Settings":        "settings",
        }

        for label, page_key in pages.items():
            is_active = st.session_state.page == page_key
            if st.button(
                label,
                use_container_width=True,
                type="primary" if is_active else "secondary",
                key=f"nav_{page_key}",
            ):
                st.session_state.page = page_key
                st.session_state.quiz_started = False
                st.session_state.session_submitted = False
                st.rerun()

        st.divider()

        # System Status
        st.markdown("**System Status**")

        if system["errors"]:
            for err in system["errors"]:
                st.error(f"❌ {err}", icon="🚨")
        else:
            st.success("✅ All systems ready", icon="✅")

        # Quick stats
        if system["kb"]:
            try:
                all_sessions = system["kb"].get_all_sessions()
                st.metric("Total Sessions", len(all_sessions))
            except Exception:
                pass

        if system["pdf_parser"]:
            sections = system["pdf_parser"].get_all_sections()
            st.metric("PDF Sections", len(sections))

        st.divider()
        st.markdown(
            "<p style='font-size: 11px; color: #555; text-align: center;'>"
            "Cloudly AI/ML Intern Assessment<br>"
            "Built with Streamlit + Groq</p>",
            unsafe_allow_html=True,
        )


# ─── Page: Home ──────────────────────────────────────────────────

def page_home():
    """Landing page with project overview."""

    # Hero section
    st.markdown("""
    <div style='text-align: center; padding: 40px 0 20px 0;'>
        <h1 style='font-size: 42px; font-weight: 800;'>
            📖 SLATEFALL Prep System
        </h1>
        <p style='font-size: 18px; color: #888; max-width: 600px; margin: 0 auto;'>
            An adaptive study assistant that learns what you don't know
            and focuses every session on improving your weak areas.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # How it works
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class='stat-card'>
            <h2>📄</h2>
            <h3>1. Select Sections</h3>
            <p style='color: #888;'>
                Choose which sections of the SLATEFALL dossier
                you want to study.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class='stat-card'>
            <h2>🤖</h2>
            <h3>2. AI Generates Questions</h3>
            <p style='color: #888;'>
                Groq AI creates MCQs from the content.
                On return visits, it focuses on your weak areas.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class='stat-card'>
            <h2>📈</h2>
            <h3>3. System Adapts</h3>
            <p style='color: #888;'>
                Your history is tracked. Each new session
                targets what you consistently get wrong.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Quick stats row
    if system["kb"] and system["pdf_parser"]:
        st.markdown("### 📊 Quick Overview")

        try:
            all_sessions = system["kb"].get_all_sessions()
            sections     = system["pdf_parser"].get_all_sections()
            adaptive_count = sum(1 for s in all_sessions if s.is_adaptive)
            avg_score = (
                sum(s.score for s in all_sessions) / len(all_sessions)
                if all_sessions else 0
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📚 Sessions Completed", len(all_sessions))
            c2.metric("🔄 Adaptive Sessions",   adaptive_count)
            c3.metric("📄 PDF Sections",         len(sections))
            c4.metric("🎯 Average Score",         f"{avg_score:.1%}")

        except Exception as e:
            st.info("Start your first session to see statistics here.")

    st.divider()

    # Quick start button
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        if st.button(
            "🚀 Start Studying Now",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.page = "study"
            st.rerun()

    # PDF sections preview
    if system["pdf_parser"]:
        with st.expander("📋 View Available PDF Sections"):
            sections = system["pdf_parser"].get_all_sections()
            for s in sections:
                col1, col2, col3 = st.columns([1, 5, 2])
                with col1:
                    st.markdown(f"**Section {s.section_id}**")
                with col2:
                    st.markdown(s.title)
                with col3:
                    st.markdown(
                        f"<span style='color: #888;'>p{s.start_page}–{s.end_page} "
                        f"| {s.word_count} words</span>",
                        unsafe_allow_html=True,
                    )


# ─── Page: Study Session ─────────────────────────────────────────

def page_study():
    """Main study session page."""

    st.markdown("## 📚 Study Session")

    # Check system ready
    if not system["pdf_parser"] or not system["session_manager"]:
        st.error("System not ready. Check sidebar for errors.")
        return

    # ── Session Setup (before quiz starts) ───────────────────────
    if not st.session_state.quiz_started:
        _render_session_setup()

    # ── Quiz Interface (after setup) ─────────────────────────────
    elif not st.session_state.session_submitted:
        if st.session_state.mode == "interactive":
            _render_interactive_quiz()
        else:
            _render_simulated_session()

    # ── Results (after submission) ────────────────────────────────
    else:
        _render_session_results()


def _render_session_setup():
    """Render the session setup form."""

    sections = system["pdf_parser"].get_all_sections()
    section_options = {
        f"Section {s.section_id}: {s.title[:45]}": s.section_id
        for s in sections
    }

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📋 Configure Your Session")

        # Section selection
        selected_labels = st.multiselect(
            "Select sections to study",
            options=list(section_options.keys()),
            default=list(section_options.keys())[:2],
            help="Choose one or more sections from the dossier",
        )
        selected_ids = [section_options[label] for label in selected_labels]

        # Show adaptive status
        if selected_ids and system["kb"]:
            has_history = system["kb"].has_prior_history(selected_ids)
            if has_history:
                weak = system["kb"].get_weak_topics(selected_ids)
                st.markdown(
                    f"<span class='adaptive-badge'>🔄 ADAPTIVE SESSION</span> "
                    f"Prior history found — {len(weak)} weak topic(s) will be targeted.",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<span class='cold-badge'>❄️ COLD START</span> "
                    "First time studying these sections.",
                    unsafe_allow_html=True,
                )

        # Mode selection
        st.markdown("### 🎮 Session Mode")
        mode = st.radio(
            "How would you like to answer?",
            options=["🤖 Simulate Answers", "✍️ Answer Yourself"],
            horizontal=True,
        )
        is_simulate = mode.startswith("🤖")

        # Number of questions
        n_questions = st.slider(
            "Questions per section",
            min_value=1,
            max_value=10,
            value=st.session_state.n_per_section,
            help="How many questions to generate per section",
        )

        # Simulation accuracy (only shown in simulate mode)
        sim_accuracy = 0.6
        if is_simulate:
            sim_accuracy = st.slider(
                "Simulated accuracy",
                min_value=0.1,
                max_value=1.0,
                value=st.session_state.simulation_accuracy,
                step=0.1,
                help="What % of simulated answers should be correct",
            )

    with col2:
        st.markdown("### 📌 Session Preview")

        if selected_ids:
            st.info(
                f"**Sections:** {selected_ids}\n\n"
                f"**Questions:** {n_questions} × {len(selected_ids)} = "
                f"{n_questions * len(selected_ids)} total\n\n"
                f"**Mode:** {'Simulated' if is_simulate else 'Interactive'}"
            )

            if is_simulate:
                st.markdown(
                    f"Expected correct: ~{int(sim_accuracy * n_questions * len(selected_ids))} "
                    f"/ {n_questions * len(selected_ids)}"
                )

            # Show weak topics if adaptive
            if system["kb"] and system["kb"].has_prior_history(selected_ids):
                weak = system["kb"].get_weak_topics(selected_ids)
                if weak:
                    st.markdown("**🎯 Weak areas to target:**")
                    for wt in weak[:5]:
                        st.markdown(
                            f"• {wt['topic']} "
                            f"<span style='color: #ff6b6b;'>({wt['wrong_count']}× wrong)</span>",
                            unsafe_allow_html=True,
                        )
        else:
            st.warning("Select at least one section to continue.")

    st.divider()

    # Start button
    can_start = len(selected_ids) > 0

    if st.button(
        "🚀 Start Session",
        disabled=not can_start,
        type="primary",
        use_container_width=True,
    ):
        st.session_state.selected_sections   = selected_ids
        st.session_state.n_per_section       = n_questions
        st.session_state.simulation_accuracy = sim_accuracy
        st.session_state.mode                = "simulate" if is_simulate else "interactive"
        st.session_state.quiz_started        = True
        st.session_state.current_questions   = []
        st.session_state.current_answers     = {}
        st.session_state.current_q_index     = 0
        st.rerun()


def _render_simulated_session():
    """Run a simulated session and show results immediately."""

    st.markdown("### 🤖 Running Simulated Session...")

    # Progress placeholder
    progress_bar  = st.progress(0)
    status_text   = st.empty()

    with st.spinner("Generating questions and simulating answers..."):
        try:
            status_text.markdown("🔍 Checking session history...")
            progress_bar.progress(20)
            time.sleep(0.3)

            status_text.markdown("📄 Loading PDF sections...")
            progress_bar.progress(40)
            time.sleep(0.3)

            status_text.markdown("🤖 Generating questions with AI...")
            progress_bar.progress(60)

            # Run the actual session
            result = system["session_manager"].run_session(
                section_ids         = st.session_state.selected_sections,
                n_per_section       = st.session_state.n_per_section,
                simulate_answers    = True,
                simulation_accuracy = st.session_state.simulation_accuracy,
                interactive         = False,
            )

            progress_bar.progress(80)
            status_text.markdown("💾 Saving to knowledge base...")
            time.sleep(0.3)

            progress_bar.progress(100)
            status_text.markdown("✅ Complete!")
            time.sleep(0.5)

            # Store result and go to results page
            st.session_state.session_result   = result
            st.session_state.session_submitted = True
            st.rerun()

        except Exception as e:
            st.error(f"Session failed: {e}")
            st.exception(e)
            if st.button("← Back to Setup"):
                st.session_state.quiz_started = False
                st.rerun()


def _render_interactive_quiz():
    """Render interactive quiz where user answers questions one by one."""

    # Generate questions if not yet done
    if not st.session_state.current_questions:
        with st.spinner("🤖 Generating questions..."):
            try:
                from core.adaptive_engine import adaptive_engine
                questions, metadata = adaptive_engine.prepare_session(
                    section_ids   = st.session_state.selected_sections,
                    n_per_section = st.session_state.n_per_section,
                )
                st.session_state.current_questions = questions
                st.session_state._session_metadata = metadata
            except Exception as e:
                st.error(f"Failed to generate questions: {e}")
                if st.button("← Back"):
                    st.session_state.quiz_started = False
                    st.rerun()
                return

    questions = st.session_state.current_questions
    total     = len(questions)

    if total == 0:
        st.error("No questions were generated. Check your PDF and API key.")
        if st.button("← Back"):
            st.session_state.quiz_started = False
            st.rerun()
        return

    # Progress header
    answered = len(st.session_state.current_answers)
    progress = answered / total if total > 0 else 0

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.progress(progress, text=f"Progress: {answered}/{total} questions answered")
    with col2:
        st.metric("Answered", f"{answered}/{total}")
    with col3:
        correct_so_far = sum(
            1 for q, ans in st.session_state.current_answers.items()
            if ans == questions[q].correct_answer
        )
        st.metric("Correct so far", correct_so_far)

    st.divider()

    # Show all questions
    for i, question in enumerate(questions):
        q_answered = i in st.session_state.current_answers
        user_ans   = st.session_state.current_answers.get(i)

        with st.container():
            # Question header
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(
                    f"**Q{i+1}.** {question.question_text}",
                )
            with col2:
                st.markdown(
                    f"<span style='color: #888; font-size: 12px;'>"
                    f"Section {question.section_id} — {question.topic}"
                    f"</span>",
                    unsafe_allow_html=True,
                )

            # Answer choices
            if not q_answered:
                # Show as radio buttons
                choice = st.radio(
                    f"Select answer for Q{i+1}:",
                    options=["A", "B", "C", "D"],
                    format_func=lambda x: f"{x})  {question.choices[x]}",
                    key=f"q_{i}",
                    label_visibility="collapsed",
                )

                if st.button(f"Submit Answer", key=f"submit_{i}"):
                    st.session_state.current_answers[i] = choice
                    st.rerun()

            else:
                # Show result
                is_correct = user_ans == question.correct_answer

                for letter, text in question.choices.items():
                    if letter == question.correct_answer:
                        st.markdown(
                            f"<div class='correct-answer'>"
                            f"✅ <strong>{letter})</strong> {text}"
                            f"{'  ← Your Answer' if user_ans == letter else '  ← Correct Answer'}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    elif letter == user_ans and not is_correct:
                        st.markdown(
                            f"<div class='wrong-answer'>"
                            f"❌ <strong>{letter})</strong> {text}  ← Your Answer"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;{letter})  {text}")

                if not is_correct:
                    st.info(f"💡 **Explanation:** {question.explanation}")

            st.divider()

    # Submit all button (only when all answered)
    all_answered = len(st.session_state.current_answers) == total

    if all_answered:
        st.success(f"✅ All {total} questions answered!")

        if st.button("📊 View Final Results & Save Session", type="primary", use_container_width=True):
            _save_interactive_session(questions)

    else:
        remaining = total - len(st.session_state.current_answers)
        st.warning(f"⚠️ Please answer all questions. {remaining} remaining.")


def _save_interactive_session(questions):
    """Save interactive session results to KB."""
    with st.spinner("Saving results..."):
        try:
            from kb.queries import kb
            metadata = getattr(st.session_state, "_session_metadata", {})

            questions_with_results = []
            for i, q in enumerate(questions):
                user_answer = st.session_state.current_answers.get(i)
                is_correct  = user_answer == q.correct_answer

                q_dict = q.to_dict()
                q_dict.update({
                    "user_answer":     user_answer,
                    "is_correct":      is_correct,
                    "question_number": i + 1,
                })
                questions_with_results.append(q_dict)

            is_adaptive      = metadata.get("is_adaptive", False)
            weak_topics_used = metadata.get("weak_topics_used", [])

            saved = kb.save_session(
                section_ids           = st.session_state.selected_sections,
                questions_and_results = questions_with_results,
                is_adaptive           = is_adaptive,
                weak_topics_used      = [wt["topic"] for wt in weak_topics_used],
            )

            total   = len(questions_with_results)
            correct = sum(1 for q in questions_with_results if q["is_correct"])
            score   = correct / total if total > 0 else 0.0

            from core.session_manager import SessionResult
            result = SessionResult(
                session_id       = saved.id,
                section_ids      = st.session_state.selected_sections,
                questions        = questions_with_results,
                score            = score,
                correct_count    = correct,
                total_count      = total,
                is_adaptive      = is_adaptive,
                weak_topics_used = weak_topics_used,
            )

            st.session_state.session_result    = result
            st.session_state.session_submitted = True
            st.rerun()

        except Exception as e:
            st.error(f"Failed to save session: {e}")


def _render_session_results():
    """Show final session results."""
    result = st.session_state.session_result

    if not result:
        st.error("No results found.")
        return

    # ── Score Hero ────────────────────────────────────────────────
    score_pct = result.score * 100
    if score_pct >= 80:
        score_color = "#00c864"
        score_emoji = "🏆"
        score_msg   = "Excellent work!"
    elif score_pct >= 60:
        score_color = "#ffd700"
        score_emoji = "👍"
        score_msg   = "Good progress!"
    else:
        score_color = "#ff6b6b"
        score_emoji = "💪"
        score_msg   = "Keep practicing!"

    st.markdown(f"""
    <div style='text-align: center; padding: 30px;'>
        <div style='font-size: 64px;'>{score_emoji}</div>
        <div style='font-size: 72px; font-weight: 800; color: {score_color};'>
            {score_pct:.0f}%
        </div>
        <div style='font-size: 24px; color: #888;'>
            {result.correct_count} / {result.total_count} correct
        </div>
        <div style='font-size: 18px; color: {score_color}; margin-top: 10px;'>
            {score_msg}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Session Info ──────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Session ID",   result.session_id)
    col2.metric("Sections",     str(result.section_ids))
    col3.metric("Total Questions", result.total_count)
    col4.metric(
        "Session Type",
        "🔄 Adaptive" if result.is_adaptive else "❄️ Cold Start",
    )

    # Adaptive info
    if result.is_adaptive and result.weak_topics_used:
        st.markdown("### 🎯 Weak Topics That Were Targeted")
        for wt in result.weak_topics_used:
            if isinstance(wt, dict):
                topic = wt.get("topic", str(wt))
                count = wt.get("wrong_count", "?")
            else:
                topic = str(wt)
                count = "?"
            st.markdown(
                f"• **{topic}** — answered wrong {count}× in previous sessions"
            )

    st.divider()

    # ── Question Review ───────────────────────────────────────────
    st.markdown("### 📋 Question Review")

    # Filter buttons
    filter_mode = st.radio(
        "Show:",
        ["All Questions", "Wrong Answers Only", "Correct Answers Only"],
        horizontal=True,
    )

    for i, q_data in enumerate(result.questions):
        is_correct  = q_data.get("is_correct", False)
        user_answer = q_data.get("user_answer", "N/A")

        # Apply filter
        if filter_mode == "Wrong Answers Only" and is_correct:
            continue
        if filter_mode == "Correct Answers Only" and not is_correct:
            continue

        with st.expander(
            f"{'✅' if is_correct else '❌'} Q{i+1}: "
            f"{q_data['question_text'][:80]}..."
        ):
            st.markdown(f"**Topic:** {q_data.get('topic', 'General')}")
            st.markdown(f"**Section:** {q_data.get('section_id', '?')}")
            st.divider()

            choices = q_data.get("choices", {})
            correct = q_data.get("correct_answer", "")

            for letter, text in choices.items():
                if letter == correct:
                    st.markdown(
                        f"<div class='correct-answer'>"
                        f"✅ <strong>{letter})</strong> {text}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                elif letter == user_answer and not is_correct:
                    st.markdown(
                        f"<div class='wrong-answer'>"
                        f"❌ <strong>{letter})</strong> {text}  ← You answered"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{letter})  {text}")

            if not is_correct:
                st.info(f"💡 **Explanation:** {q_data.get('explanation', '')}")

    st.divider()

    # ── Action Buttons ────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Study Same Sections Again", use_container_width=True):
            st.session_state.session_submitted = False
            st.session_state.quiz_started      = False
            st.session_state.current_questions = []
            st.session_state.current_answers   = {}
            st.rerun()

    with col2:
        if st.button("📚 New Session (Different Sections)", use_container_width=True):
            st.session_state.session_submitted = False
            st.session_state.quiz_started      = False
            st.session_state.current_questions = []
            st.session_state.current_answers   = {}
            st.session_state.selected_sections = []
            st.rerun()

    with col3:
        if st.button("📊 View My Progress", use_container_width=True, type="primary"):
            st.session_state.page = "progress"
            st.rerun()


# ─── Page: Progress ───────────────────────────────────────────────

def page_progress():
    """Show user's learning progress and history."""

    st.markdown("## 📊 My Progress")

    if not system["kb"]:
        st.error("Knowledge base not available.")
        return

    try:
        all_sessions = system["kb"].get_all_sessions()
    except Exception as e:
        st.error(f"Could not load sessions: {e}")
        return

    if not all_sessions:
        st.info(
            "No sessions yet! "
            "Go to Study Session to start your first prep session."
        )
        if st.button("🚀 Start First Session", type="primary"):
            st.session_state.page = "study"
            st.rerun()
        return

    # ── Overview Metrics ──────────────────────────────────────────
    total_sessions  = len(all_sessions)
    adaptive_count  = sum(1 for s in all_sessions if s.is_adaptive)
    avg_score       = sum(s.score for s in all_sessions) / total_sessions
    best_score      = max(s.score for s in all_sessions)
    total_questions = sum(s.total_questions for s in all_sessions)
    total_correct   = sum(s.correct_count for s in all_sessions)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Sessions",    total_sessions)
    col2.metric("Adaptive Sessions", adaptive_count)
    col3.metric("Average Score",     f"{avg_score:.1%}")
    col4.metric("Best Score",        f"{best_score:.1%}")
    col5.metric("Questions Answered", total_questions)

    st.divider()

    # ── Score Over Time Chart ─────────────────────────────────────
    st.markdown("### 📈 Score History")

    try:
        import pandas as pd

        session_data = []
        for s in all_sessions:
            session_data.append({
                "Session":    s.id,
                "Score":      round(s.score * 100, 1),
                "Sections":   s.section_ids,
                "Adaptive":   "Adaptive" if s.is_adaptive else "Cold Start",
                "Date":       s.created_at,
                "Correct":    s.correct_count,
                "Total":      s.total_questions,
            })

        df = pd.DataFrame(session_data)

        # Score line chart
        st.line_chart(
            df.set_index("Session")["Score"],
            color="#4f8ef7",
        )

        # Sessions table
        st.markdown("### 📋 All Sessions")
        st.dataframe(
            df[["Session", "Score", "Sections", "Adaptive", "Correct", "Total", "Date"]],
            use_container_width=True,
            hide_index=True,
        )

    except ImportError:
        # Fallback without pandas
        for s in reversed(all_sessions):
            score_color = (
                "green" if s.score >= 0.7
                else "orange" if s.score >= 0.5
                else "red"
            )
            tag = "🔄 ADAPTIVE" if s.is_adaptive else "❄️ COLD START"
            st.markdown(
                f"**Session {s.id}** | {tag} | "
                f"Sections: {s.section_ids} | "
                f"Score: :{score_color}[{s.score:.1%}] | "
                f"{s.correct_count}/{s.total_questions} correct"
            )

    st.divider()

    # ── Weak Topics Analysis ──────────────────────────────────────
    st.markdown("### 🎯 Your Weak Areas")
    st.markdown(
        "Topics you consistently get wrong — "
        "your next adaptive session will focus here."
    )

    # Get weak topics across ALL sections
    all_section_ids = list(range(1, 11))
    try:
        weak_topics = system["kb"].get_weak_topics(all_section_ids, min_wrong_count=1)
    except Exception:
        weak_topics = []

    if weak_topics:
        # Show as progress bars (inverted — more wrong = longer bar)
        max_wrong = max(wt["wrong_count"] for wt in weak_topics)

        for wt in weak_topics[:10]:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                progress = wt["wrong_count"] / max_wrong
                st.markdown(f"**{wt['topic']}**")
                st.progress(progress)
            with col2:
                st.metric("Times Wrong", wt["wrong_count"])
            with col3:
                st.metric("Section", wt.get("section_id", "?"))
    else:
        st.success("🎉 No consistent weak areas identified yet. Keep studying!")

    st.divider()

    # ── Section Performance ───────────────────────────────────────
    st.markdown("### 📄 Performance by Section")

    section_stats: dict = {}

    for session in all_sessions:
        for section_id_str in session.section_ids.split(","):
            try:
                sid = int(section_id_str.strip())
                if sid not in section_stats:
                    section_stats[sid] = {"scores": [], "sessions": 0}
                section_stats[sid]["scores"].append(session.score)
                section_stats[sid]["sessions"] += 1
            except ValueError:
                continue

    if section_stats:
        cols = st.columns(min(5, len(section_stats)))
        for i, (sid, stats) in enumerate(sorted(section_stats.items())):
            avg = sum(stats["scores"]) / len(stats["scores"])
            col = cols[i % len(cols)]
            col.metric(
                f"Section {sid}",
                f"{avg:.0%}",
                f"{stats['sessions']} session(s)",
            )


# ─── Page: Knowledge Base Viewer ─────────────────────────────────

def page_kb_view():
    """View the Knowledge Base snapshots."""

    st.markdown("## 🗂️ Knowledge Base")
    st.markdown(
        "Inspect what the system has stored. "
        "This is the same data that drives adaptive question generation."
    )

    if not system["kb"]:
        st.error("Knowledge base not available.")
        return

    # ── Controls ──────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])

    with col1:
        top_n = st.slider("Number of recent sessions to show", 1, 20, 5)

    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    # ── Snapshot ──────────────────────────────────────────────────
    try:
        snapshot = system["kb"].get_kb_snapshot(top_n=top_n)
    except Exception as e:
        st.error(f"Could not load snapshot: {e}")
        return

    if not snapshot:
        st.info("No sessions in the knowledge base yet.")
        return

    for session_data in snapshot:
        adaptive = session_data.get("is_adaptive", False)
        badge_html = (
            "<span class='adaptive-badge'>🔄 ADAPTIVE</span>"
            if adaptive
            else "<span class='cold-badge'>❄️ COLD START</span>"
        )

        with st.expander(
            f"Session {session_data['id']} | "
            f"Sections: {session_data['section_ids']} | "
            f"Score: {session_data['percentage']} | "
            f"{'ADAPTIVE' if adaptive else 'COLD START'}",
            expanded=(session_data == snapshot[0]),  # First one expanded
        ):
            # Session header
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown(f"**Date:** {session_data.get('created_at', 'N/A')}")
                st.markdown(f"**Sections studied:** {session_data['section_ids']}")

                weak_topics = session_data.get("weak_topics_used", [])
                if weak_topics:
                    st.markdown(f"**Weak topics targeted:** {', '.join(str(w) for w in weak_topics)}")

            with col2:
                score = session_data.get("score", 0)
                st.metric(
                    "Score",
                    session_data.get("percentage", "N/A"),
                    f"{session_data.get('correct_count', 0)}/{session_data.get('total_questions', 0)}",
                )

            # Questions breakdown
            questions = session_data.get("questions", [])
            if questions:
                st.markdown(f"**Questions ({len(questions)} total):**")

                correct_q   = [q for q in questions if q.get("is_correct")]
                incorrect_q = [q for q in questions if not q.get("is_correct")]

                tab1, tab2 = st.tabs([
                    f"❌ Wrong ({len(incorrect_q)})",
                    f"✅ Correct ({len(correct_q)})",
                ])

                with tab1:
                    for q in incorrect_q:
                        st.markdown(
                            f"**Topic:** {q.get('topic', 'General')} "
                            f"| Section {q.get('section_id', '?')}\n\n"
                            f"*{q.get('question_text', '')}*\n\n"
                            f"You answered: **{q.get('user_answer', '?')}** | "
                            f"Correct: **{q.get('correct_answer', '?')}**"
                        )
                        st.divider()

                with tab2:
                    for q in correct_q:
                        st.markdown(
                            f"**Topic:** {q.get('topic', 'General')} "
                            f"| Section {q.get('section_id', '?')}\n\n"
                            f"*{q.get('question_text', '')}*"
                        )
                        st.divider()

    st.divider()

    # ── Export Raw JSON ───────────────────────────────────────────
    st.markdown("### 💾 Export Raw KB Snapshot")

    try:
        snapshot_json = json.dumps(snapshot, indent=2, default=str)
        st.download_button(
            label     = "⬇️ Download KB Snapshot (JSON)",
            data      = snapshot_json,
            file_name = "kb_snapshot.json",
            mime      = "application/json",
        )
    except Exception as e:
        st.error(f"Export failed: {e}")


# ─── Page: Run Scenarios ──────────────────────────────────────────

def page_scenarios():
    """Run the evaluation scenarios directly from the UI."""

    st.markdown("## 🧪 Run Evaluation Scenarios")
    st.markdown(
        "Run the official assessment scenarios and generate "
        "the required output files."
    )

    if not system["session_manager"]:
        st.error("System not ready.")
        return

    # ── Scenario A ────────────────────────────────────────────────
    st.markdown("### Scenario A — Cold Start")
    st.markdown("Run a single cold-start session over any two sections.")

    with st.form("scenario_a_form"):
        col1, col2 = st.columns(2)

        with col1:
            sections = system["pdf_parser"].get_all_sections() if system["pdf_parser"] else []
            options  = {f"Section {s.section_id}: {s.title[:40]}": s.section_id for s in sections}

            a_sections = st.multiselect(
                "Sections",
                options=list(options.keys()),
                default=list(options.keys())[:2] if len(options) >= 2 else list(options.keys()),
                key="scenario_a_sections",
            )
            a_section_ids = [options[l] for l in a_sections]

        with col2:
            a_n = st.number_input("Questions per section", 1, 10, 5, key="a_n")

        submitted_a = st.form_submit_button("▶️ Run Scenario A", type="primary")

    if submitted_a and a_section_ids:
        with st.spinner("Running Scenario A..."):
            try:
                from utils.exporter import export_iteration_outputs
                result = system["session_manager"].run_session(
                    section_ids         = a_section_ids,
                    n_per_section       = a_n,
                    simulate_answers    = True,
                    simulation_accuracy = 0.6,
                    interactive         = False,
                )
                paths = export_iteration_outputs(1, "scenario_a", result)

                st.success(
                    f"✅ Scenario A complete! "
                    f"Score: {result.score:.1%} ({result.correct_count}/{result.total_count})"
                )

                col1, col2 = st.columns(2)
                with col1:
                    q_json = json.dumps(result.to_dict(), indent=2, default=str)
                    st.download_button(
                        "⬇️ questions_iter1.json",
                        q_json,
                        "questions_iter1.json",
                        "application/json",
                    )
                with col2:
                    from kb.queries import kb
                    snap  = kb.get_kb_snapshot(5)
                    s_json = json.dumps(snap, indent=2, default=str)
                    st.download_button(
                        "⬇️ kb_snapshot_iter1.json",
                        s_json,
                        "kb_snapshot_iter1.json",
                        "application/json",
                    )
            except Exception as e:
                st.error(f"Scenario A failed: {e}")
                st.exception(e)

    st.divider()

    # ── Scenario B ────────────────────────────────────────────────
    st.markdown("### Scenario B — Three Adaptive Iterations")
    st.markdown("""
    | Iteration | Sections | Expected |
    |-----------|----------|----------|
    | Iter 1    | 5, 8     | Cold Start |
    | Iter 2    | 6, 8, 9  | Adaptive (uses Iter 1 history) |
    | Iter 3    | 8        | Adaptive (uses Iter 1+2 history) |
    """)

    with st.form("scenario_b_form"):
        col1, col2 = st.columns(2)
        with col1:
            b_n = st.number_input("Questions per section", 1, 10, 5, key="b_n")
        with col2:
            b_acc = st.slider(
                "Simulated accuracy",
                0.1, 1.0, 0.6, 0.1,
                key="b_acc",
            )
        submitted_b = st.form_submit_button("▶️ Run Scenario B (All 3 Iterations)", type="primary")

    if submitted_b:
        from utils.exporter import export_iteration_outputs

        iterations = [(1, [5, 8]), (2, [6, 8, 9]), (3, [8])]
        all_results = []

        progress_bar = st.progress(0)
        status       = st.empty()

        for i, (iteration, section_ids) in enumerate(iterations):
            status.markdown(
                f"⏳ Running Iteration {iteration} "
                f"(Sections {section_ids})..."
            )
            progress_bar.progress((i) / 3)

            try:
                result = system["session_manager"].run_session(
                    section_ids         = section_ids,
                    n_per_section       = b_n,
                    simulate_answers    = True,
                    simulation_accuracy = b_acc,
                    interactive         = False,
                )
                paths = export_iteration_outputs(iteration, "scenario_b", result)
                all_results.append((iteration, result, paths))

            except Exception as e:
                st.error(f"Iteration {iteration} failed: {e}")
                break

        progress_bar.progress(1.0)
        status.markdown("✅ All iterations complete!")

        # Show results for each iteration
        for iteration, result, paths in all_results:
            adaptive_label = "🔄 ADAPTIVE" if result.is_adaptive else "❄️ COLD START"
            score_color    = "green" if result.score >= 0.7 else "orange"

            st.markdown(f"""
            **Iteration {iteration}** — {adaptive_label}
            | Score: {result.score:.1%}
            ({result.correct_count}/{result.total_count})
            """)

            if result.is_adaptive and result.weak_topics_used:
                for wt in result.weak_topics_used[:3]:
                    if isinstance(wt, dict):
                        st.markdown(
                            f"&nbsp;&nbsp;&nbsp;→ Targeted: *{wt.get('topic', wt)}* "
                            f"(wrong {wt.get('wrong_count', '?')}×)"
                        )

            col1, col2 = st.columns(2)
            with col1:
                q_json = json.dumps(result.to_dict(), indent=2, default=str)
                st.download_button(
                    f"⬇️ questions_iter{iteration}.json",
                    q_json,
                    f"questions_iter{iteration}.json",
                    "application/json",
                    key=f"dl_q_{iteration}",
                )
            with col2:
                from kb.queries import kb
                snap   = kb.get_kb_snapshot(5)
                s_json = json.dumps(snap, indent=2, default=str)
                st.download_button(
                    f"⬇️ kb_snapshot_iter{iteration}.json",
                    s_json,
                    f"kb_snapshot_iter{iteration}.json",
                    "application/json",
                    key=f"dl_s_{iteration}",
                )

        if all_results:
            st.balloons()
            st.success("🎉 Scenario B complete! Download the files above.")


# ─── Page: Settings ───────────────────────────────────────────────

def page_settings():
    """Settings and system info page."""

    st.markdown("## ⚙️ Settings & System Info")

    # ── Configuration ─────────────────────────────────────────────
    st.markdown("### 🔧 Current Configuration")

    try:
        import config

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**LLM Settings**")
            st.code(f"""
Provider : {config.LLM_PROVIDER}
Model    : {config.GROQ_MODEL if config.LLM_PROVIDER == 'groq' else config.GEMINI_MODEL}
API Key  : {'✅ Set' if config.GROQ_API_KEY or config.GEMINI_API_KEY else '❌ Not Set'}
            """)

        with col2:
            st.markdown("**App Settings**")
            st.code(f"""
Questions/Section : {config.QUESTIONS_PER_SECTION}
PDF Path          : {config.PDF_PATH}
DB Path           : {config.DB_PATH}
API Port          : {config.API_PORT}
            """)

    except Exception as e:
        st.error(f"Could not load config: {e}")

    st.divider()

    # ── Database Management ───────────────────────────────────────
    st.markdown("### 🗄️ Database Management")

    col1, col2 = st.columns(2)

    with col1:
        if system["kb"]:
            try:
                all_sessions = system["kb"].get_all_sessions()
                st.metric("Total sessions in DB", len(all_sessions))

                if all_sessions:
                    total_q = sum(s.total_questions for s in all_sessions)
                    st.metric("Total questions recorded", total_q)
            except Exception:
                pass

    with col2:
        st.markdown("**Reset Database**")
        st.warning("⚠️ This will delete ALL session history!")

        confirm = st.checkbox("I understand this cannot be undone")
        if st.button("🗑️ Reset Database", disabled=not confirm):
            try:
                import config as cfg
                db_path = cfg.DB_PATH
                if db_path.exists():
                    db_path.unlink()

                from kb.database import init_db
                import kb.database as db_module
                db_module._engine         = None
                db_module._SessionFactory = None
                init_db()

                st.success("✅ Database reset. Reload the page.")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Reset failed: {e}")

    st.divider()

    # ── System Status ─────────────────────────────────────────────
    st.markdown("### 🔍 System Status")

    checks = {
        "PDF Parser loaded": system["pdf_parser"] is not None,
        "Session Manager ready": system["session_manager"] is not None,
        "Knowledge Base connected": system["kb"] is not None,
        "No startup errors": len(system["errors"]) == 0,
    }

    for check, passed in checks.items():
        if passed:
            st.success(f"✅ {check}")
        else:
            st.error(f"❌ {check}")

    if system["pdf_parser"]:
        sections = system["pdf_parser"].get_all_sections()
        st.info(f"📄 PDF: {len(sections)} sections detected")

    st.divider()

    # ── About ─────────────────────────────────────────────────────
    st.markdown("### ℹ️ About This Project")
    st.markdown("""
    **Adaptive Document Preparation System**

    Built for the Cloudly AI/ML Intern Assessment.

    **Stack:**
    - 🐍 Python 3.11
    - 🚀 Streamlit (UI)
    - ⚡ FastAPI (REST API)
    - 🤖 Groq + Llama 3 8B (LLM)
    - 📄 PyMuPDF (PDF parsing)
    - 🗄️ SQLite + SQLAlchemy (Knowledge Base)
    - 🖥️ Click + Rich (CLI)

    **Key Design Decisions:**
    - Adaptation happens at prompt level, not post-generation filtering
    - SQLite chosen over PostgreSQL (zero setup, sufficient for local use)
    - Groq chosen over Ollama (fast, free, no local GPU needed)
    - Two prompt templates: cold-start and adaptive
    """)


# ─── Main App Router ─────────────────────────────────────────────

def main():
    """Main app entry point — renders sidebar + current page."""
    render_sidebar()

    # Show any startup errors prominently
    if system["errors"]:
        st.error("⚠️ System has errors — some features may not work.")
        for err in system["errors"]:
            st.warning(err)
        st.divider()

    # Route to the correct page
    page = st.session_state.page

    if page == "home":
        page_home()
    elif page == "study":
        page_study()
    elif page == "progress":
        page_progress()
    elif page == "kb_view":
        page_kb_view()
    elif page == "scenarios":
        page_scenarios()
    elif page == "settings":
        page_settings()
    else:
        page_home()


if __name__ == "__main__":
    main()