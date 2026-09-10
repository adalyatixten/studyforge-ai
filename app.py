import os
import re
import sqlite3
from collections import Counter

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from pypdf import PdfReader


# -----------------------------
# Configuration
# -----------------------------

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY) if API_KEY else None

DB_FILE = "studyforge.db"


# -----------------------------
# Database
# -----------------------------

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


# -----------------------------
# PDF Processing
# -----------------------------

def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text, len(reader.pages)


# -----------------------------
# Local Topic Detection
# -----------------------------

STOP_WORDS = {
    "the", "and", "for", "that", "with", "this", "from",
    "are", "was", "were", "have", "has", "into", "your",
    "you", "will", "can", "not", "all", "but", "using",
    "question", "questions", "answer", "answers",
    "mark", "marks", "page", "exam", "examination",
    "student", "students"
}


def detect_topics_locally(text):
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())

    filtered_words = [
        word
        for word in words
        if word not in STOP_WORDS
    ]

    counts = Counter(filtered_words)

    common_words = counts.most_common(12)

    return [
        word.replace("-", " ").title()
        for word, _ in common_words
    ]


# -----------------------------
# AI Topic Detection
# -----------------------------

def detect_topics_with_ai(text):
    if not client:
        return None

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=f"""
You are an academic study assistant.

Analyze the following study material.

Identify the most important study topics and subtopics
that a student should revise for an examination.

Return a concise Markdown list.

DOCUMENT:

{text[:15000]}
"""
    )

    return response.output_text


# -----------------------------
# App
# -----------------------------

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

uploaded_file = st.file_uploader(
    "Upload your study material",
    type="pdf",
)


if uploaded_file is None:
    st.info("Upload a PDF to begin.")

else:
    text, page_count = extract_pdf_text(uploaded_file)

    st.success("PDF uploaded successfully!")

    st.write(f"**Pages:** {page_count}")

    document_tab, topics_tab, quiz_tab, progress_tab = st.tabs(
        [
            "📄 Document",
            "🧠 Topics",
            "📝 Revision",
            "📊 Progress",
        ]
    )

    # -----------------------------
    # Document
    # -----------------------------

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

    # -----------------------------
    # Topics
    # -----------------------------

    with topics_tab:

        st.subheader("Study Topics")

        if st.button("Analyze study material"):

            with st.spinner("Analyzing document..."):

                try:
                    ai_topics = detect_topics_with_ai(text)

                    if ai_topics:

                        st.session_state["ai_topics"] = ai_topics

                        st.success("AI analysis completed.")

                    else:

                        raise ValueError("AI unavailable")

                except (RateLimitError, ValueError):

                    st.warning(
                        "OpenAI API credits are currently unavailable. "
                        "Using local topic detection instead."
                    )

                    local_topics = detect_topics_locally(text)

                    st.session_state["local_topics"] = local_topics

        if "ai_topics" in st.session_state:

            st.markdown(st.session_state["ai_topics"])

        elif "local_topics" in st.session_state:

            st.write("### Detected Topics")

            for number, topic in enumerate(
                st.session_state["local_topics"],
                start=1,
            ):
                st.write(f"{number}. **{topic}**")

        else:

            st.info(
                "Click 'Analyze study material' to detect topics."
            )

    # -----------------------------
    # Revision
    # -----------------------------

    with quiz_tab:

        st.subheader("Revision Session")

        topics = st.session_state.get(
            "local_topics",
            [],
        )

        if not topics:

            st.info(
                "Analyze the document first to create a revision session."
            )

        else:

            selected_topic = st.selectbox(
                "Choose a topic",
                topics,
            )

            st.write("### Practice Questions")

            st.write(
                f"1. Explain **{selected_topic}** in your own words."
            )

            st.write(
                f"2. What are the most important rules or formulas "
                f"related to **{selected_topic}**?"
            )

            st.write(
                f"3. Give an example where **{selected_topic}** "
                f"would be used."
            )

            st.write(
                f"4. What mistakes could a student make when solving "
                f"a problem involving **{selected_topic}**?"
            )

            st.divider()

            confidence = st.slider(
                "How confident are you with this topic?",
                min_value=1,
                max_value=5,
                value=3,
            )

            if st.button("Save progress"):

                save_progress(
                    selected_topic,
                    confidence,
                )

                st.success("Progress saved!")

    # -----------------------------
    # Progress
    # -----------------------------

    with progress_tab:

        st.subheader("Learning Progress")

        progress_data = load_progress()

        if progress_data.empty:

            st.info(
                "Complete a revision session to start tracking progress."
            )

        else:

            latest_scores = (
                progress_data
                .groupby("topic")["confidence"]
                .mean()
                .sort_values()
            )

            st.write("### Average Confidence")

            st.bar_chart(latest_scores)

            st.write("### Study History")

            st.dataframe(
                progress_data,
                use_container_width=True,
            )

            weakest_topic = latest_scores.index[0]

            st.warning(
                f"Current weakest topic: **{weakest_topic}**"
            )