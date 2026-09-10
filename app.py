import os
import re
import sqlite3
from html import escape

import pandas as pd
import streamlit as st
import yake
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from pypdf import PdfReader


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY) if API_KEY else None

DB_FILE = "studyforge.db"


# =========================================================
# DATABASE
# =========================================================

def init_database():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


def save_progress(topic, confidence):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO progress (topic, confidence)
        VALUES (?, ?)
        """,
        (topic, confidence),
    )

    connection.commit()
    connection.close()


def load_progress():
    connection = sqlite3.connect(DB_FILE)

    dataframe = pd.read_sql_query(
        """
        SELECT topic, confidence, created_at
        FROM progress
        ORDER BY created_at DESC
        """,
        connection,
    )

    connection.close()

    return dataframe


# =========================================================
# PDF PROCESSING
# =========================================================

def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)

    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text_parts.append(page_text)

    return "\n".join(text_parts), len(reader.pages)


# =========================================================
# OFFLINE TOPIC DETECTION
# =========================================================

def detect_topics_locally(text):
    text_lower = text.lower()

    topic_patterns = {
        "Differentiation": [
            "differentiate",
            "differentiation",
            "derivative",
            "derivatives",
        ],
        "Product Rule": [
            "product rule",
        ],
        "Quotient Rule": [
            "quotient rule",
        ],
        "Chain Rule": [
            "chain rule",
        ],
        "Implicit Differentiation": [
            "implicit differentiation",
            "differentiate implicitly",
            "implicitly",
        ],
        "Tangent and Normal": [
            "tangent",
            "normal to the curve",
            "normal line",
        ],
        "Rate of Change": [
            "rate of change",
            "rate at which",
            "related rates",
        ],
        "Integration": [
            "integrate",
            "integration",
            "integral",
            "integrals",
        ],
        "Definite Integrals": [
            "definite integral",
            "limits of integration",
        ],
        "Substitution": [
            "substitution",
            "u-substitution",
            "change of variable",
        ],
        "Integration by Parts": [
            "integration by parts",
        ],
        "Partial Fractions": [
            "partial fraction",
            "partial fractions",
        ],
        "Trigonometric Functions": [
            "trigonometric",
            "sine",
            "cosine",
            "sin ",
            "cos ",
            "tan ",
        ],
        "Exponential Functions": [
            "exponential function",
            "exponential functions",
        ],
        "Logarithmic Functions": [
            "logarithmic",
            "natural logarithm",
            "ln ",
        ],
        "Area Under a Curve": [
            "area under",
            "area bounded",
            "area enclosed",
            "area of the region",
        ],
        "Volume": [
            "volume",
            "volume of revolution",
        ],
        "Quadratic Equations": [
            "quadratic",
            "quadratic equation",
        ],
        "Mean, Median and Mode": [
            "mean",
            "median",
            "mode",
        ],
        "Standard Deviation": [
            "standard deviation",
        ],
        "Variance": [
            "variance",
        ],
        "Quartiles and IQR": [
            "quartile",
            "interquartile",
            "iqr",
        ],
        "Normal Distribution": [
            "normal distribution",
            "normally distributed",
        ],
        "Z-Score": [
            "z-score",
            "z score",
            "standard score",
        ],
        "Binomial Distribution": [
            "binomial distribution",
            "binomial",
        ],
        "Poisson Distribution": [
            "poisson distribution",
            "poisson",
        ],
        "Correlation": [
            "correlation",
            "correlation coefficient",
        ],
        "Regression": [
            "regression",
            "regression line",
        ],
    }

    scored_topics = []

    for topic, patterns in topic_patterns.items():
        score = 0

        for pattern in patterns:
            occurrences = text_lower.count(pattern)

            if " " in pattern:
                score += occurrences * 2
            else:
                score += occurrences

        if score > 0:
            scored_topics.append((topic, score))

    scored_topics.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    topics = [
        topic
        for topic, score in scored_topics
    ]

    # YAKE fallback
    if len(topics) < 6:
        extractor = yake.KeywordExtractor(
            lan="en",
            n=3,
            dedupLim=0.85,
            top=40,
        )

        keywords = extractor.extract_keywords(text)

        blocked_phrases = {
            "question",
            "questions",
            "solution",
            "answer",
            "answers",
            "marking guide",
            "final examination",
            "examination",
            "student",
            "students",
            "marks",
            "technical mathematics",
            "subject title",
            "subject code",
            "semester",
            "intake",
            "total marks",
            "materials allowed",
            "allowed standard",
            "science and technology",
            "foundation in science",
            "time allowed",
            "reading time",
            "working time",
            "calculator",
            "dictionary",
        }

        for keyword, score in keywords:
            cleaned = keyword.strip()
            cleaned_lower = cleaned.lower()

            if len(cleaned) < 4:
                continue

            if any(
                blocked in cleaned_lower
                for blocked in blocked_phrases
            ):
                continue

            if re.search(
                r"\b(question|mark|marks|paper|semester|subject)\b",
                cleaned_lower,
            ):
                continue

            cleaned = cleaned.title()

            if cleaned not in topics:
                topics.append(cleaned)

            if len(topics) >= 12:
                break

    return topics[:12]


# =========================================================
# AI TOPIC DETECTION
# =========================================================

def detect_topics_with_ai(text):
    if not client:
        return None

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=f"""
You are an academic study assistant.

