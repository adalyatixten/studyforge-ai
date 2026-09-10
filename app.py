import streamlit as st
from pypdf import PdfReader


st.set_page_config(
    page_title="StudyForge AI",
    page_icon="📚"
)

st.title("📚 StudyForge AI")

st.write(
    "Upload your study materials and turn them "
    "into smarter revision sessions."
)

uploaded_file = st.file_uploader(
    "Upload a PDF",
    type="pdf"
)

if uploaded_file is not None:
    reader = PdfReader(uploaded_file)

    st.success("PDF uploaded successfully!")

    st.write(f"Pages: {len(reader.pages)}")

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    st.subheader("Document Preview")

    st.text_area(
        "Extracted text",
        text[:5000],
        height=300

        
    )