import os
import streamlit as st
from dotenv import load_dotenv

from core.parser import parse_transcript, parse_interview_guide
from core.analysis import answer_question_for_expert, synthesize_across_experts, answer_freeform

load_dotenv(override=True)

st.set_page_config(
    page_title="Expert Call Analyzer",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data_")
DEFAULT_GUIDE = os.path.join(DATA_DIR, "Interview_Guide.txt")
DEFAULT_TRANSCRIPTS = [
    os.path.join(DATA_DIR, "Transcript_1_France.txt"),
    os.path.join(DATA_DIR, "Transcript_2_Germany.txt"),
    os.path.join(DATA_DIR, "Transcript_3_UK.txt"),
]

API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Style
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

:root {
    --ink: #14181f;
    --ink-soft: #4c5566;
    --line: #e4e7ee;
    --surface: #ffffff;
    --surface-tint: #f7f8fb;
    --accent: #1e4d8c;
    --accent-soft: #eaf0fa;
    --good: #1a7f5a;
    --good-soft: #e7f6ef;
    --warn: #a15c00;
    --warn-soft: #fdf2e0;
}

.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }
#MainMenu, footer, header { visibility: hidden; }

/* Masthead */
.masthead { border-bottom: 1px solid var(--line); padding-bottom: 1.4rem; margin-bottom: 1.6rem; }
.masthead-eyebrow {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--accent); margin-bottom: 0.35rem;
}
.masthead h1 {
    font-family: 'Source Serif 4', serif; font-weight: 600; font-size: 2.15rem;
    color: var(--accent); margin: 0 0 0.3rem 0; letter-spacing: -0.01em;
}

.masthead p { color: var(--ink-soft); font-size: 0.98rem; margin: 0; }

/* Guardrail strip */
.guardrail {
    display: flex; align-items: center; gap: 0.6rem;
    background: var(--surface-tint); border: 1px solid var(--line); border-radius: 10px;
    padding: 0.65rem 1rem; font-size: 0.85rem; color: var(--ink-soft); margin-bottom: 1.6rem;
}
.guardrail b { color: var(--ink); }

/* Expert roster */
.roster { display: flex; gap: 0.75rem; margin-bottom: 1.8rem; flex-wrap: wrap; }
.roster-card {
    flex: 1; min-width: 220px; background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; padding: 0.9rem 1.1rem;
}
.roster-card .name { font-weight: 700; font-size: 0.95rem; color: var(--ink); }
.roster-card .meta { font-size: 0.8rem; color: var(--ink-soft); margin-top: 0.15rem; }
.roster-card .count {
    display: inline-block; margin-top: 0.5rem; font-size: 0.72rem; font-weight: 600;
    color: var(--accent); background: var(--accent-soft); padding: 0.15rem 0.55rem; border-radius: 20px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] {
    height: 2.6rem; font-weight: 600; font-size: 0.92rem; color: var(--ink-soft);
    background: transparent; border-radius: 8px 8px 0 0; padding: 0 1rem;
}
.stTabs [aria-selected="true"] { color: var(--accent) !important; background: var(--accent-soft); }

/* Answer card */
.answer-card {
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    padding: 1.1rem 1.2rem; height: 100%;
}
.answer-card h4 {
    font-size: 0.9rem; font-weight: 700; color: var(--ink); margin: 0 0 0.1rem 0;
}
.answer-card .market { font-size: 0.76rem; color: var(--ink-soft); margin-bottom: 0.7rem; }
.answer-card .body-text { font-size: 0.9rem; color: var(--ink); line-height: 1.5; margin-bottom: 0.7rem; }