Analyze the study material below and identify the most
important academic topics that a student should revise.

Rules:

- Ignore exam instructions and administrative information.
- Ignore marks, materials allowed and time limits.
- Prefer specific academic concepts.
- One topic per line.
- Do not number topics.
- Do not use bullet points.
- Do not explain the topics.
- Return around 8 to 12 topics.

DOCUMENT:

{text[:15000]}
"""
    )

    topics = []

    for line in response.output_text.splitlines():
        cleaned = re.sub(
            r"^[\-\*\d\.\)\s]+",
            "",
            line,
        ).strip()

        if cleaned and cleaned not in topics:
            topics.append(cleaned)

    return topics[:12]


# =========================================================
# APP INITIALIZATION
# =========================================================

init_database()

st.set_page_config(
    page_title="StudyForge AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CUSTOM STYLE
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    .hero {
        padding: 2.4rem;
        border-radius: 22px;
        border: 1px solid rgba(255,255,255,0.08);
        background:
            radial-gradient(
                circle at top right,
                rgba(125, 92, 255, 0.20),
                transparent 40%
            ),
            rgba(255,255,255,0.025);
        margin-bottom: 1.5rem;
    }

    .hero h1 {
        font-size: 3rem;
        margin: 0;
        padding: 0;
    }

    .hero p {
        font-size: 1.1rem;
        opacity: 0.72;
        margin-top: 0.8rem;
        margin-bottom: 0;
    }

    .badge {
        display: inline-block;
        padding: 6px 11px;
        margin-right: 7px;
        margin-top: 16px;
        border-radius: 20px;
        font-size: 0.82rem;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.04);
    }

    .section-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 1.4rem;
        margin-bottom: 1rem;
        background: rgba(255,255,255,0.02);
    }

    .topic-card {
        padding: 0.8rem 1rem;
        border-radius: 12px;
        margin-bottom: 8px;
        border: 1px solid rgba(255,255,255,0.07);
        background: rgba(255,255,255,0.025);
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(255,255,255,0.08);
        padding: 18px;
        border-radius: 16px;
        background: rgba(255,255,255,0.02);
    }

    .small-muted {
        opacity: 0.55;
        font-size: 0.9rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.title("📚 StudyForge")

    st.caption("AI-powered study workspace")

    st.divider()

    st.write("### System")

    if API_KEY:
        st.success("API key loaded")
    else:
        st.warning("Offline mode")

    st.write("**Storage**")
    st.caption("SQLite local database")

    st.write("**Document engine**")
    st.caption("PyPDF")

    st.write("**Offline analysis**")
    st.caption("Concept detection + YAKE")

    st.divider()

    st.caption("StudyForge AI • Portfolio Project")


# =========================================================
# HERO
# =========================================================

st.markdown(
    """
<div class="hero">
<h1>📚 StudyForge AI</h1>
<p>Turn course materials into structured revision, practice sessions and measurable learning progress.</p>
<span class="badge">PDF Analysis</span>
<span class="badge">Topic Detection</span>
<span class="badge">Adaptive Revision</span>
<span class="badge">Progress Tracking</span>
</div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "Upload study material",
    type="pdf",
)


