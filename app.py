import os
import re
import sqlite3

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

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text, len(reader.pages)


# =========================================================
# LOCAL TOPIC DETECTION
# =========================================================

def detect_topics_locally(text):
    keyword_extractor = yake.KeywordExtractor(
        lan="en",
        n=3,
        dedupLim=0.85,
        top=30,
    )

    keywords = keyword_extractor.extract_keywords(text)

    blocked_words = {
        "question",
        "questions",
        "solution",
        "answer",
        "answers",
        "marking guide",
        "examination",
        "final examination",
        "student",
        "students",
        "marks",
        "technical mathematics",
        "subject title",
        "subject code",
        "semester",
        "intake",
        "total marks",
    }

    topics = []

    for keyword, score in keywords:
        cleaned = keyword.strip().title()
        cleaned_lower = cleaned.lower()

        if len(cleaned) < 4:
            continue

        if any(
            blocked_word in cleaned_lower
            for blocked_word in blocked_words
        ):
            continue

        if cleaned not in topics:
            topics.append(cleaned)

        if len(topics) == 12:
            break

    return topics


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

Analyze the study material below.

Identify the most important topics a student needs to revise.

Rules:
- Return only topic names.
- One topic per line.
- Do not number them.
- Do not use bullet points.
- Do not include explanations.
- Prefer specific academic concepts.
- Return around 8 to 12 topics.

DOCUMENT:

{text[:15000]}
"""
    )

    raw_topics = response.output_text

    topics = []

    for line in raw_topics.splitlines():
        cleaned = re.sub(
            r"^[\-\*\d\.\)\s]+",
            "",
            line,
        ).strip()

        if cleaned:
            topics.append(cleaned)

    return topics[:12]


# =========================================================
# APP SETUP
# =========================================================

init_database()

st.set_page_config(
    page_title="StudyForge AI",
    page_icon="📚",
    layout="wide",
)

st.title("📚 StudyForge AI")

st.write(
    "Turn your study materials into structured revision sessions."
)


# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "Upload your study material",
    type="pdf",
)


if uploaded_file is None:
    st.info("Upload a PDF to begin.")

else:
    # Reset topics when a different PDF is uploaded
    if (
        "uploaded_file_name" not in st.session_state
        or st.session_state["uploaded_file_name"] != uploaded_file.name
    ):
        st.session_state["uploaded_file_name"] = uploaded_file.name

        st.session_state.pop("topics", None)
        st.session_state.pop("topics_editor", None)
        st.session_state.pop("analysis_mode", None)

    # Extract PDF text
    try:
        text, page_count = extract_pdf_text(uploaded_file)

    except Exception as error:
        st.error(f"Could not read PDF: {error}")
        st.stop()

    st.success("PDF uploaded successfully!")

    st.write(f"**Pages:** {page_count}")

    if not text.strip():
        st.warning(
            "No readable text was found in this PDF."
        )
        st.stop()

    # =====================================================
    # TABS
    # =====================================================

    document_tab, topics_tab, revision_tab, progress_tab = st.tabs(
        [
            "📄 Document",
            "🧠 Topics",
            "📝 Revision",
            "📊 Progress",
        ]
    )

    # =====================================================
    # DOCUMENT TAB
    # =====================================================

    with document_tab:
        st.subheader("Document Preview")

        st.text_area(
            "Extracted text",
            text[:10000],
            height=500,
        )

        st.caption(
            f"Extracted approximately {len(text):,} characters."
        )

    # =====================================================
    # TOPICS TAB
    # =====================================================

    with topics_tab:
        st.subheader("Study Topics")

        if st.button(
            "Analyze study material",
            type="primary",
        ):
            with st.spinner("Analyzing document..."):

                topics = None
                analysis_mode = None

                # Try OpenAI first
                if client:
                    try:
                        topics = detect_topics_with_ai(text)
                        analysis_mode = "AI"

                    except RateLimitError:
                        st.warning(
                            "OpenAI API credits are currently unavailable. "
                            "Using local topic detection instead."
                        )

                    except Exception:
                        st.warning(
                            "AI analysis is currently unavailable. "
                            "Using local topic detection instead."
                        )

                # Local fallback
                if not topics:
                    topics = detect_topics_locally(text)
                    analysis_mode = "Local"

                st.session_state["topics"] = topics
                st.session_state["analysis_mode"] = analysis_mode

                st.session_state["topics_editor"] = "\n".join(
                    topics
                )

        # Display detected topics
        if "topics" in st.session_state:
            mode = st.session_state.get(
                "analysis_mode",
                "Unknown",
            )

            if mode == "AI":
                st.success(
                    "Topics detected using AI."
                )
            else:
                st.info(
                    "Topics detected using local analysis."
                )

            st.write("### Detected Topics")

            edited_topics = st.text_area(
                "Review or edit the topics",
                key="topics_editor",
                height=300,
            )

            if st.button("Save reviewed topics"):
                reviewed_topics = [
                    topic.strip()
                    for topic in edited_topics.splitlines()
                    if topic.strip()
                ]

                st.session_state["topics"] = reviewed_topics

                st.success("Topics updated successfully.")

            st.write("### Current Topic List")

            for number, topic in enumerate(
                st.session_state["topics"],
                start=1,
            ):
                st.write(
                    f"{number}. **{topic}**"
                )

        else:
            st.info(
                "Click 'Analyze study material' to detect topics."
            )

    # =====================================================
    # REVISION TAB
    # =====================================================

    with revision_tab:
        st.subheader("Revision Session")

        topics = st.session_state.get(
            "topics",
            [],
        )

        if not topics:
            st.info(
                "Analyze the document first to create "
                "a revision session."
            )

        else:
            selected_topic = st.selectbox(
                "Choose a topic",
                topics,
            )

            st.write("### Practice Questions")

            st.write(
                f"1. Explain **{selected_topic}** "
                f"in your own words."
            )

            st.write(
                f"2. What are the most important rules "
                f"or formulas related to "
                f"**{selected_topic}**?"
            )

            st.write(
                f"3. Give an example where "
                f"**{selected_topic}** would be used."
            )

            st.write(
                f"4. What mistakes could a student make "
                f"when solving a problem involving "
                f"**{selected_topic}**?"
            )

            st.divider()

            confidence = st.slider(
                "How confident are you with this topic?",
                min_value=1,
                max_value=5,
                value=3,
            )

            st.caption(
                "1 = Very weak • 5 = Very confident"
            )

            if st.button(
                "Save progress",
                type="primary",
            ):
                save_progress(
                    selected_topic,
                    confidence,
                )

                st.success(
                    "Progress saved successfully!"
                )

    # =====================================================
    # PROGRESS TAB
    # =====================================================

    with progress_tab:
        st.subheader("Learning Progress")

        progress_data = load_progress()

        if progress_data.empty:
            st.info(
                "Complete a revision session "
                "to start tracking progress."
            )

        else:
            latest_scores = (
                progress_data
                .groupby("topic")["confidence"]
                .mean()
                .sort_values()
            )

            # ---------------------------------------------
            # Metrics
            # ---------------------------------------------

            average_confidence = (
                progress_data["confidence"].mean()
            )

            total_sessions = len(progress_data)

            topics_practiced = (
                progress_data["topic"].nunique()
            )

            weakest_topic = latest_scores.index[0]

            metric1, metric2, metric3 = st.columns(3)

            metric1.metric(
                "Revision Sessions",
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

            st.divider()

            # ---------------------------------------------
            # Chart
            # ---------------------------------------------

            st.write("### Average Confidence by Topic")

            st.bar_chart(
                latest_scores,
            )

            # ---------------------------------------------
            # Weakest Topic
            # ---------------------------------------------

            st.warning(
                f"Current weakest topic: "
                f"**{weakest_topic}**"
            )

            # ---------------------------------------------
            # History
            # ---------------------------------------------

            st.write("### Study History")

            st.dataframe(
                progress_data,
                use_container_width=True,
                hide_index=True,
            )