.evidence-item {
    display: flex; gap: 0.5rem; align-items: flex-start; font-size: 0.82rem;
    padding: 0.45rem 0.6rem; border-radius: 8px; margin-bottom: 0.4rem; line-height: 1.4;
}
.evidence-item.verified { background: var(--good-soft); color: #0d4029; }
.evidence-item.unverified { background: var(--warn-soft); color: #5c3800; }
.evidence-ts { font-weight: 700; white-space: nowrap; opacity: 0.75; }

.not-addressed {
    font-size: 0.85rem; color: var(--ink-soft); font-style: italic;
    background: var(--surface-tint); padding: 0.6rem 0.8rem; border-radius: 8px;
}

/* Theme / disagreement cards */
.theme-card, .diff-card {
    border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.15rem; margin-bottom: 0.75rem;
    background: var(--surface);
}
.theme-card { border-left: 3px solid var(--good); }
.diff-card { border-left: 3px solid var(--warn); }
.theme-card h5, .diff-card h5 { margin: 0 0 0.3rem 0; font-size: 0.95rem; color: var(--ink); }
.theme-card p, .diff-card p { margin: 0 0 0.5rem 0; font-size: 0.88rem; color: var(--ink-soft); }
.support-chip {
    display: inline-block; font-size: 0.74rem; font-weight: 600; color: var(--accent);
    background: var(--accent-soft); padding: 0.15rem 0.55rem; border-radius: 20px; margin: 0.15rem 0.3rem 0 0;
}
.position-row { font-size: 0.85rem; color: var(--ink); margin: 0.25rem 0; padding-left: 0.2rem; }
.position-row b { color: var(--accent); }

/* Section labels */
.section-label {
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--ink-soft); margin: 1.3rem 0 0.6rem 0;
}

.stButton>button {
    border-radius: 8px; font-weight: 600; font-size: 0.88rem; border: 1px solid var(--line);
}
.stButton>button[kind="primary"] { background: var(--accent); border-color: var(--accent); }

div[data-testid="stTextInput"] input { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# Session state
if "transcripts" not in st.session_state:
    st.session_state.transcripts = None
if "questions" not in st.session_state:
    st.session_state.questions = None
if "per_question" not in st.session_state:
    st.session_state.per_question = {}   
if "synthesis" not in st.session_state:
    st.session_state.synthesis = {}      


def load_default_data():
    with open(DEFAULT_GUIDE, encoding="utf-8") as f:
        st.session_state.questions = parse_interview_guide(f.read())
    transcripts = []
    for path in DEFAULT_TRANSCRIPTS:
        with open(path, encoding="utf-8") as f:
            transcripts.append(parse_transcript(f.read()))
    st.session_state.transcripts = transcripts


if st.session_state.transcripts is None:
    load_default_data()

transcripts = st.session_state.transcripts
questions = st.session_state.questions

# Masthead
st.markdown("""
<div class="masthead">
    <div class="masthead-eyebrow">Hasamex &middot; AI Engineer Case Study</div>
    <h1>Expert Call Analyzer</h1>
</div>
""", unsafe_allow_html=True)

if not API_KEY:
    st.error(
        "**GEMINI_API_KEY** is not set. Add it to a `.env` file in the project root "
        "(see `.env.example`) and restart the app.",
        icon="🔑",
    )

roster_html = '<div class="roster">'
for t in transcripts:
    roster_html += f"""
    <div class="roster-card">
        <div class="name">{t['name']}</div>
        <div class="meta">{t.get('role','')} &middot; {t.get('market','')}</div>
        <span class="count">{len(t['segments'])} segments</span>
    </div>"""
roster_html += "</div>"
st.markdown(roster_html, unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["Per-Question Answers", "Cross-Expert Themes", "Ask Across Transcripts"])

# Tab 1: Per-question answers
with tab1:
    question = st.selectbox("Interview guide question", questions, key="q1")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        run_one = st.button("Analyze this question", type="primary", use_container_width=True)
    with col_b:
        run_all = st.button("Analyze all questions", use_container_width=True)

    def run_question(q):
        results = {}
        for t in transcripts:
            with st.spinner(f"Analyzing {t['name']}..."):
                results[t["name"]] = answer_question_for_expert(q, t, api_key=API_KEY)
        st.session_state.per_question[q] = results

    if run_one:
        try:
            run_question(question)
        except Exception as e:
            st.error(str(e))

    if run_all:
        for q in questions:
            try:
                run_question(q)
            except Exception as e:
                st.error(f"Question '{q}': {e}")
                break
        st.success("Done analyzing all questions.")

    results = st.session_state.per_question.get(question)
    if results:
        st.markdown('<div class="section-label">Per-expert answers</div>', unsafe_allow_html=True)
        cols = st.columns(len(transcripts))
        for col, t in zip(cols, transcripts):
            res = results.get(t["name"])
            with col:
                card = f'<div class="answer-card"><h4>{t["name"]}</h4>' \
                       f'<div class="market">{t.get("market","")}</div>'
                if not res:
                    card += '<div class="not-addressed">Not yet analyzed.</div></div>'
                    st.markdown(card, unsafe_allow_html=True)
                    continue
                if res.get("not_addressed"):
                    card += '<div class="not-addressed">Not addressed in this transcript.</div></div>'
                    st.markdown(card, unsafe_allow_html=True)
                    continue
                card += f'<div class="body-text">{res.get("answer", "")}</div>'
                for ev in res.get("evidence", []):
                    cls = "verified" if ev.get("verified") else "unverified"
                    icon = "✓" if ev.get("verified") else "⚠"
                    card += (
                        f'<div class="evidence-item {cls}">'
                        f'<span class="evidence-ts">{icon} {ev["timestamp"]}</span>'
                        f'<span>&ldquo;{ev["quote"]}&rdquo;</span></div>'
                    )
                card += "</div>"
                st.markdown(card, unsafe_allow_html=True)
    

# Tab 2: Cross-expert synthesis
with tab2:
    question2 = st.selectbox("Interview guide question", questions, key="q2")

    prereq = st.session_state.per_question.get(question2)
    if not prereq:
        st.info("Analyze this question in **Per-Question Answers** first, so the synthesis "
                "has grounded per-expert answers to compare.")
    else:
        if st.button("Find themes & disagreements", type="primary"):
            with st.spinner("Comparing experts..."):
                try:
                    st.session_state.synthesis[question2] = synthesize_across_experts(
                        question2, prereq, api_key=API_KEY
                    )
                except Exception as e:
                    st.error(str(e))

        synth = st.session_state.synthesis.get(question2)
        if synth:
            st.markdown('<div class="section-label">Common themes</div>', unsafe_allow_html=True)
            if synth.get("common_themes"):
                for theme in synth["common_themes"]:
                    chips = "".join(
                        f'<span class="support-chip">{s["expert"]} &middot; {s["timestamp"]}</span>'
                        for s in theme.get("support", [])
                    )
                    st.markdown(
                        f'<div class="theme-card"><h5>{theme["theme"]}</h5>'
                        f'<p>{theme.get("summary","")}</p>{chips}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No common themes identified.")

            st.markdown('<div class="section-label">Disagreements &amp; differences in emphasis</div>',
                        unsafe_allow_html=True)
            if synth.get("disagreements"):
                for d in synth["disagreements"]:
                    positions = "".join(
                        f'<div class="position-row"><b>{p["expert"]}</b> '
                        f'(<code>{p["timestamp"]}</code>) &mdash; {p["position"]}</div>'
                        for p in d.get("positions", [])
                    )
                    st.markdown(
                        f'<div class="diff-card"><h5>{d["topic"]}</h5>'
                        f'<p>{d.get("summary","")}</p>{positions}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No notable disagreements identified.")

# Tab 3: Free-form Q&A
with tab3:
    user_q = st.text_input(
        "Your question", key="freeform_q",
        placeholder="e.g. Do all three experts agree that training affects ROI?",
        label_visibility="collapsed",
    )
    if st.button("Ask", type="primary") and user_q:
        with st.spinner("Searching transcripts..."):
            try:
                result = answer_freeform(user_q, transcripts, api_key=API_KEY)
                if result.get("not_addressed"):
                    st.warning(result.get("answer") or "Not addressed in the transcripts.")
                else:
                    st.markdown('<div class="section-label">Answer</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="answer-card"><div class="body-text">'
                                f'{result.get("answer", "")}</div>', unsafe_allow_html=True)
                    for c in result.get("citations", []):
                        cls = "verified" if c.get("verified") else "unverified"
                        icon = "✓" if c.get("verified") else "⚠"
                        st.markdown(
                            f'<div class="evidence-item {cls}">'
                            f'<span class="evidence-ts">{icon} {c["expert"]} &middot; {c.get("market","")} '
                            f'&middot; {c["timestamp"]}</span><span>&ldquo;{c["quote"]}&rdquo;</span></div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown('</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(str(e))