if uploaded_file is None:
    st.markdown("### Start a new study session")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
<div class="section-card">
<h3>📄 Upload</h3>
<p>Add lecture notes, revision packs, past papers or textbooks.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
<div class="section-card">
<h3>🧠 Analyze</h3>
<p>StudyForge identifies important topics automatically.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
<div class="section-card">
<h3>📊 Improve</h3>
<p>Practice weak topics and track confidence over time.</p>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.stop()


# =========================================================
# RESET SESSION FOR NEW DOCUMENT
# =========================================================

if (
    "uploaded_file_name" not in st.session_state
    or st.session_state["uploaded_file_name"] != uploaded_file.name
):
    st.session_state["uploaded_file_name"] = uploaded_file.name

    st.session_state.pop("topics", None)
    st.session_state.pop("topics_editor", None)
    st.session_state.pop("analysis_mode", None)


# =========================================================
# PROCESS PDF
# =========================================================

try:
    text, page_count = extract_pdf_text(uploaded_file)

except Exception as error:
    st.error(
        f"Could not read PDF: {error}"
    )
    st.stop()


if not text.strip():
    st.warning(
        "No readable text was found in this PDF."
    )
    st.stop()


# =========================================================
# DOCUMENT SUMMARY
# =========================================================

progress_data = load_progress()

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Pages",
    page_count,
)

col2.metric(
    "Characters",
    f"{len(text):,}",
)

col3.metric(
    "Topics",
    len(
        st.session_state.get(
            "topics",
            [],
        )
    ),
)

col4.metric(
    "Study Sessions",
    len(progress_data),
)

st.success(
    f"{uploaded_file.name} loaded successfully."
)


# =========================================================
# MAIN WORKSPACE
# =========================================================

document_tab, topics_tab, revision_tab, progress_tab = st.tabs(
    [
        "📄 Document",
        "🧠 Topics",
        "📝 Revision",
        "📊 Progress",
    ]
)


# =========================================================
# DOCUMENT TAB
# =========================================================

with document_tab:
    st.subheader("Document")

    st.caption(
        "Preview the text extracted from your study material."
    )

    st.text_area(
        "Document text",
        text[:12000],
        height=520,
        label_visibility="collapsed",
    )

    if len(text) > 12000:
        st.caption(
            "Preview limited to the first 12,000 characters."
        )


# =========================================================
# TOPICS TAB
# =========================================================

