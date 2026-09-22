import os
import streamlit as st

from core.parser import parse_transcript, parse_interview_guide
from core.analysis import answer_question_for_expert, synthesize_across_experts, answer_freeform
from dotenv import load_dotenv
load_dotenv(override=True)

st.set_page_config(page_title="Expert Call Analyzer", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data_")
DEFAULT_GUIDE = os.path.join(DATA_DIR, "Interview_Guide.txt")
DEFAULT_TRANSCRIPTS = [
    os.path.join(DATA_DIR, "Transcript_1_France.txt"),
    os.path.join(DATA_DIR, "Transcript_2_Germany.txt"),
    os.path.join(DATA_DIR, "Transcript_3_UK.txt"),
]

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "transcripts" not in st.session_state:
    st.session_state.transcripts = None
if "questions" not in st.session_state:
    st.session_state.questions = None
if "per_question" not in st.session_state:
    st.session_state.per_question = {}   # question -> {expert_name: result_dict}
if "synthesis" not in st.session_state:
    st.session_state.synthesis = {}      # question -> synthesis_dict


def load_default_data():
    with open(DEFAULT_GUIDE, encoding="utf-8") as f:
        st.session_state.questions = parse_interview_guide(f.read())
    transcripts = []
    for path in DEFAULT_TRANSCRIPTS:
        with open(path, encoding="utf-8") as f:
            transcripts.append(parse_transcript(f.read()))
    st.session_state.transcripts = transcripts


# ---------------------------------------------------------------------------
# Sidebar: data + API key
# ---------------------------------------------------------------------------
st.sidebar.title("Setup")

api_key_input = st.sidebar.text_input("Gemini API key", type="password",
                                       value=os.environ.get("GEMINI_API_KEY", ""),
                                       help="Or set GEMINI_API_KEY as an environment variable before launching.")

st.sidebar.markdown("---")
st.sidebar.subheader("Data")
use_sample = st.sidebar.checkbox("Use bundled sample data (Hasamex case pack)", value=True)

if use_sample:
    if st.sidebar.button("Load sample transcripts", use_container_width=True):
        load_default_data()
        st.session_state.per_question = {}
        st.session_state.synthesis = {}
        st.sidebar.success(f"Loaded {len(st.session_state.transcripts)} transcripts and "
                            f"{len(st.session_state.questions)} questions.")
else:
    guide_file = st.sidebar.file_uploader("Interview guide (.txt)", type=["txt"])
    transcript_files = st.sidebar.file_uploader("Transcripts (.txt)", type=["txt"],
                                                 accept_multiple_files=True)
    if st.sidebar.button("Load uploaded files", use_container_width=True):
        if guide_file and transcript_files:
            st.session_state.questions = parse_interview_guide(guide_file.getvalue().decode("utf-8"))
            st.session_state.transcripts = [parse_transcript(f.getvalue().decode("utf-8"))
                                             for f in transcript_files]
            st.session_state.per_question = {}
            st.session_state.synthesis = {}
            st.sidebar.success(f"Loaded {len(st.session_state.transcripts)} transcripts and "
                                f"{len(st.session_state.questions)} questions.")
        else:
            st.sidebar.error("Please provide both the interview guide and at least one transcript.")

if st.session_state.transcripts is None:
    load_default_data()  # sensible default on first run

st.sidebar.markdown("---")
st.sidebar.caption(
    "Every answer below must be traced back to a verbatim, timestamped quote. "
    "Quotes are checked against the source transcript before being shown - "
    "unverified quotes are flagged, never silently trusted."
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🤖 Expert Call Analyzer")
st.caption("Hasamex AI Engineer case study — European Robotic Surgery Market")

transcripts = st.session_state.transcripts
questions = st.session_state.questions

with st.expander("Loaded experts", expanded=False):
    for t in transcripts:
        st.markdown(f"- **{t['name']}** — {t.get('role','')} ({t.get('market','')}), "
                     f"{len(t['segments'])} timestamped segments")

tab1, tab2, tab3 = st.tabs(["📋 Per-Question Answers", "🔍 Cross-Expert Themes", "💬 Ask Across Transcripts"])

# ---------------------------------------------------------------------------
# Tab 1: Per-question answers
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Answer the interview guide, per expert")
    question = st.selectbox("Interview guide question", questions, key="q1")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        run_one = st.button("Analyze this question", type="primary")
    with col_b:
        run_all = st.button("Analyze ALL questions (for all experts)")

    def run_question(q):
        results = {}
        for t in transcripts:
            with st.spinner(f"Analyzing '{t['name']}'..."):
                results[t["name"]] = answer_question_for_expert(q, t, api_key=api_key_input)
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
        cols = st.columns(len(transcripts))
        for col, t in zip(cols, transcripts):
            res = results.get(t["name"])
            with col:
                st.markdown(f"**{t['name']}** ({t.get('market','')})")
                if not res:
                    st.info("Not yet analyzed.")
                    continue
                if res.get("not_addressed"):
                    st.warning("Not addressed in this transcript.")
                    continue
                st.write(res.get("answer", ""))
                for ev in res.get("evidence", []):
                    icon = "✔️" if ev.get("verified") else "⚠️"
                    st.markdown(f"{icon} `{ev['timestamp']}` — \u201c{ev['quote']}\u201d")
                    if not ev.get("verified"):
                        st.caption("Quote could not be matched verbatim to the transcript — flagged, not hidden.")
    else:
        st.info("Click 'Analyze this question' to generate grounded answers for each expert.")

# ---------------------------------------------------------------------------
# Tab 2: Cross-expert synthesis
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Common themes and disagreements across experts")
    question2 = st.selectbox("Interview guide question", questions, key="q2")

    prereq = st.session_state.per_question.get(question2)
    if not prereq:
        st.info("Analyze this question in the 'Per-Question Answers' tab first, "
                 "so the synthesis has grounded per-expert answers to compare.")
    else:
        if st.button("Find themes & disagreements", type="primary"):
            with st.spinner("Comparing experts..."):
                try:
                    st.session_state.synthesis[question2] = synthesize_across_experts(
                        question2, prereq, api_key=api_key_input
                    )
                except Exception as e:
                    st.error(str(e))

        synth = st.session_state.synthesis.get(question2)
        if synth:
            st.markdown("### 🤝 Common themes")
            if synth.get("common_themes"):
                for theme in synth["common_themes"]:
                    support = ", ".join(f"{s['expert']} ({s['timestamp']})" for s in theme.get("support", []))
                    st.markdown(f"**{theme['theme']}** — {theme.get('summary','')}")
                    st.caption(f"Supported by: {support}")
            else:
                st.write("No common themes identified.")

            st.markdown("### ⚔️ Disagreements / differences in emphasis")
            if synth.get("disagreements"):
                for d in synth["disagreements"]:
                    st.markdown(f"**{d['topic']}** — {d.get('summary','')}")
                    for p in d.get("positions", []):
                        st.markdown(f"- {p['expert']} (`{p['timestamp']}`): {p['position']}")
            else:
                st.write("No notable disagreements identified.")

# ---------------------------------------------------------------------------
# Tab 3: Free-form Q&A
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Ask any question across all transcripts")
    user_q = st.text_input("Your question", placeholder="e.g. Do all three experts agree that training affects ROI?")
    if st.button("Ask", type="primary") and user_q:
        with st.spinner("Searching transcripts..."):
            try:
                result = answer_freeform(user_q, transcripts, api_key=api_key_input)
                if result.get("not_addressed"):
                    st.warning(result.get("answer") or "Not addressed in the transcripts.")
                else:
                    st.write(result.get("answer", ""))
                    st.markdown("**Citations:**")
                    for c in result.get("citations", []):
                        icon = "✔️" if c.get("verified") else "⚠️"
                        st.markdown(f"{icon} **{c['expert']}** ({c.get('market','')}) `{c['timestamp']}` — "
                                    f"\u201c{c['quote']}\u201d")
            except Exception as e:
                st.error(str(e))