with topics_tab:
    header_col, button_col = st.columns(
        [4, 1]
    )

    with header_col:
        st.subheader("Topic Intelligence")

        st.caption(
            "Identify the concepts that matter most."
        )

    with button_col:
        analyze_clicked = st.button(
            "Analyze material",
            type="primary",
            use_container_width=True,
        )

    if analyze_clicked:
        with st.spinner(
            "Analyzing your study material..."
        ):
            topics = None
            analysis_mode = None

            if client:
                try:
                    topics = detect_topics_with_ai(text)

                    if topics:
                        analysis_mode = "AI"

                except RateLimitError:
                    st.warning(
                        "API credits unavailable. "
                        "Offline analysis activated."
                    )

                except Exception:
                    st.warning(
                        "AI service unavailable. "
                        "Offline analysis activated."
                    )

            if not topics:
                topics = detect_topics_locally(text)
                analysis_mode = "Offline"

            st.session_state["topics"] = topics
            st.session_state["analysis_mode"] = analysis_mode

            st.session_state["topics_editor"] = "\n".join(
                topics
            )

    if "topics" not in st.session_state:
        st.info(
            "Run an analysis to discover the main study topics."
        )

    else:
        mode = st.session_state.get(
            "analysis_mode",
            "Offline",
        )

        if mode == "AI":
            st.success("AI analysis completed.")
        else:
            st.info(
                "Offline analysis completed."
            )

        topics = st.session_state["topics"]

        st.markdown(
            f"### {len(topics)} topics detected"
        )

        topic_columns = st.columns(2)

        for index, topic in enumerate(topics):
            target_column = topic_columns[
                index % 2
            ]

            safe_topic = escape(topic)

            with target_column:
                st.markdown(
                    f"""
<div class="topic-card">
<b>{index + 1}. {safe_topic}</b>
</div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()

        with st.expander(
            "✏️ Review or edit detected topics"
        ):
            edited_topics = st.text_area(
                "One topic per line",
                key="topics_editor",
                height=260,
            )

            if st.button(
                "Save topic list"
            ):
                reviewed_topics = [
                    topic.strip()
                    for topic
                    in edited_topics.splitlines()
                    if topic.strip()
                ]

                st.session_state[
                    "topics"
                ] = reviewed_topics

                st.success(
                    "Topic list updated."
                )

                st.rerun()


# =========================================================
# REVISION TAB
# =========================================================

with revision_tab:
    st.subheader(
        "Revision Session"
    )

    st.caption(
        "Choose a topic and assess your current understanding."
    )

    topics = st.session_state.get(
        "topics",
        [],
    )

    if not topics:
        st.info(
            "Analyze the document first."
        )

    else:
        selected_topic = st.selectbox(
            "Topic",
            topics,
        )

        st.markdown(
            f"## {selected_topic}"
        )

        st.markdown(
            """
<div class="section-card">
<b>Goal</b><br>
Answer the questions without checking your notes first.
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
### Practice Questions

**1.** Explain **{selected_topic}** in your own words.

**2.** What are the most important rules,
formulas or principles related to **{selected_topic}**?

**3.** Give a practical or exam-style example
involving **{selected_topic}**.

**4.** What common mistakes can occur when
working with **{selected_topic}**?
            """
        )

        st.divider()

        confidence = st.slider(
            "Confidence",
            min_value=1,
            max_value=5,
            value=3,
        )

        confidence_labels = {
            1: "Very weak",
            2: "Weak",
            3: "Developing",
            4: "Confident",
            5: "Very confident",
        }

        st.caption(
            f"Current assessment: "
            f"{confidence_labels[confidence]}"
        )

        if st.button(
            "Save revision result",
            type="primary",
        ):
            save_progress(
                selected_topic,
                confidence,
            )

            st.success(
                "Revision progress saved."
            )


# =========================================================
# PROGRESS TAB
# =========================================================

with progress_tab:
    st.subheader(
        "Learning Dashboard"
    )

    progress_data = load_progress()

    if progress_data.empty:
        st.info(
            "Complete a revision session "
            "to start building your learning history."
        )

    else:
        average_scores = (
            progress_data
            .groupby("topic")["confidence"]
            .mean()
            .sort_values()
        )

        total_sessions = len(
            progress_data
        )

        topics_practiced = (
            progress_data["topic"].nunique()
        )

        average_confidence = (
            progress_data["confidence"].mean()
        )

        weakest_topic = (
            average_scores.index[0]
        )

        strongest_topic = (
            average_scores.index[-1]
        )

        highest_confidence = (
            average_scores.max()
        )

        metric1, metric2, metric3, metric4 = st.columns(
            4
        )

        metric1.metric(
            "Sessions",
            total_sessions,
        )

        metric2.metric(
            "Topics Practiced",
            topics_practiced,
        )

        metric3.metric(
            "Average Confidence",
            f"{average_confidence:.1f}/5",
        )

        metric4.metric(
            "Highest Confidence",
            f"{highest_confidence:.1f}/5",
        )

        st.caption(
            f"Strongest topic: **{strongest_topic}**"
        )

        st.divider()

        left, right = st.columns(
            [2, 1]
        )

        with left:
            st.markdown(
                "### Confidence by Topic"
            )

            st.bar_chart(
                average_scores
            )

        with right:
            st.markdown(
                "### Focus Recommendation"
            )

            safe_weakest_topic = escape(
                weakest_topic
            )

            st.markdown(
                f"""
<div class="section-card">
<span class="small-muted">Weakest topic</span>
<h3>{safe_weakest_topic}</h3>
<p>Prioritize this topic during your next revision session.</p>
</div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        st.markdown(
            "### Revision History"
        )

        st.dataframe(
            progress_data,
            use_container_width=True,
            hide_index=True,
        )